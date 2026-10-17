"""Labelling cost: reference checker/labeller vs the bitsliced labeller.

Part 1 mirrors docs/adversarial-search-3.md §D2: one random 12-gate circuit,
2 secrets, k randoms, timing a single check of every wire.

Part 2: for a chain of `depth` ISW masked ANDs (depth + 1 secrets, `depth` fresh
randoms), saturate the in-house e-graph up to a class cap, then label every
class with both labellers and time them. Where both run, their labels must be
identical (the script asserts it).

The reference labeller is exponential per class and is only run where it
finishes in reasonable time. For the largest configuration its cost is instead
EXTRAPOLATED from a timed sample of classes, and reported as an estimate.

Usage:
    uv run python experiments/labeller/measure.py
"""

import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ("premise_test", "constrained_extraction", "labeller"):
    sys.path.insert(0, str(ROOT / "experiments" / sub))

from constrained import (  # noqa: E402
    class_safety,
    class_safety_reference,
    free_vars_for,
)
from egraph import (  # noqa: E402
    RULES_CORE,
    RULES_FULL,
    EGraph,
    extract,
    materialize,
    saturate,
)
from labeller import check_first_order_bitsliced  # noqa: E402
from masked import SECRET_GROUPS_AND, Circuit, check_first_order  # noqa: E402
from run_chain import isw_and  # noqa: E402

# (depth, rules, class cap, run the reference labeller in full?)
CONFIGS = [
    (1, "full", 10**9, True),
    (2, "core", 10**9, True),
    (3, "full", 1000, True),
    (2, "full", 1000, True),
    (5, "full", 1000, False),
]
SAMPLE = 5  # classes timed for the extrapolated reference cost
CIRCUIT_RANDOMS = [2, 6, 10, 12, 14, 16, 20, 22]  # 22 + 4 = the 2**26 cap
REFERENCE_MAX_RANDOMS = 14  # the reference checker takes >5 s per check beyond


def random_circuit(rng, secrets, randoms, gates):
    c = Circuit()
    pool = [c.add_input(x) for shares in secrets.values() for x in shares]
    pool += [c.add_input(r) for r in randoms]
    for _ in range(gates):
        op = rng.choice(["and", "xor", "xor"])
        pool.append(c.add_gate(op, rng.choice(pool), rng.choice(pool)))
    return c


def circuit_scaling():
    print("== single circuit: 12 gates, 2 secrets, k randoms ==")
    print(f"{'randoms':>7} {'reference':>10} {'bitsliced':>10}")
    for k in CIRCUIT_RANDOMS:
        randoms = [f"r{i}" for i in range(k)]
        free = free_vars_for(SECRET_GROUPS_AND, randoms)
        circ = random_circuit(random.Random(k), SECRET_GROUPS_AND, randoms, 12)
        t = time.perf_counter()
        new = check_first_order_bitsliced(circ, SECRET_GROUPS_AND, free)
        t_new = time.perf_counter() - t
        ref_txt = "-"
        if k <= REFERENCE_MAX_RANDOMS:
            t = time.perf_counter()
            ref = check_first_order(circ, SECRET_GROUPS_AND, free)
            ref_txt = f"{time.perf_counter() - t:.3f}s"
            assert ref == new, "checkers disagree"
        print(f"{k:>7} {ref_txt:>10} {t_new:>9.4f}s", flush=True)


def build_chain(depth):
    eg = EGraph()
    x0, x1 = eg.add_var("s0_0"), eg.add_var("s0_1")
    secrets = {"s0": ["s0_0", "s0_1"]}
    randoms = []
    for k in range(1, depth + 1):
        y0, y1 = eg.add_var(f"s{k}_0"), eg.add_var(f"s{k}_1")
        r = eg.add_var(f"r{k}")
        secrets[f"s{k}"] = [f"s{k}_0", f"s{k}_1"]
        randoms.append(f"r{k}")
        x0, x1 = isw_and(None, eg, x0, x1, y0, y1, r)
    return eg, secrets, randoms


def sampled_reference_cost(eg, secrets, randoms, rng):
    """Mean seconds per class for the reference checker, over SAMPLE classes."""
    free = free_vars_for(secrets, randoms)
    reps, _ = extract(eg)
    classes = sorted({eg.find(c) for c in eg._nodes})
    total = 0.0
    for c in rng.sample(classes, SAMPLE):
        circ = Circuit()
        materialize(eg, reps, [c], circ)
        t = time.perf_counter()
        check_first_order(circ, secrets, free)
        total += time.perf_counter() - t
    return total / SAMPLE


def chain_scaling():
    rng = random.Random(0)
    print("== chain e-graphs: label every class ==")
    print(
        f"{'depth':>5} {'rules':>5} {'bits':>4} {'classes':>7} "
        f"{'saturate':>9} {'reference':>12} {'bitsliced':>10} {'speedup':>9}"
    )
    for depth, rules, cap, full_reference in CONFIGS:
        eg, secrets, randoms = build_chain(depth)
        bits = len(secrets) + len(free_vars_for(secrets, randoms))
        t = time.perf_counter()
        saturate(eg, RULES_FULL if rules == "full" else RULES_CORE, 12, cap)
        t_sat = time.perf_counter() - t

        t = time.perf_counter()
        new = class_safety(eg, secrets, randoms)
        t_new = time.perf_counter() - t

        if full_reference:
            t = time.perf_counter()
            ref = class_safety_reference(eg, secrets, randoms)
            t_ref = time.perf_counter() - t
            assert ref == new, "labellers disagree"
            ref_txt = f"{t_ref:.2f}s"
        else:
            t_ref = sampled_reference_cost(eg, secrets, randoms, rng) * len(new)
            ref_txt = f"~{t_ref:.0f}s est"
        speedup = f"{t_ref / t_new:,.0f}x" if t_new > 0 else "-"
        print(
            f"{depth:>5} {rules:>5} {bits:>4} {len(new):>7} {t_sat:>8.1f}s "
            f"{ref_txt:>12} {t_new:>9.3f}s {speedup:>9}",
            flush=True,
        )
    print("labels identical wherever the reference labeller ran in full")


def main():
    circuit_scaling()
    print()
    chain_scaling()


if __name__ == "__main__":
    main()
