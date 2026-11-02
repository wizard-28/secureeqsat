"""Send every circuit of egglog's glitch k-best frontier to VerifMSI.

    uv run python experiments/bench_extra/glitch_frontier_crosscheck.py

Purpose
-------
The paper says none of egglog's 784 cheapest candidates for a registered DOM chain is
glitch-secure. That verdict used our glitch checker; VerifMSI had cross-checked only 10
circuits (167 probes). This regenerates the 784 circuits exactly as
`glitch_probe/probe.py` does (transparent registers, k = 30 per output) and compares our
glitch and glitch-free verdicts with VerifMSI's on every probe of every circuit.
"""

import itertools
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ("glitch_probe", "premise_test"):
    sys.path.insert(0, str(ROOT / "experiments" / sub))

import probe  # noqa: E402

K = 30  # egglog k-best size per output, as in probe.py's default


def frontier():
    """All combinations of egglog's k-best terms for the registered DOM chain."""
    roots, secrets, randoms = probe.fixtures()["dom chain (registered)"]
    eg, hs = probe.saturate(roots, "transparent")
    variants = [eg.extract_multiple(h, K) for h in hs]
    circuits = [
        probe.to_circuit([probe.parse(str(t)) for t in combo])
        for combo in itertools.product(*variants)
    ]
    return circuits, secrets, randoms


def main():
    """Cross-check each distinct circuit of the frontier and print the totals."""
    t0 = time.time()
    circuits, secrets, randoms = frontier()
    distinct = {}
    for c in circuits:
        distinct.setdefault(tuple(c.wires), c)
    print(f"{len(circuits)} frontier circuits, {len(distinct)} distinct")
    ours_secure = sum(
        not probe.verdict(c, secrets, randoms)[0] for c in distinct.values()
    )

    def check(c):
        n, bad, nb_leak = probe.crosscheck(c, secrets, randoms)
        glitch_leak_ours = probe.verdict(c, secrets, randoms)[0]
        return n, bad, (nb_leak > 0) == glitch_leak_ours

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(check, distinct.values()))
    probes = sum(r[0] for r in results)
    bad = sum(len(r[1]) for r in results)
    differs = sum(not r[2] for r in results)
    print(f"ours: {ours_secure} glitch-secure among the distinct circuits")
    print(f"VerifMSI: {probes} probes compared, {bad} per-probe disagreements")
    print(f"end-to-end checkSecurity verdict differs from ours on {differs} circuits")
    print(f"({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
