"""seqc: a source-to-netlist compiler over the SecureEqSat pipeline (design/0020).

    uv run python experiments/frontend/seqc.py experiments/frontend/examples/factor.sec
    uv run python experiments/frontend/seqc.py prog.sec --emit verilog --crosscheck

Stages: parse -> mask (policy) -> saturate (egglog, rules R1-R3) -> extract twice
(security ignored, security enforced) -> verify -> emit.

Scope is unchanged (first order, 2 shares, straight-line, glitch-free). The
emitted logic is combinational and is NOT glitch-extended secure.
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

POLICIES = ("refresh", "naive")
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
    """
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}")
    memo = {} if memo is None else memo
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
        gadget = ("isw", x, ("refresh", y) if policy == "refresh" else y)
        term = gadget if op == "and" else ("xor", ("xor", x, y), gadget)
    memo[ast] = term
    return term


def bundle(terms):
    """Several outputs as one root, in order (`out` adds no gates)."""
    root = terms[-1]
    for t in reversed(terms[:-1]):
        root = ("out", t, root)
    return root


# ---- pipeline -----------------------------------------------------------------


@dataclass
class Stage:
    term: tuple
    cost: int
    gates: int
    randoms: int
    leaks: list

    @property
    def secure(self):
        return not self.leaks


@dataclass
class Result:
    prog: object
    policy: str
    start: Stage
    unconstrained: Stage | None
    constrained: Stage | None
    classes: int = 0
    seconds: dict = field(default_factory=dict)
    info: dict = field(default_factory=dict)


def stage_of(term, ev):
    cost, leaks = ev(term)
    low = lower([term])
    return Stage(term, cost, low.circ.gate_count(), len(low.randoms), leaks or [])


def compile_program(
    prog, policy="refresh", rules=("R1", "R2", "R3"), k=8, iters=6
) -> Result:
    start_term = bundle([mask(ast, policy) for _, ast in prog.outputs])
    ev = Evaluator()
    t0 = time.time()
    eg, _ = saturate(start_term, rules, iters)
    classes, root = export(eg)
    t_sat = time.time() - t0
    res = Result(prog, policy, stage_of(start_term, ev), None, None, len(classes))
    res.seconds["saturate"] = t_sat
    for secure in (False, True):
        t0 = time.time()
        best, info = kbest(classes, root, k=k, secure=secure, evaluator=ev)
        res.seconds["constrained" if secure else "unconstrained"] = time.time() - t0
        res.info["constrained" if secure else "unconstrained"] = info
        stage = stage_of(best[1], ev) if best else None
        if secure:
            res.constrained = stage
        else:
            res.unconstrained = stage
    return res


# ---- verification ---------------------------------------------------------------


def _flatten(v):
    if isinstance(v, tuple):
        return [x for part in v for x in _flatten(part)]
    return [v]


def check_function(prog, term):
    """Term-level equivalence with the source, over every input assignment."""
    for bits in itertools.product((0, 1), repeat=len(prog.inputs)):
        env = dict(zip(prog.inputs, bits, strict=True))
        want = [evaluate(ast, env) for _, ast in prog.outputs]
        have = _flatten(value(term, {n: env[n] for n in secrets_of(term)}))
        if want != have:
            return False
    return True


def check_circuit(prog, term):
    """Reconstruct the outputs of the lowered circuit over every secret and
    every free assignment. Returns True/False, or None if too large to run."""
    names = secrets_of(term)
    low = lower([term])
    free = free_vars(names, low.randoms)
    if len(names) + len(free) > CHECK_BITS:
        return None
    outs = low.circ.outputs
    for svals in itertools.product((0, 1), repeat=len(names)):
        env = dict(zip(names, svals, strict=True))
        full = {n: env.get(n, 0) for n in prog.inputs}
        want = [evaluate(ast, full) for _, ast in prog.outputs]
        for fvals in itertools.product((0, 1), repeat=len(free)):
            ass = dict(zip(free, fvals, strict=True))
            for s in names:
                ass[f"{s}1"] = ass[f"{s}0"] ^ env[s]
            vals = eval_circuit(low.circ, ass)
            have = [vals[outs[i]] ^ vals[outs[i + 1]] for i in range(0, len(outs), 2)]
            if [int(v) for v in have] != want:
                return False
    return True


def crosscheck(term):
    """VerifMSI over every wire of the lowered circuit; None if unavailable."""
    from crosscheck import compare, oracle_available

    if not oracle_available():
        return None
    low = lower([term])
    out = compare(low.circ, secret_groups(secrets_of(term)), low.randoms)
    return out["n_wires"], out["violations"]


# ---- emitters ---------------------------------------------------------------------


def _port_maps(prog, low):
    """Readable names for the circuit's inputs and outputs."""
    rename = {}
    for n in prog.inputs:
        rename[f"{n}0"] = f"{n}_s0"
        rename[f"{n}1"] = f"{n}_s1"
    for i, r in enumerate(low.randoms, start=1):
        rename[r] = f"rnd{i}"
    return rename


def gate_list(prog, term):
    """The lowered circuit as ordered gates with readable wire names.

    Returns (inputs, gates, outputs): inputs is [name]; gates is
    [(name, op, args)] with op in and/xor/const; outputs is [(port, wire)].
    """
    low = lower([term])
    rename = _port_maps(prog, low)
    inputs, gates, n = [], [], 0
    for name, op, payload in low.circ.wires:
        if op == "input":
            rename.setdefault(name, name)
            inputs.append(rename[name])
        elif op == "const":
            rename[name] = "_one" if payload else "_zero"
            gates.append((rename[name], "const", (int(payload),)))
        else:
            n += 1
            rename[name] = f"_w{n}"
            a, b = payload
            gates.append((rename[name], op, (rename[a], rename[b])))
    outs = []
    for i, (oname, _) in enumerate(prog.outputs):
        outs.append((f"{oname}_s0", rename[low.circ.outputs[2 * i]]))
        outs.append((f"{oname}_s1", rename[low.circ.outputs[2 * i + 1]]))
    return inputs, gates, outs


def emit_netlist(prog, term):
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
    """Evaluate an emitted netlist; returns {output port: bit}."""
    vals, outs = {}, {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        op, *rest = line.split()
        if op == "input":
            vals[rest[0]] = assignment[rest[0]]
        elif op == "const":
            vals[rest[0]] = int(rest[1])
        elif op in ("and", "xor"):
            a, b = vals[rest[1]], vals[rest[2]]
            vals[rest[0]] = (a & b) if op == "and" else (a ^ b)
        elif op == "output":
            outs[rest[0]] = vals[rest[1]]
        else:
            raise ValueError(f"bad netlist line: {line!r}")
    return outs


VERILOG_KEYWORDS = {
    "module", "endmodule", "input", "output", "inout", "wire", "reg", "assign", "and",
    "or", "xor", "not", "nand", "nor", "xnor", "buf", "begin", "end", "if", "else",
    "always", "initial", "integer", "real", "time", "parameter", "function", "task",
    "case", "for", "while", "generate", "supply0", "supply1", "tri", "wand", "wor",
}  # fmt: skip


def emit_verilog(prog, term, module="masked"):
    inputs, gates, outs = gate_list(prog, term)
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
            lines.append(f"  wire {name} = 1'b{args[0]};")
        else:
            sym = "&" if op == "and" else "^"
            lines.append(f"  wire {name} = {args[0]} {sym} {args[1]};")
    lines += [f"  assign {port} = {wire};" for port, wire in outs]
    lines.append("endmodule")
    return "\n".join(lines) + "\n"


# ---- reporting --------------------------------------------------------------------


def fmt(stage):
    if stage is None:
        return "no secure realisation in the k-best frontier"
    verdict = "secure" if stage.secure else f"LEAKS ({len(stage.leaks)} wires)"
    return (
        f"cost {stage.cost:>3} = {stage.gates:>2}g + {stage.randoms}r  {verdict:<16} "
        f"{show(stage.term)}"
    )


def report(res, equiv, circuit_ok, oracle):
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
        return "\n".join(out)
    out.append("verify")
    out.append(f"  function equals the source on all inputs   {_ok(equiv)}")
    out.append(f"  lowered circuit reconstructs the outputs   {_ok(circuit_ok)}")
    leaks = len(res.constrained.leaks)
    out.append(f"  first-order check, in-house exact          {leaks} leaking wires")
    if oracle is None:
        out.append("  VerifMSI cross-check                       not run")
    else:
        n, bad = oracle
        out.append(
            f"  VerifMSI cross-check                       {n} wires, "
            f"{len(bad)} disagreements"
        )
    return "\n".join(out)


def _ok(flag):
    return "skipped (too many cases)" if flag is None else ("ok" if flag else "FAILED")


# ---- command line ------------------------------------------------------------------


def main(argv=None):
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
    term = res.constrained.term
    equiv = check_function(prog, term)
    circuit_ok = check_circuit(prog, term)
    oracle = crosscheck(term) if args.crosscheck else None
    print(report(res, equiv, circuit_ok, oracle))
    if args.crosscheck and oracle is None:
        print("note: VerifMSI is not available, so the cross-check was skipped")
    code = 0 if equiv and circuit_ok is not False and res.constrained.secure else 1
    if oracle is not None and oracle[1]:
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
