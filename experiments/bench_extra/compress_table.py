"""Summarise COMPRESS runs (two shares) from the stats.json files it writes.

    uv run python experiments/bench_extra/compress_table.py [work_dir [suffix]]

Purpose
-------
`make area` in the COMPRESS repository leaves one `stats.json` per (circuit, latency).
This prints, per program, every latency (AND gadgets, fresh random bits, area in GE,
solver seconds) and the latency with the smallest area, which is what the head-to-head
table reports. A latency with no `stats.json` was infeasible or did not finish.
"""

import json
import re
import sys
from pathlib import Path

WORK = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "h2h/work"
SUFFIX = sys.argv[2] if len(sys.argv) > 2 else ""  # "_sq": COMPRESS on seqc's logic
ORDER = [
    "factor", "square", "mux", "adder", "majority", "majority_or",
    "cmp2", "add2", "mul2", "mux4", "ascon_sbox", "present_sbox",
]  # fmt: skip


def gadgets(stats):
    """AND-type gadgets: every `MSKand*` and `MSKg4mul*` instance."""
    return sum(v for k, v in stats.items() if re.match(r"MSK(and|g4mul)", k))


def main():
    """Print the per-latency rows and the best (smallest-area) latency per program.

    Area is the synthesised design area (`area_ge`, no random-number generator), the
    figure the head-to-head table uses; `area_ge_wrng` adds COMPRESS's RNG estimate.
    """
    for name in ORDER:
        rows = []
        for f in sorted((WORK / "circuits").glob(f"{name}{SUFFIX}_d2_l*/stats.json")):
            st = json.loads(f.read_text())
            csv = WORK / f"{name}{SUFFIX}_area.csv"
            area = rng = None
            for ln in csv.read_text().splitlines()[1:]:
                c = ln.split(",")
                if int(c[1]) == st["Latency"]:
                    area, rng = float(c[3]), float(c[4])
            rows.append(
                (
                    st["Latency"],
                    gadgets(st),
                    st["RNG Bits"],
                    area,
                    rng,
                    st["solve_time"],
                )
            )
        for lat, g, r, a, w, t in rows:
            print(
                f"{name:13s} lat {lat} gadgets {g:2d} rnd {r:2d} "
                f"area {a:7.1f} GE (with RNG {w:7.1f}) {t:6.2f}s"
            )
        if rows:
            b = min(rows, key=lambda x: x[3])
            print(
                f"{name:13s} BEST lat {b[0]} gadgets {b[1]} rnd {b[2]} area {b[3]:.1f}"
            )
        else:
            print(f"{name:13s} no result")


if __name__ == "__main__":
    main()
