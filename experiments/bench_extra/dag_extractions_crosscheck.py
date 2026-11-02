"""Cross-check every one-node-per-class extraction of `square` with VerifMSI.

    uv run python experiments/bench_extra/dag_extractions_crosscheck.py

Purpose
-------
`dag_extractions.py` counts the acyclic extractions of `square` under four rule sets and
how many our checker calls secure. This sends the lowered circuit of every one of
them to VerifMSI and applies the per-wire protocol of `crosscheck.compare` (our exact
verdict must equal VerifMSI's exact `independent` verdict on every wire), so the counts
no longer rest on our checker alone.
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for sub in ("resharing", "premise_test", "oracle_crosscheck"):
    sys.path.insert(0, str(ROOT / "experiments" / sub))
sys.path.insert(0, str(HERE))

from crosscheck import compare, oracle_available  # noqa: E402
from dag_extractions import acyclic, assignments, build  # noqa: E402
from fixtures import FIXTURES  # noqa: E402
from gadgets import lower, secret_groups, secrets_of  # noqa: E402
from layer import export, saturate  # noqa: E402


def check(term):
    """VerifMSI-vs-ours comparison for one extracted term."""
    low = lower([term])
    r = compare(low.circ, secret_groups(secrets_of(term)), low.randoms)
    return r["safe_wires"] == r["n_wires"], r["n_wires"], len(r["violations"])


def main():
    """Cross-check every extraction under each rule set; print the totals."""
    if not oracle_available():
        print("VerifMSI not available: SKIPPED (not a pass)")
        sys.exit(2)
    term = FIXTURES["square"]
    for rules in [("R3",), ("R1", "R3"), ("R2", "R3"), ("R1", "R2", "R3")]:
        t0 = time.time()
        eg, _ = saturate(term, rules, 6)
        classes, root = export(eg)
        terms = [
            build(a, root, {}) for a in assignments(classes, root) if acyclic(a, root)
        ]
        with ThreadPoolExecutor(8) as pool:
            res = list(pool.map(check, terms))
        secure = sum(r[0] for r in res)
        wires = sum(r[1] for r in res)
        bad = sum(r[2] for r in res)
        print(
            f"{'+'.join(rules):9s} {len(terms):5d} extractions, {secure} secure, "
            f"{wires} wires, {bad} disagreements ({time.time() - t0:.0f} s)"
        )


if __name__ == "__main__":
    main()
