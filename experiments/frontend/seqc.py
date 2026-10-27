"""seqc: a source-to-netlist compiler over the SecureEqSat pipeline (design/0020).

    uv run python experiments/frontend/seqc.py experiments/frontend/examples/factor.sec
    uv run python experiments/frontend/seqc.py prog.sec --emit verilog --crosscheck

Stages: parse -> mask (policy) -> saturate (egglog, rules R1-R3) -> extract twice
(security ignored, security enforced) -> verify -> emit.

Scope is unchanged (first order, 2 shares, straight-line, glitch-free). The
emitted logic is combinational and is NOT glitch-extended secure.

Purpose
-------
This is the compiler driver: it ties the front end (`lang.py`) to the existing
optimisation pipeline (the value-layer e-graph in `experiments/resharing`) and adds the
back end (netlist and Verilog emitters). It is the part of the project that makes it a
compiler in the usual sense: source text in, hardware-ready code out, with the security
check built into the optimisation.

A worked run on `factor.sec` (`out y = a&b ^ a&d`):
  mask       refresh every AND's second operand       cost 26
  optimise   security ignored: cost 11, secure (factored: one gadget instead of two)
  verify     equals the source on all inputs, 0 leaking wires, VerifMSI agrees
  emit       a netlist or Verilog module with `a_s0`, `a_s1`, ... ports
"""

import argparse
import itertools
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for sub in ("frontend", "resharing", "labeller", "premise_test", "oracle_crosscheck"):
    sys.path.insert(0, str(ROOT / "experiments" / sub))

from extract import Evaluator, kbest  # noqa: E402
from gadgets import (  # noqa: E402
    free_vars,
    lower,
    secret_groups,
    secrets_of,
    show,
    value,
)
from lang import ParseError, evaluate, parse  # noqa: E402
from layer import export, saturate  # noqa: E402
from masked import evaluate as eval_circuit  # noqa: E402

POLICIES = ("refresh", "naive")  # the two masking policies
BIG_PROGRAM_ANDS = 4  # term-based extraction slows down sharply beyond this
CHECK_BITS = 22  # exhaustive reconstruction check is skipped above 2**22 cases


# ---- masking pass -----------------------------------------------------------


def mask(ast, policy="refresh", memo=None):
    """Turn an AST into a shared-value term.

    policy "refresh": every AND gadget gets a refreshed second operand, so its
    two operand sharings are independent and the gadget is secure by
    construction (the conservative choice a compiler would make; the optimiser
    removes the refreshes that turn out to be redundant).
    policy "naive": no refresh; can leak when the operands are correlated.

    Algorithm, step by step (recursive over the tree):
      1. A variable becomes the input term `("in", name)`.
      2. `~x` and `x ^ y` become the share-wise `not` and `xor` of the masked operands.
      3. `x & y` becomes an ISW gadget; with the "refresh" policy the second operand
         is wrapped in `refresh`.
      4. `x | y` is rewritten as `x ^ y ^ (x & y)`: an XOR of the two operands and the
         gadget (there is no OR gadget).
      5. A memo table keyed by the AST remembers each result, so a sub-expression used
         twice masks to the SAME term (and later lowers to one set of wires).
    """
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}")
    memo = {} if memo is None else memo  # AST -> masked term, for sharing
    if ast in memo:
        return memo[ast]
    op = ast[0]
    if op == "var":
        term = ("in", ast[1])
    elif op == "not":
        term = ("not", mask(ast[1], policy, memo))
    elif op == "xor":
        term = ("xor", mask(ast[1], policy, memo), mask(ast[2], policy, memo))
    else:  # and, or
        x, y = mask(ast[1], policy, memo), mask(ast[2], policy, memo)
        # ISW AND; under the "refresh" policy the second operand is refreshed first
        gadget = ("isw", x, ("refresh", y) if policy == "refresh" else y)
        # and: just the gadget; or: x ^ y ^ (x & y), built as xor(xor(x, y), gadget)
        term = gadget if op == "and" else ("xor", ("xor", x, y), gadget)
    memo[ast] = term
    return term


def bundle(terms):
    """Several outputs as one root, in order (`out` adds no gates).

    Algorithm: start with the last term and wrap each earlier term around it from the
    back, giving `out(t0, out(t1, ... tn))`. A single output is returned unchanged.
    """
    root = terms[-1]  # the innermost term
    for t in reversed(terms[:-1]):  # every earlier term, last to first
        root = ("out", t, root)
    return root


# ---- pipeline -----------------------------------------------------------------


@dataclass
class Stage:
    """One candidate circuit at some stage of the pipeline.

    Attributes:
        term: the shared-value term, e.g. ("isw", ("in", "a"), ("in", "b")).
        cost: gates + random bits of its lowered circuit.
        gates: number of gates.
        randoms: number of fresh random bits.
        leaks: names of leaking wires ([] means secure).
    """

    term: tuple
    cost: int
    gates: int
    randoms: int
    leaks: list

    @property
    def secure(self):
        """True iff the lowered circuit has no leaking wire."""
        return not self.leaks


@dataclass
class Result:
    """Everything `compile_program` produces.

    Attributes:
        prog: the parsed program.
        policy: the masking policy used.
        start: the masked starting circuit.
        unconstrained: the cheapest circuit found ignoring security (may leak), or None.
        constrained: the cheapest SECURE circuit found, or None if none exists.
        classes: number of e-classes after saturation.
        seconds: timings, e.g. {"saturate": 0.3, "constrained": 1.2}.
        info: extraction statistics per mode.
    """

    prog: object
    policy: str
    start: Stage
    unconstrained: Stage | None
    constrained: Stage | None
    classes: int = 0
    seconds: dict = field(default_factory=dict)
    info: dict = field(default_factory=dict)


def stage_of(term, ev):
    """Evaluate `term` with `ev` (an `Evaluator`) and package it as a `Stage`.

    `ev(term)` returns `(cost, leaking_wires)`. The term is also lowered to count its
    gates and random bits. `leaks or []` turns a None (too large to check) into [].
    """
    cost, leaks = ev(term)
    low = lower([term])
    return Stage(term, cost, low.circ.gate_count(), len(low.randoms), leaks or [])


def compile_program(
    prog, policy="refresh", rules=("R1", "R2", "R3"), k=8, iters=6
) -> Result:
    """Run the pipeline on a parsed program and return the `Result`.

    Algorithm, step by step:
      1. MASK every output AST and bundle them into one root term (the start circuit).
      2. SATURATE that term in egglog with the rule classes `rules` for `iters` rounds
         and export the e-graph.
      3. EXTRACT twice with the k-best extractor: once ignoring security and once with
         the leak cut (only secure terms admitted), timing each.
      4. Package each answer as a `Stage` (term, cost, gates, randoms, leaks), or
         None if no term qualified.
    """
    start_term = bundle([mask(ast, policy) for _, ast in prog.outputs])
    ev = Evaluator()  # one shared cache for all the evaluations below
    t0 = time.time()
    eg, _ = saturate(start_term, rules, iters)
    classes, root = export(eg)
    t_sat = time.time() - t0  # seconds spent saturating and exporting
    res = Result(prog, policy, stage_of(start_term, ev), None, None, len(classes))
    res.seconds["saturate"] = t_sat
    for secure in (False, True):  # first ignore security, then enforce it
        t0 = time.time()
        best, info = kbest(classes, root, k=k, secure=secure, evaluator=ev)
        res.seconds["constrained" if secure else "unconstrained"] = time.time() - t0
        res.info["constrained" if secure else "unconstrained"] = info
        # `best` is (cost, term) or None; take the term and evaluate it as a Stage
        stage = stage_of(best[1], ev) if best else None
        if secure:
            res.constrained = stage
        else:
            res.unconstrained = stage
    return res


# ---- verification ---------------------------------------------------------------


def _flatten(v):
    """Flatten nested tuples of values into one flat list.

    `value()` returns a pair for an `out` bundle (and nested pairs for several outputs);
    this turns `(1, (0, 1))` into `[1, 0, 1]` so it can be compared with a list of
    source outputs.
    """
    if isinstance(v, tuple):
        return [x for part in v for x in _flatten(part)]
    return [v]


def check_function(prog, term):
    """Term-level equivalence with the source, over every input assignment.

    Algorithm: for every combination of 0/1 for the program's inputs, evaluate the
    source outputs (`want`) and the masked term's reconstructed value (`have`, using
    only the secrets the term reads) and compare. Any difference means the optimiser
    changed the function.
    """
    for bits in itertools.product((0, 1), repeat=len(prog.inputs)):
        env = dict(zip(prog.inputs, bits, strict=True))  # e.g. {"a": 1, "b": 0}
        want = [evaluate(ast, env) for _, ast in prog.outputs]  # source outputs
        have = _flatten(value(term, {n: env[n] for n in secrets_of(term)}))
        if want != have:
            return False
    return True


def check_circuit(prog, term):
    """Reconstruct the outputs of the lowered circuit over every secret and
    every free assignment. Returns True/False, or None if too large to run.

    Algorithm, step by step:
      1. Lower the term to a real circuit; if the number of secrets plus free bits
         exceeds `CHECK_BITS`, give up (None).
      2. For every secret value, compute the source outputs (`want`; unused inputs take
         the value 0).
      3. For every assignment of the free bits, set the other shares to share0 ^ secret,
         run the circuit, and XOR each output's two shares (`have`).
      4. If `have` ever differs from `want`, return False; otherwise True.
    """
    names = secrets_of(term)  # the secrets the circuit actually reads
    low = lower([term])
    free = free_vars(names, low.randoms)  # share 0 of each secret + the randoms
    if len(names) + len(free) > CHECK_BITS:
        return None  # too many cases to enumerate
    outs = low.circ.outputs  # two share wires per source output
    for svals in itertools.product((0, 1), repeat=len(names)):
        env = dict(zip(names, svals, strict=True))
        # inputs the term never reads are irrelevant to the outputs: use 0 for them
        full = {n: env.get(n, 0) for n in prog.inputs}
        want = [evaluate(ast, full) for _, ast in prog.outputs]
        for fvals in itertools.product((0, 1), repeat=len(free)):
            ass = dict(zip(free, fvals, strict=True))
            for s in names:
                ass[f"{s}1"] = ass[f"{s}0"] ^ env[s]  # share 1 = share 0 ^ secret
            vals = eval_circuit(low.circ, ass)
            # outputs come in (share0, share1) pairs: XOR each pair to get the value
            have = [vals[outs[i]] ^ vals[outs[i + 1]] for i in range(0, len(outs), 2)]
            if [int(v) for v in have] != want:  # `int` turns True/False into 1/0
                return False
    return True


def crosscheck(term):
    """VerifMSI over every wire of the lowered circuit; None if unavailable.

    Returns `(number of wires compared, list of disagreements)`; the list is empty when
    VerifMSI and our checkers agree on every wire.
    """
    from crosscheck import compare, oracle_available

    if not oracle_available():
        return None
    low = lower([term])
    out = compare(low.circ, secret_groups(secrets_of(term)), low.randoms)
    return out["n_wires"], out["violations"]


# ---- emitters ---------------------------------------------------------------------


def _port_maps(prog, low):
    """Readable names for the circuit's inputs and outputs.

    Returns `{internal name: readable name}`: the share wires `a0`, `a1` become `a_s0`,
    `a_s1`, and the randoms `r1`, `r2` become `rnd1`, `rnd2`.
    """
    rename = {}
    for n in prog.inputs:
        rename[f"{n}0"] = f"{n}_s0"  # share 0 of input n
        rename[f"{n}1"] = f"{n}_s1"  # share 1 of input n
    for i, r in enumerate(low.randoms, start=1):  # numbering starts at 1
        rename[r] = f"rnd{i}"
    return rename


def gate_list(prog, term):
    """The lowered circuit as ordered gates with readable wire names.

    Returns (inputs, gates, outputs): inputs is [name]; gates is
    [(name, op, args)] with op in and/xor/const; outputs is [(port, wire)].

    Algorithm, step by step:
      1. Lower the term and build the rename table for inputs and randoms.
      2. Walk the wires in order. An input keeps its readable name and is listed as an
         input. A constant becomes `_one` or `_zero`. Every gate gets a fresh name
         `_w1`, `_w2`, ... and its operands are renamed.
      3. Outputs: each source output `y` has two share wires; they become the ports
         `y_s0` and `y_s1`.
    """
    low = lower([term])
    rename = _port_maps(prog, low)
    inputs, gates, n = [], [], 0  # n counts gates, to make names _w1, _w2, ...
    for name, op, payload in low.circ.wires:
        if op == "input":
            rename.setdefault(name, name)  # keep a name that has no readable form
            inputs.append(rename[name])
        elif op == "const":
            rename[name] = "_one" if payload else "_zero"
            gates.append((rename[name], "const", (int(payload),)))
        else:
            n += 1
            rename[name] = f"_w{n}"
            a, b = payload  # the two operand wires (internal names)
            gates.append((rename[name], op, (rename[a], rename[b])))
    outs = []
    for i, (oname, _) in enumerate(prog.outputs):
        # output i owns circuit outputs 2*i (share 0) and 2*i + 1 (share 1)
        outs.append((f"{oname}_s0", rename[low.circ.outputs[2 * i]]))
        outs.append((f"{oname}_s1", rename[low.circ.outputs[2 * i + 1]]))
    return inputs, gates, outs


def emit_netlist(prog, term):
    """Render the circuit as a plain-text netlist (a header, then one line per item).

    Lines are `input NAME`, `and|xor|const NAME ARGS...` and `output PORT WIRE`.
    """
    inputs, gates, outs = gate_list(prog, term)
    lines = [
        "# seqc netlist, 1-bit wires, first-order 2-share masking (glitch-free model)",
        "# input shares are <name>_s0, <name>_s1; fresh random bits are rnd<i>",
    ]
    lines += [f"input {n}" for n in inputs]
    for name, op, args in gates:
        lines.append(f"{op} {name} {' '.join(str(a) for a in args)}")
    lines += [f"output {port} {wire}" for port, wire in outs]
    return "\n".join(lines) + "\n"


def run_netlist(text, assignment):
    """Evaluate an emitted netlist; returns {output port: bit}.

    Algorithm: read the text line by line, skipping blank lines and comments. `input`
    takes its value from `assignment`; `const` stores its literal; `and`/`xor` combine
    two earlier values with `&` / `^`; `output` records a wire's value under its port
    name. Used by the tests to confirm the emitted code computes the right function.
    """
    vals, outs = {}, {}  # wire name -> bit; output port -> bit
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        op, *rest = line.split()  # first word is the operation; `*rest` the others
        if op == "input":
            vals[rest[0]] = assignment[rest[0]]
        elif op == "const":
            vals[rest[0]] = int(rest[1])
        elif op in ("and", "xor"):
            a, b = vals[rest[1]], vals[rest[2]]  # the two operand values
            vals[rest[0]] = (a & b) if op == "and" else (a ^ b)
        elif op == "output":
            outs[rest[0]] = vals[rest[1]]
        else:
            raise ValueError(f"bad netlist line: {line!r}")
    return outs


# Words that cannot be used as Verilog identifiers (a program variable called `wire`
# would produce an invalid port name `wire_s0`'s base). The `# fmt: skip` keeps the
# formatter from re-flowing this table.
VERILOG_KEYWORDS = {
    "module", "endmodule", "input", "output", "inout", "wire", "reg", "assign", "and",
    "or", "xor", "not", "nand", "nor", "xnor", "buf", "begin", "end", "if", "else",
    "always", "initial", "integer", "real", "time", "parameter", "function", "task",
    "case", "for", "while", "generate", "supply0", "supply1", "tri", "wand", "wor",
}  # fmt: skip


def emit_verilog(prog, term, module="masked"):
    """Render the circuit as a Verilog module (combinational, glitch-free model only).

    Algorithm, step by step:
      1. Build the gate list and reject source names that are Verilog keywords (the
         base name is recovered by stripping the `_s0`/`_s1` suffix).
      2. Write a comment header that states the model and its limits, then the module
         header with one `input` port per input and one `output` port per output share.
      3. Emit one `wire` per gate (`a ^ b`, `a & b`, or a 1-bit literal for a constant).
      4. Emit one `assign` per output port and close the module.
    The header warns that the logic is NOT glitch-extended secure.
    """
    inputs, gates, outs = gate_list(prog, term)
    # names used in ports with the `_s0`/`_s1` suffix removed; compare with keywords
    clash = sorted(
        {n.rsplit("_s", 1)[0] for n in inputs + [p for p, _ in outs]} & VERILOG_KEYWORDS
    )
    if clash:
        raise ValueError(f"names that are Verilog keywords: {', '.join(clash)}")
    ports = [f"    input  {n}" for n in inputs]
    ports += [f"    output {p}" for p, _ in outs]
    lines = [
        "// Generated by seqc (design/0020).",
        "// Model: first-order probing security, 2 shares, GLITCH-FREE.",
        "// This is plain combinational logic: it is NOT glitch-extended secure",
        "// (design/0017, 0018). Input shares are <name>_s0, <name>_s1; the rnd<i>",
        "// inputs must be fresh uniform random bits.",
        f"module {module} (",
        ",\n".join(ports),
        ");",
    ]
    for name, op, args in gates:
        if op == "const":
            lines.append(f"  wire {name} = 1'b{args[0]};")  # a 1-bit literal
        else:
            sym = "&" if op == "and" else "^"
            lines.append(f"  wire {name} = {args[0]} {sym} {args[1]};")
    lines += [f"  assign {port} = {wire};" for port, wire in outs]
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


# ---- reporting --------------------------------------------------------------------


def fmt(stage):
    """One-line summary of a `Stage`: cost, gate/random split, verdict, the term."""
    if stage is None:
        return "no secure realisation in the k-best frontier"
    verdict = "secure" if stage.secure else f"LEAKS ({len(stage.leaks)} wires)"
    return (
        f"cost {stage.cost:>3} = {stage.gates:>2}g + {stage.randoms}r  {verdict:<16} "
        f"{show(stage.term)}"
    )


def report(res, equiv, circuit_ok, oracle):
    """Build the text report printed by the command line.

    Args:
        res: the `Result` from `compile_program`.
        equiv: result of `check_function` (True/False).
        circuit_ok: result of `check_circuit` (True/False/None).
        oracle: result of `crosscheck` ((wires, violations) or None).

    Sections: the program summary, masking and optimisation results (with a note when
    the cheapest circuit leaks and security costs extra), then a `verify` block.
    """
    p = res.prog
    out = [
        f"program  {len(p.inputs)} inputs, {len(p.outputs)} outputs, "
        f"{p.n_and()} AND, {p.n_xor()} XOR in the source",
        f"mask     policy={res.policy}",
        f"  start                    {fmt(res.start)}",
        f"optimise {res.classes} e-classes after saturation "
        f"({res.seconds['saturate']:.2f}s)",
        f"  security ignored         {fmt(res.unconstrained)}",
        f"  security enforced        {fmt(res.constrained)}",
    ]
    # when the cheapest circuit leaks, say how much the security requirement costs
    if (
        res.unconstrained
        and res.constrained
        and not res.unconstrained.secure
        and res.unconstrained.cost < res.constrained.cost
    ):
        diff = res.constrained.cost - res.unconstrained.cost
        out.append(
            f"  -> the cheapest equivalent circuit leaks; security costs {diff} here"
        )
    if res.constrained is None:
        return "\n".join(out)  # nothing secure was found: no verify block
    out.append("verify")
    out.append(f"  function equals the source on all inputs   {_ok(equiv)}")
    out.append(f"  lowered circuit reconstructs the outputs   {_ok(circuit_ok)}")
    leaks = len(res.constrained.leaks)
    out.append(f"  first-order check, in-house exact          {leaks} leaking wires")
    if oracle is None:
        out.append("  VerifMSI cross-check                       not run")
    else:
        n, bad = oracle  # n wires compared, bad = list of disagreements
        out.append(
            f"  VerifMSI cross-check                       {n} wires, "
            f"{len(bad)} disagreements"
        )
    return "\n".join(out)


def _ok(flag):
    """Text for a check result: None -> skipped, True -> ok, False -> FAILED."""
    return "skipped (too many cases)" if flag is None else ("ok" if flag else "FAILED")


# ---- command line ------------------------------------------------------------------


def main(argv=None):
    """Command-line entry point. Returns the process exit code.

    Exit codes: 0 = compiled and verified, 1 = a check failed (or no secure circuit was
    found), 2 = the source did not parse.

    Algorithm, step by step:
      1. Read the source from a file or standard input and parse it (exit 2 on error).
      2. Warn if the program has many ANDs, since term-based extraction slows down.
      3. Run `compile_program`; if no secure circuit exists, report and exit 1.
      4. Verify the chosen circuit: function equals the source, lowered circuit
         reconstructs the outputs, and (with `--crosscheck`) VerifMSI agrees.
      5. Print the report; optionally emit a netlist or Verilog to stdout or a file.
    """
    # the description shown by --help is the first paragraph of the module docstring
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("source", help="program file, or - for standard input")
    ap.add_argument("--policy", choices=POLICIES, default="refresh")
    ap.add_argument("--emit", choices=("none", "netlist", "verilog"), default="none")
    ap.add_argument("--out", help="write the emitted code here instead of stdout")
    ap.add_argument("--module", default="masked", help="Verilog module name")
    ap.add_argument("--k", type=int, default=8, help="k-best frontier width")
    ap.add_argument("--iters", type=int, default=6, help="saturation iterations")
    ap.add_argument("--crosscheck", action="store_true", help="also run VerifMSI")
    args = ap.parse_args(argv)

    text = sys.stdin.read() if args.source == "-" else Path(args.source).read_text()
    try:
        prog = parse(text)
    except ParseError as e:
        print(f"{args.source}: {e}", file=sys.stderr)
        return 2
    if prog.n_and() > BIG_PROGRAM_ANDS:
        print(
            f"warning: {prog.n_and()} AND operations; term-based extraction slows "
            "down sharply beyond a few gadgets (design/0016)",
            file=sys.stderr,
        )
    res = compile_program(prog, args.policy, k=args.k, iters=args.iters)
    if res.constrained is None:
        print(report(res, None, None, None))
        print("error: no secure realisation found; try a larger --k", file=sys.stderr)
        return 1
    term = res.constrained.term  # the chosen (secure) circuit
    equiv = check_function(prog, term)
    circuit_ok = check_circuit(prog, term)  # True/False, or None if too large
    oracle = crosscheck(term) if args.crosscheck else None
    print(report(res, equiv, circuit_ok, oracle))
    if args.crosscheck and oracle is None:
        print("note: VerifMSI is not available, so the cross-check was skipped")
    # success needs: equal to the source, no reconstruction failure, and secure
    code = 0 if equiv and circuit_ok is not False and res.constrained.secure else 1
    if oracle is not None and oracle[1]:  # any VerifMSI disagreement is a failure
        code = 1
    if args.emit != "none":
        code_text = (
            emit_netlist(prog, term)
            if args.emit == "netlist"
            else emit_verilog(prog, term, args.module)
        )
        if args.out:
            Path(args.out).write_text(code_text)
            print(f"emitted  {args.emit} -> {args.out}")
        else:
            print(f"\n{code_text}", end="")
    return code


if __name__ == "__main__":
    sys.exit(main())
