"""Translate a seqc source program (.sec) into COMPRESS's circuit text format.

    uv run python experiments/bench_extra/sec2compress.py prog.sec > prog.txt

Purpose
-------
The head-to-head with COMPRESS (paper Sec. "Head-to-head") feeds it the Boolean logic
EXACTLY as written, because COMPRESS does not rewrite logic. This script is that
translation: one gate per AST node, shared subexpressions emitted once, `|` expanded
as `x ^ y ^ (x & y)` (the same desugaring seqc uses), and `~` as COMPRESS's `!`.

COMPRESS format: `INPUTS ...`, `OUTPUTS ...`, then `name = a + b` (XOR), `a & b`,
`!a`. Intermediate names are `t<n>`; outputs keep their source names.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "frontend"))

from lang import parse  # noqa: E402


def translate(source):
    """Return the COMPRESS circuit text for a seqc program given as a string."""
    prog = parse(source)
    lines = []  # gate lines, in dependency order
    memo = {}  # AST node -> the wire name that holds it
    counter = [0]

    def fresh():
        counter[0] += 1
        return f"t{counter[0]}"

    def wire(node, name=None):
        if node[0] == "var":
            return node[1]
        if node in memo and name is None:
            return memo[node]
        kind = node[0]
        out = name or fresh()
        if kind == "not":
            lines.append(f"{out} = !{wire(node[1])}")
        elif kind in ("and", "xor"):
            a, b = wire(node[1]), wire(node[2])
            lines.append(f"{out} = {a} {'&' if kind == 'and' else '+'} {b}")
        elif kind == "or":  # x | y = (x ^ y) ^ (x & y)
            a, b = wire(node[1]), wire(node[2])
            p, q = fresh(), fresh()
            lines.append(f"{p} = {a} + {b}")
            lines.append(f"{q} = {a} & {b}")
            lines.append(f"{out} = {p} + {q}")
        else:
            raise ValueError(kind)
        memo.setdefault(node, out)
        return out

    for oname, ast in prog.outputs:
        if ast[0] == "var":  # an output that is just an input: COMPRESS needs a gate
            lines.append(f"{oname} = {ast[1]} + {ast[1]} + {ast[1]}")
        else:
            wire(ast, name=oname)
    head = [
        "// + XOR",
        "// & AND",
        "// # XNOR",
        "",
        "INPUTS " + " ".join(prog.inputs),
        "OUTPUTS " + " ".join(n for n, _ in prog.outputs),
        "",
    ]
    return "\n".join(head + lines) + "\n"


def main():
    """Read the file named on the command line and print its COMPRESS form."""
    print(translate(Path(sys.argv[1]).read_text()), end="")


if __name__ == "__main__":
    main()
