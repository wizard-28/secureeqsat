"""Cross-check the emitted Verilog FILES of seqc with VerifMSI.

    uv run python experiments/bench_extra/verilog_crosscheck.py file.v [file.v ...]

Purpose
-------
`seqc --crosscheck` sends the in-memory netlist to VerifMSI before the Verilog is
written. This reads the Verilog file itself back (the `wire x = a ^ b;` and `assign`
subset seqc emits), rebuilds the circuit from the text, and compares our per-wire
verdicts with VerifMSI's exactly as `crosscheck.compare` does, so the file that is
shipped is the thing that is checked. First order, two shares, glitch-free model only.
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for sub in ("premise_test", "oracle_crosscheck"):
    sys.path.insert(0, str(ROOT / "experiments" / sub))

from crosscheck import compare, oracle_available  # noqa: E402
from masked import Circuit  # noqa: E402

WIRE = re.compile(r"^\s*wire\s+(\w+)\s*=\s*(.+);\s*$")
ASSIGN = re.compile(r"^\s*assign\s+(\w+)\s*=\s*(\w+)\s*;\s*$")


def parse_verilog(text):
    """Return (circuit, secrets, randoms) for an emitted seqc module."""
    c = Circuit()
    names = {}  # Verilog wire name -> circuit wire name
    inputs = re.findall(r"^\s*input\s+(\w+)", text, re.M)
    for i in inputs:
        names[i] = c.add_input(i)
    for line in text.splitlines():
        m = WIRE.match(line)
        if not m:
            continue
        out, expr = m.group(1), m.group(2).strip()
        if re.fullmatch(r"1'b[01]", expr):
            names[out] = c.add_const(expr.endswith("1"))
            continue
        parts = re.fullmatch(r"(\w+)\s*([&^])\s*(\w+)", expr)
        if not parts:
            raise ValueError(f"unsupported expression: {line.strip()}")
        a, op, b = parts.groups()
        names[out] = c.add_gate("and" if op == "&" else "xor", names[a], names[b])
    for line in text.splitlines():
        m = ASSIGN.match(line)
        if m:
            c.outputs.append(names[m.group(2)])
    bases = sorted({i[:-3] for i in inputs if i.endswith(("_s0", "_s1"))})
    secrets = {b: [f"{b}_s0", f"{b}_s1"] for b in bases}
    randoms = [i for i in inputs if i.startswith("rnd")]
    return c, secrets, randoms


def main():
    """Cross-check each file named on the command line."""
    if not oracle_available():
        print("VerifMSI not available: SKIPPED (not a pass)")
        sys.exit(2)
    for f in sys.argv[1:]:
        c, secrets, randoms = parse_verilog(Path(f).read_text())
        r = compare(c, secrets, randoms)
        leaks = r["n_wires"] - r["safe_wires"]
        print(
            f"{Path(f).stem:14s} {r['n_wires']:4d} wires, {leaks} leaking, "
            f"{len(r['violations'])} disagreements with VerifMSI"
        )


if __name__ == "__main__":
    main()
