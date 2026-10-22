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

ORACLE_DIR = Path(os.environ.get("SECUREEQSAT_ORACLE_DIR", Path.home() / "oracles"))
ORACLE_PY = ORACLE_DIR / "venv" / "bin" / "python"
DRIVER = HERE / "glitch_driver.py"


# ---- a tiny expression tree shared by fixtures, egglog and circuits ----------


class N:
    def __init__(self, op, *args):
        self.op, self.args = op, args

    def __and__(self, o):
        return N("and", self, o)

    def __xor__(self, o):
        return N("xor", self, o)

    def reg(self):
        return N("reg", self)


def v(name):
    return N("var", name)


def to_circuit(roots):
    c = GCircuit()
    memo = {}

    def go(n):
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
    c0 = (x0 & y0) ^ r
    c1 = ((r ^ (x0 & y1)) ^ (x1 & y0)) ^ (x1 & y1)
    return c0, c1


def dom(x0, x1, y0, y1, z, regs=True):
    """DOM-indep AND; with regs, the cross terms are registered (VerifMSI's
    benchmarks/dom_and/generate_dom_and.py, 2 shares)."""
    t0 = (x0 & y1) ^ z
    t1 = (x1 & y0) ^ z
    if regs:
        t0, t1 = t0.reg(), t1.reg()
    return (x0 & y0) ^ t0, (x1 & y1) ^ t1


A = ["a0", "a1", "b0", "b1"]
SEC2 = {"a": ["a0", "a1"], "b": ["b0", "b1"]}
SEC3 = {**SEC2, "d": ["d0", "d1"]}


def fixtures():
    a0, a1, b0, b1, d0, d1 = (v(n) for n in ("a0", "a1", "b0", "b1", "d0", "d1"))
    r, z1, z2 = v("r"), v("z1"), v("z2")
    t = dom(a0, a1, b0, b1, z1)
    return {
        "isw (no registers)": (isw(a0, a1, b0, b1, r), SEC2, ["r"]),
        "dom (no registers)": (dom(a0, a1, b0, b1, z1, regs=False), SEC2, ["z1"]),
        "dom (registered)": (dom(a0, a1, b0, b1, z1), SEC2, ["z1"]),
        "dom chain (registered)": (dom(*t, d0, d1, z2), SEC3, ["z1", "z2"]),
    }


# ---- egglog ---------------------------------------------------------------------


class G(Expr):
    @classmethod
    def var(cls, name: StringLike) -> G: ...
    @classmethod
    def zero(cls) -> G: ...
    def __xor__(self, other: G) -> G: ...
    def __and__(self, other: G) -> G: ...
    def reg(self) -> G: ...


@ruleset
def boolean(a: G, b: G, c: G):
    yield rewrite(a ^ b).to(b ^ a)
    yield rewrite((a ^ b) ^ c).to(a ^ (b ^ c))
    yield rewrite(a ^ a).to(G.zero())
    yield rewrite(a ^ G.zero()).to(a)
    yield rewrite(a & b).to(b & a)
    yield rewrite(a & (b ^ c)).to((a & b) ^ (a & c))
    yield rewrite((a & b) ^ (a & c)).to(a & (b ^ c))


@ruleset
def transparent(a: G, b: G):
    yield rewrite(a.reg()).to(a)
    # seed a register on every gate operand; with reg(x) = x this only adds a
    # self-loop that extraction may take per occurrence (register insertion)
    yield rewrite(a ^ b).to(a.reg() ^ b)
    yield rewrite(a & b).to(a.reg() & b)


def to_egg(n):
    if n.op == "var":
        return G.var(n.args[0])
    if n.op == "reg":
        return to_egg(n.args[0]).reg()
    a, b = to_egg(n.args[0]), to_egg(n.args[1])
    return a & b if n.op == "and" else a ^ b


class _GNS:
    @staticmethod
    def var(name):
        return v(name)

    @staticmethod
    def zero():
        return N("const", 0)


def parse(text):
    tree = ast.parse(text)
    ns = {"G": _GNS}
    for stmt in tree.body[:-1]:
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
    eg = EGraph()
    handles = [eg.let(f"o{i}", to_egg(r)) for i, r in enumerate(roots)]
    sched = boolean if mode == "opaque" else boolean | transparent
    eg.run(sched * iters)
    return eg, handles


def show(t):
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
    return [sh[0] for sh in secrets.values()] + list(randoms)


def cost(c):
    return c.count("and", "xor") + c.count("reg")


def verdict(c, secrets, randoms):
    free = free_of(secrets, randoms)
    g = check_glitch(c, secrets, free)
    f = check_glitch_free(c, secrets, free)
    return (not all(g.values()), not all(f.values()))


def describe(c, secrets, randoms):
    gl, fl = verdict(c, secrets, randoms)
    return (
        f"{cost(c):>3} = {c.count('and', 'xor'):>2}g + {c.count('reg')}reg  "
        f"glitch-free: {'LEAKS' if fl else 'secure':6}  "
        f"glitch: {'LEAKS' if gl else 'secure'}"
    )


def oracle(c, secrets, randoms):
    payload = {
        "shares": secrets,
        "randoms": randoms,
        "wires": [{"name": n, "op": op, "args": a} for n, op, a in c.wires],
        "outputs": c.outputs,
    }
    env = dict(os.environ, PYTHONPATH=str(ORACLE_DIR))
    p = subprocess.run(
        [str(ORACLE_PY), str(DRIVER)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=1800,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-2000:])
    for line in p.stdout.splitlines():
        if line.startswith("RESULT_JSON:"):
            return json.loads(line[len("RESULT_JSON:") :])
    raise RuntimeError(p.stdout[-2000:])


def crosscheck(c, secrets, randoms):
    """Return (wires, disagreements, verifmsi nb_leak)."""
    free = free_of(secrets, randoms)
    g = check_glitch(c, secrets, free)
    f = check_glitch_free(c, secrets, free)
    res = oracle(c, secrets, randoms)
    bad = []
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=30, help="egglog k-best size")
    ap.add_argument("--k-terms", type=int, default=8, help="term extractor k")
    ap.add_argument("--no-oracle", action="store_true")
    args = ap.parse_args()
    use_oracle = not args.no_oracle and ORACLE_PY.exists()
    checked = []

    for name, (roots, secrets, randoms) in fixtures().items():
        start = to_circuit(roots)
        print(f"\n== {name}\n   start          {describe(start, secrets, randoms)}")
        checked.append((name, start, secrets, randoms))
        for mode in ("opaque", "transparent"):
            eg, hs = saturate(roots, mode)
            best = to_circuit([parse(str(eg.extract(h))) for h in hs])
            print(f"   {mode:<11} U  {describe(best, secrets, randoms)}")
            checked.append((f"{name} / {mode} / U", best, secrets, randoms))
            # egglog's own k-best frontier: does it contain any glitch-secure pair?
            variants = [eg.extract_multiple(h, args.k) for h in hs]
            frontier = [
                to_circuit([parse(str(t)) for t in combo])
                for combo in itertools.product(*variants)
            ]
            n_regs = sum(c.count("reg") > 0 for c in frontier)
            secure = [c for c in frontier if not verdict(c, secrets, randoms)[0]]
            print(
                f"   {mode:<11} egglog k-best: {len(frontier)} circuits, "
                f"{n_regs} with a register, {len(secure)} glitch-secure"
            )
            # occurrence-aware, glitch-constrained term extraction
            classes, rts = export(eg, [f"o{i}" for i in range(len(hs))])
            free = free_of(secrets, randoms)
            picks = [
                kbest(classes, rts[f"o{i}"], secrets, free, k=args.k_terms)[0]
                for i in range(len(hs))
            ]
            if not all(picks):
                print(f"   {mode:<11} C  no glitch-secure term (k={args.k_terms})")
                continue
            c = term_circuit([p[1] for p in picks])
            print(f"   {mode:<11} C  {describe(c, secrets, randoms)}")
            for i, p in enumerate(picks):
                print(f"   {'':<14} o{i} = {show(p[1])}")
            checked.append((f"{name} / {mode} / C", c, secrets, randoms))

    if not use_oracle:
        print("\nVerifMSI not available: cross-check SKIPPED (not passed)")
        return
    seen, wires, bad = set(), 0, []
    print("\n== VerifMSI cross-check (exact, per probe) and checkSecurity(glitches)")
    for label, c, secrets, randoms in checked:
        key = tuple(c.wires)
        if key in seen:
            continue
        seen.add(key)
        n, b, nb_leak = crosscheck(c, secrets, randoms)
        wires += n
        bad += [(label, *x) for x in b]
        gl, _ = verdict(c, secrets, randoms)
        agree = (nb_leak > 0) == gl
        print(
            f"   {label:<44} checkSecurity leaks={nb_leak:<3} "
            f"{'agrees' if agree else 'DIFFERS (tps is incomplete)'}"
        )
    print(f"   {len(seen)} circuits, {wires} probes, {len(bad)} disagreements")
    for x in bad:
        print("   ", x)


if __name__ == "__main__":
    main()
