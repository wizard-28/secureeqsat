"""Feasibility probe (design/0017): does the soundness/repair story survive glitches?

For register-annotated masked gadgets:
  1. cross-check the in-house glitch checker against VerifMSI on every wire;
  2. saturate with the full Boolean rule set in egglog, registers OPAQUE
     (an uninterpreted operator) or TRANSPARENT (`reg(x) = x`, as a
     register-oblivious optimizer would treat them, plus register seeding at
     every gate operand so registers can be inserted);
  3. extract the cheapest circuit (cost = gates + registers) and check it;
  4. look for a glitch-secure circuit in egglog's own k-best frontier, and
     with the occurrence-aware glitch-constrained extractor (`gextract.py`);
  5. cross-check every reported circuit against VerifMSI.

    uv run python experiments/glitch_probe/probe.py [--k 30] [--no-oracle]

Purpose
-------
This produces the results table of finding F8 (see `RESULTS.md`): with registers
treated as transparent, cost-minimal extraction deletes them and the circuit leaks;
the glitch-constrained extractor puts them back. It also reports the number of
egglog's own cheapest choices that were glitch-secure (0 of 784 on the chain).

Two modes for registers: OPAQUE (a register is an unknown operator the rewrite rules
cannot see through, so it acts as a barrier) and TRANSPARENT (`reg(x) = x`, the
assumption that an optimiser treats registers as free wires and drops them).
"""

from __future__ import annotations

import argparse
import ast
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

from egglog import EGraph, Expr, StringLike, rewrite, ruleset

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from gextract import export, kbest, term_circuit  # noqa: E402
from glitch import GCircuit, check_glitch, check_glitch_free  # noqa: E402

# Where VerifMSI lives (outside the repo; GPL), and the driver script that runs inside
# its own virtual environment as a separate process.
ORACLE_DIR = Path(os.environ.get("SECUREEQSAT_ORACLE_DIR", Path.home() / "oracles"))
ORACLE_PY = ORACLE_DIR / "venv" / "bin" / "python"
DRIVER = HERE / "glitch_driver.py"


# ---- a tiny expression tree shared by fixtures, egglog and circuits ----------


class N:
    """A tiny expression node: an operator name plus operand nodes.

    Python operators build the tree, so `a & b` is an AND node, `a ^ b` an XOR node, and
    `x.reg()` a register node. The same tree is turned into a circuit (`to_circuit`)
    and into an egglog term (`to_egg`).
    """

    def __init__(self, op, *args):
        """`op` is "var", "const", "and", "xor" or "reg"; `args` are its operands."""
        self.op, self.args = op, args

    def __and__(self, o):
        """`self & o` builds an AND node."""
        return N("and", self, o)

    def __xor__(self, o):
        """`self ^ o` builds an XOR node."""
        return N("xor", self, o)

    def reg(self):
        """`self.reg()` builds a register node holding this value."""
        return N("reg", self)


def v(name):
    """A variable leaf named `name`."""
    return N("var", name)


def to_circuit(roots):
    """Turn expression trees into a `GCircuit` with the trees as outputs.

    Algorithm: recurse over each tree. A variable becomes an input wire, a constant a
    constant wire, a register a register wire over its operand, and an AND or XOR a
    gate. A node object used twice (the same Python object) is built once, via the
    `memo` table keyed by `id(n)`, so shared subexpressions stay shared.
    """
    c = GCircuit()
    memo = {}  # id of a node object -> its wire name

    def go(n):
        """Return the wire for node `n`, building operands first."""
        if id(n) in memo:
            return memo[id(n)]
        if n.op == "var":
            w = c.add_input(n.args[0])
        elif n.op == "const":
            w = c.add_const(n.args[0])
        elif n.op == "reg":
            w = c.add_reg(go(n.args[0]))
        else:
            w = c.add_gate(n.op, go(n.args[0]), go(n.args[1]))
        memo[id(n)] = w
        return w

    c.outputs = [go(r) for r in roots]
    return c


# ---- fixtures ---------------------------------------------------------------


def isw(x0, x1, y0, y1, r):
    """ISW masked AND over expression nodes; returns the two output share nodes."""
    c0 = (x0 & y0) ^ r
    c1 = ((r ^ (x0 & y1)) ^ (x1 & y0)) ^ (x1 & y1)
    return c0, c1


def dom(x0, x1, y0, y1, z, regs=True):
    """DOM-indep AND; with regs, the cross terms are registered (VerifMSI's
    benchmarks/dom_and/generate_dom_and.py, 2 shares)."""
    t0 = (x0 & y1) ^ z  # cross term x0*y1 masked by z
    t1 = (x1 & y0) ^ z  # cross term x1*y0 masked by z
    if regs:
        t0, t1 = t0.reg(), t1.reg()  # register both cross terms (the glitch barrier)
    return (x0 & y0) ^ t0, (x1 & y1) ^ t1


A = ["a0", "a1", "b0", "b1"]  # the four input share names of an AND gadget
SEC2 = {"a": ["a0", "a1"], "b": ["b0", "b1"]}  # secret groups for two secrets
SEC3 = {**SEC2, "d": ["d0", "d1"]}  # `**` copies SEC2's entries, then adds a third


def fixtures():
    """The four test circuits: {name: (output expression trees, secrets, randoms)}.

    ISW with no registers, DOM with no registers, DOM with registers (the
    glitch-robust construction), and a chain of two registered DOM gadgets.
    """
    a0, a1, b0, b1, d0, d1 = (v(n) for n in ("a0", "a1", "b0", "b1", "d0", "d1"))
    r, z1, z2 = v("r"), v("z1"), v("z2")  # fresh randoms for the gadgets
    t = dom(a0, a1, b0, b1, z1)  # the first registered DOM gadget's output shares
    return {
        "isw (no registers)": (isw(a0, a1, b0, b1, r), SEC2, ["r"]),
        "dom (no registers)": (dom(a0, a1, b0, b1, z1, regs=False), SEC2, ["z1"]),
        "dom (registered)": (dom(a0, a1, b0, b1, z1), SEC2, ["z1"]),
        # `*t` unpacks the two output shares as the next gadget's first operand
        "dom chain (registered)": (dom(*t, d0, d1, z2), SEC3, ["z1", "z2"]),
    }


# ---- egglog ---------------------------------------------------------------------


class G(Expr):
    """The egglog sort for Boolean terms with registers (signatures only)."""

    @classmethod
    def var(cls, name: StringLike) -> G: ...
    @classmethod
    def zero(cls) -> G: ...
    def __xor__(self, other: G) -> G: ...
    def __and__(self, other: G) -> G: ...
    def reg(self) -> G: ...


@ruleset
def boolean(a: G, b: G, c: G):
    """The full Boolean rules: XOR/AND laws plus distributivity and factoring."""
    yield rewrite(a ^ b).to(b ^ a)  # XOR commutativity
    yield rewrite((a ^ b) ^ c).to(a ^ (b ^ c))  # XOR associativity
    yield rewrite(a ^ a).to(G.zero())  # x ^ x = 0
    yield rewrite(a ^ G.zero()).to(a)  # x ^ 0 = x
    yield rewrite(a & b).to(b & a)  # AND commutativity
    yield rewrite(a & (b ^ c)).to((a & b) ^ (a & c))  # distributivity
    yield rewrite((a & b) ^ (a & c)).to(a & (b ^ c))  # factoring


@ruleset
def transparent(a: G, b: G):
    """Registers as free wires: `reg(x) = x`, plus a register seeded on each operand."""
    yield rewrite(a.reg()).to(a)
    # seed a register on every gate operand; with reg(x) = x this only adds a
    # self-loop that extraction may take per occurrence (register insertion)
    yield rewrite(a ^ b).to(a.reg() ^ b)
    yield rewrite(a & b).to(a.reg() & b)


def to_egg(n):
    """Convert an expression tree `N` into an egglog `G` term (recursively)."""
    if n.op == "var":
        return G.var(n.args[0])
    if n.op == "reg":
        return to_egg(n.args[0]).reg()
    a, b = to_egg(n.args[0]), to_egg(n.args[1])
    return a & b if n.op == "and" else a ^ b


class _GNS:
    """Stand-in for `G` when evaluating egglog's printed text: builds `N` trees."""

    @staticmethod
    def var(name):
        """A variable leaf."""
        return v(name)

    @staticmethod
    def zero():
        """The constant 0 leaf."""
        return N("const", 0)


def parse(text):
    """Turn egglog's printed extraction into an `N` tree (as `port.parse_extracted`).

    The text may contain shared-subterm bindings followed by a result expression. The
    bindings are run first in a restricted namespace where `G` means `_GNS`, then the
    last expression is evaluated; `__builtins__` is emptied so the text can only build
    trees.
    """
    tree = ast.parse(text)  # parse into statements
    ns = {"G": _GNS}  # names available to the printed text
    for stmt in tree.body[:-1]:  # all statements but the last: the bindings
        exec(  # noqa: S102 - egglog's own printed extraction
            compile(ast.Module(body=[stmt], type_ignores=[]), "<x>", "exec"),
            {"__builtins__": {}},
            ns,
        )
    return eval(  # noqa: S307
        compile(ast.Expression(body=tree.body[-1].value), "<x>", "eval"),
        {"__builtins__": {}},
        ns,
    )


def saturate(roots, mode, iters=4):
    """Saturate the circuit's expressions in egglog; return `(egraph, handles)`.

    `mode` is "opaque" (only the Boolean rules; registers are barriers) or
    "transparent" (the Boolean rules plus `reg(x) = x` and register seeding). `a | b`
    runs two rule sets in the same round, and `sched * iters` repeats the schedule.
    """
    eg = EGraph()
    # name each output "o0", "o1", ... so it can be found again after serialising
    handles = [eg.let(f"o{i}", to_egg(r)) for i, r in enumerate(roots)]
    sched = boolean if mode == "opaque" else boolean | transparent
    eg.run(sched * iters)
    return eg, handles


def show(t):
    """Readable text for an extracted term, e.g. `reg((a0 & b1))`."""
    if t[0] == "var":
        return t[1]
    if t[0] == "zero":
        return "0"
    if t[0] == "reg":
        return f"reg({show(t[1])})"
    sym = " & " if t[0] == "and" else " ^ "
    return "(" + sym.join(show(x) for x in t[1:]) + ")"


# ---- evaluation -----------------------------------------------------------------


def free_of(secrets, randoms):
    """Free (uniform) variables: share 0 of every secret plus the fresh randoms."""
    return [sh[0] for sh in secrets.values()] + list(randoms)


def cost(c):
    """Cost of a circuit: gates plus registers (each counts 1)."""
    return c.count("and", "xor") + c.count("reg")


def verdict(c, secrets, randoms):
    """`(glitch_leaks, glitch_free_leaks)` for a circuit: two booleans.

    Each is True if at least one probe leaks under that model. A circuit that is
    glitch-free-secure but not glitch-secure gives `(True, False)`.
    """
    free = free_of(secrets, randoms)
    g = check_glitch(c, secrets, free)  # {wire: safe?} with glitches
    f = check_glitch_free(c, secrets, free)  # {wire: safe?} without glitches
    return (not all(g.values()), not all(f.values()))


def describe(c, secrets, randoms):
    """One-line summary: cost, gate/register split, and both verdicts."""
    gl, fl = verdict(c, secrets, randoms)
    return (
        f"{cost(c):>3} = {c.count('and', 'xor'):>2}g + {c.count('reg')}reg  "
        f"glitch-free: {'LEAKS' if fl else 'secure':6}  "
        f"glitch: {'LEAKS' if gl else 'secure'}"
    )


def oracle(c, secrets, randoms):
    """Ask VerifMSI about every wire of `c`; return its decoded JSON answer.

    Algorithm: serialise the circuit as JSON, start VerifMSI's driver as a separate
    process in its own Python (stdin = the JSON, 30 minute timeout), fail with the
    process's error text if it crashed, and parse the line tagged `RESULT_JSON:`.
    """
    payload = {
        "shares": secrets,  # secret -> its two share names
        "randoms": randoms,  # fresh random input names
        "wires": [{"name": n, "op": op, "args": a} for n, op, a in c.wires],
        "outputs": c.outputs,
    }
    # copy of our environment plus PYTHONPATH so the driver can import VerifMSI
    env = dict(os.environ, PYTHONPATH=str(ORACLE_DIR))
    p = subprocess.run(
        [str(ORACLE_PY), str(DRIVER)],
        input=json.dumps(payload),  # sent on the driver's standard input
        capture_output=True,  # collect stdout and stderr
        text=True,  # as text, not bytes
        env=env,
        timeout=1800,  # seconds
    )
    if p.returncode != 0:  # the driver crashed
        raise RuntimeError(p.stderr[-2000:])  # show the last 2000 characters
    for line in p.stdout.splitlines():
        if line.startswith("RESULT_JSON:"):
            # slice off the tag so only the JSON text remains
            return json.loads(line[len("RESULT_JSON:") :])
    raise RuntimeError(p.stdout[-2000:])


def crosscheck(c, secrets, randoms):
    """Return (wires, disagreements, verifmsi nb_leak).

    Algorithm: compute our glitch and glitch-free verdicts per wire, ask VerifMSI for
    its two verdicts per wire, and record any wire where they differ (or where VerifMSI
    reported an error). `disagreements` is empty when the checkers fully agree.
    """
    free = free_of(secrets, randoms)
    g = check_glitch(c, secrets, free)  # our glitch-extended verdicts
    f = check_glitch_free(c, secrets, free)  # our glitch-free verdicts
    res = oracle(c, secrets, randoms)  # VerifMSI's verdicts
    bad = []  # list of disagreements
    for name, o in res["wires"].items():
        if "error" in o:
            bad.append((name, "oracle-error", o["error"]))
            continue
        if o["glitch"] != g[name]:
            bad.append((name, "glitch", g[name], o["glitch"]))
        if o["glitch_free"] != f[name]:
            bad.append((name, "glitch-free", f[name], o["glitch_free"]))
    return len(res["wires"]), bad, res["check_security"]["nb_leak"]


def main():
    """Run the whole probe on the four fixtures and print the results.

    Algorithm, step by step, for each fixture:
      1. Print the starting circuit's cost and verdicts.
      2. For each register mode (opaque, transparent): saturate in egglog, take egglog's
         own cheapest extraction ("U" for unconstrained) and describe it.
      3. List egglog's k-best extractions for every output, form every combination, and
         count how many contain a register and how many are glitch-secure.
      4. Run the glitch-constrained term extractor ("C") and describe its answer (or say
         none was found).
    Afterwards, unless disabled, cross-check every distinct circuit against VerifMSI and
    print the totals (probes compared and disagreements).
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=30, help="egglog k-best size")
    ap.add_argument("--k-terms", type=int, default=8, help="term extractor k")
    ap.add_argument("--no-oracle", action="store_true")
    args = ap.parse_args()
    use_oracle = not args.no_oracle and ORACLE_PY.exists()  # skip if not installed
    checked = []  # (label, circuit, secrets, randoms) to cross-check at the end

    for name, (roots, secrets, randoms) in fixtures().items():
        start = to_circuit(roots)
        print(f"\n== {name}\n   start          {describe(start, secrets, randoms)}")
        checked.append((name, start, secrets, randoms))
        for mode in ("opaque", "transparent"):
            eg, hs = saturate(roots, mode)
            # egglog's single cheapest extraction per output, parsed back into trees
            best = to_circuit([parse(str(eg.extract(h))) for h in hs])
            print(f"   {mode:<11} U  {describe(best, secrets, randoms)}")
            checked.append((f"{name} / {mode} / U", best, secrets, randoms))
            # egglog's own k-best frontier: does it contain any glitch-secure pair?
            variants = [eg.extract_multiple(h, args.k) for h in hs]  # k per output
            frontier = [
                to_circuit([parse(str(t)) for t in combo])
                # every combination: one variant chosen for each output
                for combo in itertools.product(*variants)
            ]
            # `c.count("reg") > 0` is True/False; summing counts the True ones
            n_regs = sum(c.count("reg") > 0 for c in frontier)
            secure = [c for c in frontier if not verdict(c, secrets, randoms)[0]]
            print(
                f"   {mode:<11} egglog k-best: {len(frontier)} circuits, "
                f"{n_regs} with a register, {len(secure)} glitch-secure"
            )
            # occurrence-aware, glitch-constrained term extraction
            classes, rts = export(eg, [f"o{i}" for i in range(len(hs))])
            free = free_of(secrets, randoms)
            picks = [  # the best term for each output (or None if none is secure)
                kbest(classes, rts[f"o{i}"], secrets, free, k=args.k_terms)[0]
                for i in range(len(hs))
            ]
            if not all(picks):  # any output without a secure term
                print(f"   {mode:<11} C  no glitch-secure term (k={args.k_terms})")
                continue
            c = term_circuit([p[1] for p in picks])  # p = (cost, term)
            print(f"   {mode:<11} C  {describe(c, secrets, randoms)}")
            for i, p in enumerate(picks):
                print(f"   {'':<14} o{i} = {show(p[1])}")
            checked.append((f"{name} / {mode} / C", c, secrets, randoms))

    if not use_oracle:
        print("\nVerifMSI not available: cross-check SKIPPED (not passed)")
        return
    seen, wires, bad = set(), 0, []  # distinct circuits, probes compared, problems
    print("\n== VerifMSI cross-check (exact, per probe) and checkSecurity(glitches)")
    for label, c, secrets, randoms in checked:
        key = tuple(c.wires)  # a hashable fingerprint of the circuit
        if key in seen:
            continue  # the same circuit was already checked under another label
        seen.add(key)
        n, b, nb_leak = crosscheck(c, secrets, randoms)
        wires += n
        bad += [(label, *x) for x in b]  # prefix each problem with the circuit label
        gl, _ = verdict(c, secrets, randoms)
        agree = (nb_leak > 0) == gl  # does VerifMSI's end-to-end verdict match ours?
        print(
            f"   {label:<44} checkSecurity leaks={nb_leak:<3} "
            f"{'agrees' if agree else 'DIFFERS (tps is incomplete)'}"
        )
    print(f"   {len(seen)} circuits, {wires} probes, {len(bad)} disagreements")
    for x in bad:
        print("   ", x)


if __name__ == "__main__":
    main()
