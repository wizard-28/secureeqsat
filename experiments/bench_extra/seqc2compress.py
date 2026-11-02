"""Feed seqc's chosen Boolean structure to COMPRESS ("COMPRESS on seqc's logic").

    uv run python experiments/bench_extra/seqc2compress.py prog.sec > p.txt

Purpose
-------
COMPRESS keeps the logic as written, so to ask whether seqc's savings carry over into
a glitch-robust flow, hand COMPRESS the Boolean structure seqc chose. This compiles the
program, takes the security-enforced term, and writes it in COMPRESS's circuit format:
each gadget (`isw`, `dom`, `hpc1`) becomes an AND, `refresh` becomes the identity
(COMPRESS inserts its own refreshing), and shared subterms are emitted once.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "frontend"))

import seqc  # noqa: E402
from lang import parse  # noqa: E402

GADGETS = ("isw", "dom", "hpc1")


def to_compress(prog, term):
    """COMPRESS circuit text for `term`, whose `out(...)` spine lists the outputs."""
    lines, memo, count = [], {}, [0]
    outs = []

    def wire(t, name=None):
        if t[0] == "in":
            return t[1]
        if t[0] == "refresh":
            return wire(t[1], name)
        if t in memo and name is None:
            return memo[t]
        count[0] += 1
        name = name or f"t{count[0]}"
        if t[0] == "not":
            lines.append(f"{name} = !{wire(t[1])}")
        else:
            a, b = wire(t[1]), wire(t[2])
            op = "&" if t[0] in GADGETS else "+"
            lines.append(f"{name} = {a} {op} {b}")
        memo.setdefault(t, name)
        return name

    spine = term
    while spine[0] == "out":
        outs.append(spine[1])
        spine = spine[2]
    outs.append(spine)
    names = [n for n, _ in prog.outputs]
    for n, t in zip(names, outs, strict=True):
        wire(t, name=n)
    head = ["// + XOR", "// & AND", "// # XNOR", ""]
    head += ["INPUTS " + " ".join(prog.inputs), "OUTPUTS " + " ".join(names), ""]
    return "\n".join(head + lines) + "\n"


def main():
    """Compile the program and print COMPRESS's input for its secure optimum."""
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--iters", type=int, default=6)
    a = ap.parse_args()
    prog = parse(Path(a.source).read_text())
    res = seqc.compile_program(prog, k=a.k, iters=a.iters)
    print(to_compress(prog, res.constrained.term), end="")


if __name__ == "__main__":
    main()
