"""Cross-check the two circuit sets that were previously decided by our checker alone.

    uv run python experiments/oracle_crosscheck/extended.py

Purpose
-------
The paper's trust-boundary paragraph used to say that two sets were decided by the
in-house exact checker only: the 240 sampled k-best extractions of the two-gadget ISW
chain (finding F4) and the random PINI-built terms of the composition soundness test
(finding F11, section 3). This script sends every circuit in both sets to VerifMSI and
applies the same per-wire protocol as `crosscheck.py` (`compare`): our exact verdict
must equal VerifMSI's exact `independent` verdict on every wire, and VerifMSI's
certificate must never call a wire safe that either exact check calls leaking.

It regenerates both sets exactly as the original experiments do (same rules, same k,
same random seed), so the circuits checked are the ones the paper reports on.
"""

from __future__ import annotations

import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for sub in ("premise_test", "labeller", "egglog_port", "resharing", "composition"):
    sys.path.insert(0, str(ROOT / "experiments" / sub))
sys.path.insert(0, str(HERE))

from crosscheck import compare, oracle_available  # noqa: E402
from gadgets import lower, secret_groups, secrets_of  # noqa: E402
from kbest import build_chain, circuit_of  # noqa: E402
from labeller import DEFAULT_MAX_BITS  # noqa: E402
from port import FREE_CHAIN, SECRETS_CHAIN, make_egraph  # noqa: E402
from run_composition import bits_of, random_pini_term  # noqa: E402


def tally(name, results):
    """Print one summary line for a set and return its violation count."""
    circuits = len(results)
    wires = sum(r["n_wires"] for r in results)
    bad = sum(len(r["violations"]) for r in results)
    leaking = sum(1 for r in results if r["safe_wires"] < r["n_wires"])
    print(
        f"{name}: {circuits} circuits / {wires} wires cross-checked, "
        f"{leaking} circuits with a leaking wire, {bad} disagreements"
    )
    return bad


def kbest_set(k=40, iters=4):
    """The 240 sampled extractions of finding F4, each compared with VerifMSI."""
    eg = make_egraph("full")
    e0, e1 = build_chain(eg)
    eg.run(iters)
    v0 = eg.extract_multiple(e0, k)
    v1 = eg.extract_multiple(e1, k)
    randoms = [x for x in FREE_CHAIN if x not in {s[0] for s in SECRETS_CHAIN.values()}]
    out = []
    for a in v0:
        for b in v1:
            if a is None or b is None:
                continue
            out.append(compare(circuit_of(a, b), SECRETS_CHAIN, randoms))
    return out


def pini_set(n=300):
    """The random PINI-only terms of F11 section 3 (seed 19), compared with VerifMSI."""
    rng = random.Random(19)
    leaves = [("in", s) for s in "abd"]
    out = []
    for _ in range(n):
        t = random_pini_term(rng, 3, leaves)
        if t[0] == "in" or bits_of(t)[0] > DEFAULT_MAX_BITS:
            continue
        low = lower([t])
        out.append(compare(low.circ, secret_groups(secrets_of(t)), low.randoms))
    return out


def main():
    """Run both sets; exit non-zero on any disagreement or if VerifMSI is missing."""
    if not oracle_available():
        print("VerifMSI not available: SKIPPED (not a pass)")
        sys.exit(2)
    t = time.time()
    bad = tally("k-best chain extractions (F4)", kbest_set())
    bad += tally("random PINI-built terms (F11 sec. 3)", pini_set())
    print(f"total disagreements: {bad}  ({time.time() - t:.0f} s)")
    if bad == 0:
        print("EXTENDED CROSS-CHECK: AGREE")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
