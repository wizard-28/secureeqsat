"""Baseline without an e-graph: how many AND gadgets does plain logic minimisation need?

    uv run python experiments/bench_extra/baseline_noegraph.py prog.sec ...

Purpose
-------
Reviewer question: do the savings need equality saturation at all? For each program,
count AND gates (= masked AND gadgets) in (a) the logic as written, with each shared
subexpression counted once, and (b) the result of Yosys + ABC (`abc -g AND,XOR`),
a standard area-oriented logic minimiser that knows nothing about masking.
Each masked AND gadget costs area and fresh randomness in every masking scheme, so the
AND count is the figure of merit; XOR/NOT counts are reported for completeness.

Limits: ABC's default script is not a multiplicative-complexity minimiser, so (b) is a
lower bar than a dedicated optimiser would set. Security is not considered.
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "frontend"))

from lang import parse  # noqa: E402

YOSYS = os.environ.get("YOSYS", str(Path.home() / "h2h/oss/oss-cad-suite/bin/yosys"))


def to_verilog(prog):
    """Unmasked combinational Verilog for `prog`, one assign per AST node (shared)."""
    names, lines = {}, []

    def w(node):
        if node[0] == "var":
            return node[1]
        if node not in names:
            k = node[0]
            if k == "not":
                e = f"~{w(node[1])}"
            else:
                op = {"and": "&", "xor": "^", "or": "|"}[k]
                e = f"{w(node[1])} {op} {w(node[2])}"
            names[node] = f"n{len(names)}"
            lines.append(f"  wire {names[node]} = {e};")
        return names[node]

    outs = [(n, w(a)) for n, a in prog.outputs]
    ports = ", ".join([*prog.inputs, *(n for n, _ in outs)])
    body = [f"module top({ports});"]
    body += [f"  input {i};" for i in prog.inputs]
    body += [f"  output {n};" for n, _ in outs]
    body += lines + [f"  assign {n} = {x};" for n, x in outs] + ["endmodule"]
    return "\n".join(body) + "\n", names


def written_ands(names):
    """AND gates as written (an `or` costs one AND, like `x ^ y ^ (x & y)`)."""
    return sum(1 for node in names if node[0] in ("and", "or"))


def abc_counts(verilog):
    """Run Yosys + ABC and return (ands, xors, nots) of the minimised netlist."""
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "top.v"
        f.write_text(verilog)
        script = f"read_verilog {f}; synth -top top; abc -g AND,XOR; opt_clean; stat"
        out = subprocess.run(
            [YOSYS, "-qq", "-p", script, "-p", "tee -o /dev/stdout stat"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    def n(cell):
        m = re.search(rf"\$_{cell}_\s*(\d+)|(\d+)\s+\$_{cell}_", out)
        return int(m.group(1) or m.group(2)) if m else 0

    return n("AND"), n("XOR"), n("NOT")


def main():
    """Print one line per program: ANDs as written vs after Yosys/ABC."""
    print(f"{'program':16s} ANDs(written)  ANDs(ABC)  XOR(ABC)  NOT(ABC)")
    for f in sys.argv[1:]:
        v, names = to_verilog(parse(Path(f).read_text()))
        a, x, nn = abc_counts(v)
        print(f"{Path(f).stem:16s} {written_ands(names):13d}  {a:9d}  {x:8d}  {nn:8d}")


if __name__ == "__main__":
    main()
