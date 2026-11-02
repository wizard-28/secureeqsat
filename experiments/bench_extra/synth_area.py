"""Synthesise seqc's emitted Verilog with Yosys + Nangate45 and report area in GE.

    uv run python experiments/bench_extra/synth_area.py <file>.v ...

Purpose
-------
Item "area for seqc's own output": the same flow COMPRESS uses (proc/opt/techmap, then
`abc -liberty` on the Nangate45 library, 1 GE = 0.798 um^2), so the numbers sit next to
COMPRESS's in the head-to-head table. The Verilog is glitch-free-model logic only.

Environment: `YOSYS` (default `~/h2h/oss/oss-cad-suite/bin/yosys`) and `NANGATE_LIB`
(default `~/h2h/compress/synthesis/nangate45-pdk/stdcells.lib`).
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

GE = 0.798  # area of NAND2_X1 in Nangate45, as in COMPRESS's summarize_design_area.py
YOSYS = os.environ.get("YOSYS", str(Path.home() / "h2h/oss/oss-cad-suite/bin/yosys"))
LIB = os.environ.get(
    "NANGATE_LIB",
    str(Path.home() / "h2h/compress/synthesis/nangate45-pdk/stdcells.lib"),
)


def area_ge(verilog, top="masked"):
    """Return `(area in GE, number of cells)` for the Verilog file `verilog`."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "area.json"
        script = (
            f"read_verilog {verilog}; hierarchy -check -top {top}; proc; opt; fsm; "
            f"opt; memory; opt; techmap; opt; dfflibmap -liberty {LIB}; "
            f"abc -liberty {LIB}; "
            f"clean; tee -o {out} stat -liberty {LIB} -json"
        )
        subprocess.run([YOSYS, "-qq", "-p", script], check=True, capture_output=True)
        d = json.loads(out.read_text())["design"]
    return float(d["area"]) / GE, int(d["num_cells"])


def main():
    """Print one `name  GE  cells` line per Verilog file given on the command line."""
    for f in sys.argv[1:]:
        ge, cells = area_ge(f)
        print(f"{Path(f).stem:14s} {ge:8.1f} GE {cells:5d} cells")


if __name__ == "__main__":
    main()
