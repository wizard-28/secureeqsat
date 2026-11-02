"""Simulate seqc's emitted Verilog with Icarus and compare it with the source program.

    uv run python experiments/bench_extra/sim_verilog.py prog.sec prog.v

Purpose
-------
The hardware flow was only synthesised for area. This closes part of that gap: it
generates a testbench that drives every input value with several random sharings and
random bits, and checks that the two output shares XOR to the value the source program
computes. It checks function in simulation, NOT security: the Verilog is combinational
and glitch-free-model only.
"""

import itertools
import os
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "frontend"))

from lang import evaluate, parse  # noqa: E402

BIN = Path(os.environ.get("H2H", Path.home() / "h2h")) / "oss/oss-cad-suite/bin"
SHARINGS = 8  # random sharings and random bits tried per input value


def testbench(prog, verilog):
    """Verilog testbench text; prints `PASS n` or `FAIL ...` and finishes."""
    text = Path(verilog).read_text()
    ports = re.findall(r"input\s+(\w+)", text)
    rnds = [p for p in ports if p.startswith("rnd")]
    rng = random.Random(1)
    lines = ["module tb;"]
    lines += [f"  reg {i}_s0, {i}_s1;" for i in prog.inputs]
    lines += [f"  reg {r};" for r in rnds]
    lines += [f"  wire {n}_s0, {n}_s1;" for n, _ in prog.outputs]
    conn = [f".{i}_s{k}({i}_s{k})" for i in prog.inputs for k in (0, 1)]
    conn += [f".{r}({r})" for r in rnds]
    conn += [f".{n}_s{k}({n}_s{k})" for n, _ in prog.outputs for k in (0, 1)]
    lines += [f"  masked dut({', '.join(conn)});", "  integer bad = 0, n = 0;"]
    lines += ["  initial begin"]
    for vals in itertools.product((0, 1), repeat=len(prog.inputs)):
        env = dict(zip(prog.inputs, vals, strict=True))
        want = {n: int(evaluate(a, env)) for n, a in prog.outputs}
        for _ in range(SHARINGS):
            for i in prog.inputs:
                r = rng.randint(0, 1)
                lines.append(f"    {i}_s0 = {r}; {i}_s1 = {r ^ env[i]};")
            lines += [f"    {r} = {rng.randint(0, 1)};" for r in rnds]
            lines.append("    #1; n = n + 1;")
            for name, w in want.items():
                lines.append(
                    f"    if (({name}_s0 ^ {name}_s1) !== 1'b{w}) bad = bad + 1;"
                )
    lines += [
        '    if (bad == 0) $display("PASS %0d", n); else $display("FAIL %0d", bad);'
    ]
    lines += ["    $finish;", "  end", "endmodule"]
    return "\n".join(lines)


def main():
    """Run the testbench for one program and print the simulator's verdict."""
    prog = parse(Path(sys.argv[1]).read_text())
    with tempfile.TemporaryDirectory() as tmp:
        tb = Path(tmp) / "tb.v"
        tb.write_text(testbench(prog, sys.argv[2]))
        vvp = Path(tmp) / "a.vvp"
        subprocess.run(
            [str(BIN / "iverilog"), "-g2012", "-o", str(vvp), str(tb), sys.argv[2]],
            check=True,
        )
        out = subprocess.run(
            [str(BIN / "vvp"), str(vvp)], capture_output=True, text=True
        ).stdout
    verdict = [x for x in out.splitlines() if x.startswith(("PASS", "FAIL"))]
    print(f"{Path(sys.argv[1]).stem:14s} {verdict[-1] if verdict else out[-200:]}")


if __name__ == "__main__":
    main()
