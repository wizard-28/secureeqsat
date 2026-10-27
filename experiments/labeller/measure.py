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

Purpose
-------
This is the measurement behind finding F5 ("labelling and search scale at chain
scale"). It is a benchmark script, not a test: it prints two tables of timings
(reference checker vs bitsliced labeller) and asserts that the two always give the
same verdicts wherever both were run.

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
# depth = number of chained ISW gadgets; the cap stops saturation from exploding.
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
    """Build a random AND/XOR circuit over the given secret shares and randoms.

    Args:
        rng: a seeded `random.Random`, so results are reproducible.
        secrets: `{secret: [share names]}`.
        randoms: fresh random input names, e.g. ["r0", "r1"].
        gates: how many random gates to add.

    XOR is chosen twice as often as AND (the choice list has "xor" twice), which
    resembles masked circuits where XORs dominate.
    """
    c = Circuit()
    # every share of every secret, then every random, as input wires
    pool = [c.add_input(x) for shares in secrets.values() for x in shares]
    pool += [c.add_input(r) for r in randoms]
    for _ in range(gates):
        op = rng.choice(["and", "xor", "xor"])  # 2/3 XOR, 1/3 AND
        # a new gate over two random existing wires; it joins the pool
        pool.append(c.add_gate(op, rng.choice(pool), rng.choice(pool)))
    return c


def circuit_scaling():
    """Part 1: time one circuit check as the number of random bits k grows.

    Algorithm, step by step, for each k in `CIRCUIT_RANDOMS`:
      1. Build a random 12-gate circuit with k randoms (seeded by k).
      2. Time the bitsliced check of every wire.
      3. If k is small enough, also time the reference checker and assert that it
         returns exactly the same verdicts.
      4. Print the two times. The reference time grows as 2**k, the bitsliced one
         much more slowly.
    """
    print("== single circuit: 12 gates, 2 secrets, k randoms ==")
    print(f"{'randoms':>7} {'reference':>10} {'bitsliced':>10}")
    for k in CIRCUIT_RANDOMS:
        randoms = [f"r{i}" for i in range(k)]  # ["r0", ..., "r{k-1}"]
        free = free_vars_for(SECRET_GROUPS_AND, randoms)
        circ = random_circuit(random.Random(k), SECRET_GROUPS_AND, randoms, 12)
        t = time.perf_counter()  # high-resolution timer start
        new = check_first_order_bitsliced(circ, SECRET_GROUPS_AND, free)
        t_new = time.perf_counter() - t
        ref_txt = "-"  # shown when the reference is skipped as too slow
        if k <= REFERENCE_MAX_RANDOMS:
            t = time.perf_counter()
            ref = check_first_order(circ, SECRET_GROUPS_AND, free)
            ref_txt = f"{time.perf_counter() - t:.3f}s"
            assert ref == new, "checkers disagree"
        print(f"{k:>7} {ref_txt:>10} {t_new:>9.4f}s", flush=True)


def build_chain(depth):
    """Build a chain of `depth` ISW ANDs inside an e-graph.

    Returns `(egraph, secrets, randoms)`. The chain computes
    ((s0 AND s1) AND s2) ... with `depth + 1` secrets, one fresh random per gadget.
    Each gadget's output shares feed the next gadget as its first operand.
    """
    eg = EGraph()
    x0, x1 = eg.add_var("s0_0"), eg.add_var("s0_1")  # shares of the first secret
    secrets = {"s0": ["s0_0", "s0_1"]}  # secret name -> share names
    randoms = []  # fresh random names, e.g. ["r1", "r2"]
    for k in range(1, depth + 1):
        y0, y1 = eg.add_var(f"s{k}_0"), eg.add_var(f"s{k}_1")  # next secret's shares
        r = eg.add_var(f"r{k}")  # this gadget's fresh random
        secrets[f"s{k}"] = [f"s{k}_0", f"s{k}_1"]
        randoms.append(f"r{k}")
        # the running result (x0, x1) becomes the first operand of the next gadget
        x0, x1 = isw_and(None, eg, x0, x1, y0, y1, r)
    return eg, secrets, randoms


def sampled_reference_cost(eg, secrets, randoms, rng):
    """Mean seconds per class for the reference checker, over SAMPLE classes.

    Used to ESTIMATE the reference labeller's total time when running it on every
    class would take too long: time it on `SAMPLE` randomly chosen classes and
    return the average, which the caller multiplies by the number of classes.
    """
    free = free_vars_for(secrets, randoms)
    reps, _ = extract(eg)  # a representative node per class, to build test circuits
    classes = sorted({eg.find(c) for c in eg._nodes})  # distinct canonical ids
    total = 0.0  # accumulated seconds
    for c in rng.sample(classes, SAMPLE):  # SAMPLE distinct classes, at random
        circ = Circuit()
        materialize(eg, reps, [c], circ)  # a circuit whose output is class c
        t = time.perf_counter()
        check_first_order(circ, secrets, free)
        total += time.perf_counter() - t
    return total / SAMPLE


def chain_scaling():
    """Part 2: time labelling every class of saturated chain e-graphs.

    Algorithm, step by step, for each configuration in `CONFIGS`:
      1. Build the chain e-graph of the given depth and saturate it (with a class
         cap so it stays small enough).
      2. Time the bitsliced labeller on every class.
      3. If `full_reference` is True, also run the reference labeller on every class,
         assert both give identical labels, and time it. Otherwise ESTIMATE the
         reference time from a sample (shown with "~" and "est").
      4. Print classes, saturation time, both times and the speed-up.
    """
    rng = random.Random(0)  # seeded: the sample of classes is reproducible
    print("== chain e-graphs: label every class ==")
    print(
        f"{'depth':>5} {'rules':>5} {'bits':>4} {'classes':>7} "
        f"{'saturate':>9} {'reference':>12} {'bitsliced':>10} {'speedup':>9}"
    )
    for depth, rules, cap, full_reference in CONFIGS:
        eg, secrets, randoms = build_chain(depth)
        # width of the assignment space: number of secrets + number of free bits
        bits = len(secrets) + len(free_vars_for(secrets, randoms))
        t = time.perf_counter()
        saturate(eg, RULES_FULL if rules == "full" else RULES_CORE, 12, cap)
        t_sat = time.perf_counter() - t

        t = time.perf_counter()
        new = class_safety(eg, secrets, randoms)  # bitsliced labels {class: safe?}
        t_new = time.perf_counter() - t

        if full_reference:
            t = time.perf_counter()
            ref = class_safety_reference(eg, secrets, randoms)  # slow reference labels
            t_ref = time.perf_counter() - t
            assert ref == new, "labellers disagree"
            ref_txt = f"{t_ref:.2f}s"
        else:
            # estimated total = mean time per class x number of classes
            t_ref = sampled_reference_cost(eg, secrets, randoms, rng) * len(new)
            ref_txt = f"~{t_ref:.0f}s est"
        # `:,.0f` formats with thousands separators and no decimals, e.g. 7,500x
        speedup = f"{t_ref / t_new:,.0f}x" if t_new > 0 else "-"
        print(
            f"{depth:>5} {rules:>5} {bits:>4} {len(new):>7} {t_sat:>8.1f}s "
            f"{ref_txt:>12} {t_new:>9.3f}s {speedup:>9}",
            flush=True,
        )
    print("labels identical wherever the reference labeller ran in full")


def main():
    """Run both measurements, with a blank line between the two tables."""
    circuit_scaling()
    print()
    chain_scaling()


if __name__ == "__main__":
    main()
