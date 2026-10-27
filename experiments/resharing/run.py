"""Rule-class ablation on the shared-value layer (design/0016).

For every fixture and every subset of {R1, R2, R3}: saturate in egglog, then
extract the cheapest term twice -- unconstrained, and constrained to circuits
with no leaking wire -- and report gates, randoms, cost (gates + randoms) and
the first-order verdict of the lowered circuit.

    uv run python experiments/resharing/run.py               # ablation
    uv run python experiments/resharing/run.py --crosscheck  # + VerifMSI
    uv run python experiments/resharing/run.py --scale       # chain depth sweep

Purpose
-------
This produces the results table of finding F6/F7 (see `RESULTS.md`): which rule
class (R1 identities, R2 gadget swaps, R3 refreshes) gives which saving on which
starting circuit, and whether the saving is secure. "Ablation" means switching rule
classes on and off to see what each one is worth by itself and in combination.

Output for each fixture: the start circuit, then for each of the 8 rule
combinations the cheapest UNCONSTRAINED term (may leak) and the cheapest
CONSTRAINED term (secure). A final "stability" table re-runs the full-rule case with
different frontier widths k to show the answers do not depend on k.
"""

import argparse
import itertools
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent  # this directory
ROOT = HERE.parents[1]  # the repo root (two levels up)
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "experiments" / "oracle_crosscheck"))
sys.path.insert(0, str(ROOT / "experiments" / "premise_test"))

from extract import Evaluator, kbest  # noqa: E402
from fixtures import FIXTURES, TIGHT  # noqa: E402

ALL = {**FIXTURES, **TIGHT}  # every starting circuit: name -> term
from gadgets import lower, secret_groups, secrets_of, show  # noqa: E402
from layer import export, saturate  # noqa: E402

# Every subset of the three rule classes: (), ("R1",), ("R2",), ("R3",), ("R1","R2"),
# ... up to all three: 2**3 = 8 configurations.
CONFIGS = [
    tuple(c) for n in range(4) for c in itertools.combinations(("R1", "R2", "R3"), n)
]


def describe(term):
    """Lower `term` and evaluate it; returns `(lowered, cost, leaking_wires)`."""
    low = lower([term])  # the circuit (and its randoms) for this term
    ev = Evaluator()
    cost, leaks = ev(term)  # exact cost (gates + randoms) and unsafe wires
    return low, cost, leaks


def fmt(term):
    """One-line summary: cost, gate/random split, verdict, and the term itself.

    Example: ` 14 = 12g + 2r  secure           isw(xor(a, b), refresh(xor(a, b)))`.
    The `>3` and `<16` in the format strings are field widths for alignment.
    """
    low, cost, leaks = describe(term)
    verdict = "secure" if not leaks else f"LEAKS ({len(leaks)} wires)"
    return (
        f"{cost:>3} = {low.circ.gate_count():>2}g + {len(low.randoms)}r  "
        f"{verdict:<16} {show(term)}"
    )


def ablation(k, iters):
    """Run every fixture under every rule combination and print the results.

    Algorithm, step by step, for each fixture and each rule configuration:
      1. Saturate the fixture in egglog with that configuration (`iters` rounds).
      2. Export the saturated e-graph as plain data.
      3. Extract the best term twice with the k-best extractor: once ignoring
         security (`secure=False`) and once with the leak cut (`secure=True`).
         The two runs share one `Evaluator`, so terms are not lowered twice.
      4. Print both results, plus size and timing statistics.
    Returns the rows `(fixture, label, best_unconstrained, best_constrained)` for
    the optional VerifMSI cross-check.
    """
    rows = []  # collected results, one per (fixture, configuration)
    for name, term in ALL.items():
        print(f"\n== {name}: {fmt(term)}")  # the starting circuit and its cost
        for cfg in CONFIGS:
            t0 = time.time()
            eg, _ = saturate(term, cfg, iters)
            classes, root = export(eg)
            t_sat = time.time() - t0  # seconds for saturation plus export
            ev = Evaluator()  # shared cache for the two extractions below
            res = {}  # secure flag -> (best term, info, seconds)
            for secure in (False, True):
                t0 = time.time()
                best, info = kbest(classes, root, k=k, secure=secure, evaluator=ev)
                res[secure] = (best, info, time.time() - t0)
            label = "+".join(cfg) or "none"  # e.g. "R1+R3", or "none" for ()
            for secure, tag in ((False, "unconstrained"), (True, "constrained  ")):
                best, info, dt = res[secure]
                body = fmt(best[1]) if best else "no secure term in the frontier"
                print(f"  {label:<9} {tag} {body}")
            print(
                f"  {'':<9} [{len(classes)} classes, saturate {t_sat:.2f}s, "
                f"{res[True][1]['evaluated']} terms evaluated, "
                f"converged={res[True][1]['converged']}]"
            )
            rows.append((name, label, res[False][0], res[True][0]))
    return rows


def stability(iters, ks=(2, 8, 32)):
    """Check the constrained cost does not change as the frontier width k grows.

    For each fixture, saturate with all rules, then run the constrained extraction with
    k = 2, 8 and 32 and print the three costs side by side. Equal costs mean the
    k-best frontier was wide enough for that fixture.
    """
    print("\n== frontier stability: constrained cost, all rules, by k")
    for name, term in ALL.items():
        eg, _ = saturate(term, ("R1", "R2", "R3"), iters)
        classes, root = export(eg)
        costs = []  # best cost found for each k, e.g. [14, 14, 14]
        for k in ks:
            best, _ = kbest(classes, root, k=k, secure=True)
            costs.append(best[0] if best else None)
        pairs = zip(ks, costs, strict=True)  # [(2, 14), (8, 14), (32, 14)]
        print(f"  {name:<14} " + "  ".join(f"k={k}: {c}" for k, c in pairs))


def crosscheck(rows):
    """Confirm every circuit reported above against VerifMSI (trust boundary).

    Algorithm, step by step:
      1. If VerifMSI is not installed, say the check was SKIPPED (a skip is not a
         pass) and return.
      2. Gather every distinct term: the fixtures plus every best term found.
      3. Lower each, and compare our verdicts with VerifMSI's wire by wire.
      4. Print how many circuits and wires were compared and any violations (the
         expected number is 0).
    """
    from crosscheck import compare, oracle_available

    if not oracle_available():
        print("\nVerifMSI not available: cross-check SKIPPED (not passed)")
        return
    terms = set(ALL.values())  # a set removes duplicate terms
    for _, _, u, c in rows:  # u: unconstrained best, c: constrained best
        for best in (u, c):
            if best:  # a best entry is (cost, term); keep the term
                terms.add(best[1])
    wires = 0  # total wires compared
    bad = []  # (term text, violation) for every disagreement
    for term in sorted(terms, key=repr):  # sorted so the output order is stable
        low = lower([term])
        out = compare(low.circ, secret_groups(secrets_of(term)), low.randoms)
        wires += out["n_wires"]
        bad += [(show(term), v) for v in out["violations"]]
    print(
        f"\n== VerifMSI cross-check: {len(terms)} distinct lowered circuits, "
        f"{wires} wires, {len(bad)} violations"
    )
    for v in bad:
        print("  ", v)


def scale(iters, k):
    """Time saturation and constrained extraction on ISW chains of depth 2 to 5.

    Builds `((x0 AND x1) AND x2) ...` with one ISW gadget per step, saturates with
    all rules, and prints the number of classes and nodes and the extraction time.
    This shows where per-term extraction becomes slow (about 144 s at depth 5).
    """
    print("\n== scale: ISW chain of depth n, all rules")
    names = [("in", f"x{i}") for i in range(8)]  # input terms x0 ... x7
    for depth in range(2, 6):
        term = names[0]
        for i in range(1, depth + 1):
            term = ("isw", term, names[i])  # wrap in another ISW with the next input
        t0 = time.time()
        eg, _ = saturate(term, ("R1", "R2", "R3"), iters)
        classes, root = export(eg)
        t_sat = time.time() - t0
        t0 = time.time()
        best, info = kbest(classes, root, k=k, secure=True)
        t_ext = time.time() - t0  # seconds for the constrained extraction
        print(
            f"  depth {depth}: {len(classes):>4} classes, "
            f"{sum(len(v) for v in classes.values()):>5} nodes, "
            f"saturate {t_sat:.2f}s, constrained extract {t_ext:.1f}s "
            f"({info['evaluated']} terms), cost {best[0] if best else None}"
        )


def main():
    """Parse options and run the ablation, stability table and optional extras."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=8)  # frontier width per class
    ap.add_argument("--iters", type=int, default=6)  # saturation rounds
    ap.add_argument("--crosscheck", action="store_true")  # also run VerifMSI
    ap.add_argument("--scale", action="store_true")  # also run the depth sweep
    args = ap.parse_args()
    rows = ablation(args.k, args.iters)
    stability(args.iters)
    if args.crosscheck:
        crosscheck(rows)
    if args.scale:
        scale(args.iters, args.k)


if __name__ == "__main__":
    main()
