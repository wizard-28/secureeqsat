"""Reproduce the front-end table (paper Table V, experiments/frontend/RESULTS.md).

    uv run python experiments/frontend/table.py            # five programs, six runs
    uv run python experiments/frontend/table.py --with-or  # adds the OR-form majority

Purpose
-------
`findings/verify.py` re-runs every finding; this script is its step for the front-end
table, which had no reproduction step before. It compiles each program with `seqc.py`
(with `--crosscheck`, so VerifMSI checks every wire when it is installed), parses the
start, security-ignored and security-enforced costs, and checks every verification
line. It then compares each row with the numbers the paper reports and prints
`FRONT-END TABLE: ALL ROWS MATCH` only if every row matches and every check passed.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EX = HERE / "examples"

# (label, program file, masking policy, expected (start, ignored, enforced) costs,
#  expected verdicts (start, ignored)); the enforced circuit must always be secure.
ROWS = [
    ("ab^ac", "factor.sec", "refresh", (26, 11, 11), ("secure", "secure")),
    ("z&z, z=a^b", "square.sec", "refresh", (14, 11, 14), ("secure", "LEAKS")),
    ("mux", "mux.sec", "refresh", (27, 13, 13), ("secure", "secure")),
    ("full adder", "adder.sec", "refresh", (30, 24, 24), ("secure", "secure")),
    ("majority", "majority.sec", "refresh", (28, 22, 22), ("secure", "secure")),
    ("z&z, naive", "square.sec", "naive", (11, 11, 14), ("LEAKS", "LEAKS")),
]
OR_ROW = ("majority (OR)", "../large/majority_or.sec", "refresh", (65, 41, 41), None)

COST = re.compile(
    r"^\s*(start|security ignored|security enforced)\s+cost\s+(\d+).*?"
    r"\s(secure|LEAKS)"
)


def run(label, prog, policy, want_cost, want_verdict):
    """Compile one program; return (row text, ok)."""
    t = time.time()
    p = subprocess.run(
        [
            sys.executable,
            str(HERE / "seqc.py"),
            str(EX / prog),
            "--policy",
            policy,
            "--crosscheck",
        ],
        capture_output=True,
        text=True,
    )
    secs = time.time() - t
    out = p.stdout
    got = {}
    for line in out.splitlines():
        m = COST.match(line)
        if m:
            got[m.group(1)] = (int(m.group(2)), m.group(3))
    stages = ("start", "security ignored", "security enforced")
    ok = p.returncode == 0 and all(s in got for s in stages)
    checks = {
        "equal": "function equals the source on all inputs   ok" in out,
        "reconstruct": "lowered circuit reconstructs the outputs   ok" in out,
        "exact": "first-order check, in-house exact          0 leaking wires" in out,
    }
    oracle = re.search(r"VerifMSI cross-check\s+(.*)", out)
    oracle = oracle.group(1).strip() if oracle else "missing"
    ok = ok and all(checks.values()) and "disagreements" in oracle
    ok = ok and oracle.endswith(" 0 disagreements")
    if ok:
        costs = tuple(got[s][0] for s in stages)
        verdicts = (got["start"][1], got["security ignored"][1])
        ok = costs == want_cost and got["security enforced"][1] == "secure"
        if want_verdict is not None:
            ok = ok and verdicts == want_verdict
        cells = " -> ".join(f"{got[s][0]} {got[s][1]}" for s in stages)
    else:
        cells = "FAILED: " + (p.stderr[-300:] or out[-300:]).replace("\n", " | ")
    row = (
        f"  {label:<14} {policy:<8} {cells}   checks "
        f"{'ok' if all(checks.values()) else 'FAIL'}   VerifMSI {oracle}"
        f"   ({secs:.1f} s)   {'MATCH' if ok else 'MISMATCH'}"
    )
    return row, ok


def main():
    """Run every row, print them, and print the overall verdict line."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-or", action="store_true", help="add the OR-form majority")
    args = ap.parse_args()
    rows = ROWS + ([OR_ROW] if args.with_or else [])
    print(
        "front-end table: start -> security ignored -> security enforced "
        "(cost = gates + random bits)"
    )
    all_ok = True
    for r in rows:
        line, ok = run(*r)
        print(line, flush=True)
        all_ok &= ok
    print("FRONT-END TABLE: ALL ROWS MATCH" if all_ok else "FRONT-END TABLE: MISMATCH")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
