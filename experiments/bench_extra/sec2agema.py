"""Write a seqc source program as an AGEMA input Verilog module.

    uv run python experiments/bench_extra/sec2agema.py prog.sec > prog.v

Purpose
-------
AGEMA reads an unmasked Verilog design whose inputs carry `(* AGEMA = "secure" *)`
attributes (plus a clock and reset). Its own flow then synthesises that design with
Yosys, so the logic is NOT kept as written: its front end optimises unmasked area.
The module is named after the program, with a clock and reset that the logic ignores.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "bench_extra"))

from baseline_noegraph import to_verilog  # noqa: E402
from lang import parse  # noqa: E402


def agema_verilog(source, name):
    """Return the annotated Verilog for the seqc program text `source`."""
    prog = parse(source)
    body, _ = to_verilog(prog)
    n_in, n_out = len(prog.inputs), len(prog.outputs)
    # AGEMA's parser expects bus-typed ports, as in its examples: one secure input bus
    # `din` and one output bus `dout`, with the program's names bound to their bits.
    lines = [f"module {name} (clk, rst, din, dout);"]
    lines += [
        '  (* AGEMA = "clock" *) input clk;',
        '  (* AGEMA = "reset" *) input rst;',
    ]
    lines += [f'  (* AGEMA = "secure" *) input [{n_in - 1}:0] din;']
    # AGEMA's parser finds no secure cells behind a single-bit output, so a lone output
    # is duplicated onto a second bit (same depth, no extra gadgets).
    width = max(n_out, 2)
    lines += [f"  output [{width - 1}:0] dout;"]
    # reuse the wire/assign lines of the plain module, dropping header and port lines
    keep = []
    for ln in body.splitlines()[1:-1]:
        t = ln.strip()
        if t.startswith(("input ", "output ")):
            continue
        if t.startswith("assign "):
            oname = t.split()[1]
            k = [n for n, _ in prog.outputs].index(oname)
            ln = ln.replace(f"assign {oname}", f"assign dout[{k}]")
            if n_out == 1:  # duplicate the lone output onto the second bit
                ln += "\n" + ln.replace("dout[0]", "dout[1]")
        for k, i in enumerate(prog.inputs):  # bind each name straight to its bit
            ln = re.sub(rf"\b{i}\b", f"din[{k}]", ln)
        keep.append(ln)
    return "\n".join(lines + keep + ["endmodule", ""])


def main():
    """Print the AGEMA input module for the file named on the command line."""
    path = Path(sys.argv[1])
    print(agema_verilog(path.read_text(), path.stem), end="")


if __name__ == "__main__":
    main()
