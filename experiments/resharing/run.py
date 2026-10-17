"""Rule-class ablation on the shared-value layer (design/0016).

For every fixture and every subset of {R1, R2, R3}: saturate in egglog, then
extract the cheapest term twice -- unconstrained, and constrained to circuits
with no leaking wire -- and report gates, randoms, cost (gates + randoms) and
the first-order verdict of the lowered circuit.

    uv run python experiments/resharing/run.py               # ablation
    uv run python experiments/resharing/run.py --crosscheck  # + VerifMSI
    uv run python experiments/resharing/run.py --scale       # chain depth sweep
"""

import argparse
import itertools
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "experiments" / "oracle_crosscheck"))
sys.path.insert(0, str(ROOT / "experiments" / "premise_test"))

from extract import Evaluator, kbest  # noqa: E402
from fixtures import FIXTURES, TIGHT  # noqa: E402

ALL = {**FIXTURES, **TIGHT}
from gadgets import lower, secret_groups, secrets_of, show  # noqa: E402
from layer import export, saturate  # noqa: E402

CONFIGS = [
    tuple(c) for n in range(4) for c in itertools.combinations(("R1", "R2", "R3"), n)
]


def describe(term):
    low = lower([term])
    ev = Evaluator()
    cost, leaks = ev(term)
    return low, cost, leaks


def fmt(term):
    low, cost, leaks = describe(term)
    verdict = "secure" if not leaks else f"LEAKS ({len(leaks)} wires)"
    return (
        f"{cost:>3} = {low.circ.gate_count():>2}g + {len(low.randoms)}r  "
        f"{verdict:<16} {show(term)}"
    )


def ablation(k, iters):
    rows = []
    for name, term in ALL.items():
        print(f"\n== {name}: {fmt(term)}")
        for cfg in CONFIGS:
            t0 = time.time()
            eg, _ = saturate(term, cfg, iters)
            classes, root = export(eg)
            t_sat = time.time() - t0
            ev = Evaluator()
            res = {}
            for secure in (False, True):
                t0 = time.time()
                best, info = kbest(classes, root, k=k, secure=secure, evaluator=ev)
                res[secure] = (best, info, time.time() - t0)
            label = "+".join(cfg) or "none"
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
    print("\n== frontier stability: constrained cost, all rules, by k")
    for name, term in ALL.items():
        eg, _ = saturate(term, ("R1", "R2", "R3"), iters)
        classes, root = export(eg)
        costs = []
        for k in ks:
            best, _ = kbest(classes, root, k=k, secure=True)
            costs.append(best[0] if best else None)
        pairs = zip(ks, costs, strict=True)
        print(f"  {name:<14} " + "  ".join(f"k={k}: {c}" for k, c in pairs))


def crosscheck(rows):
    from crosscheck import compare, oracle_available

    if not oracle_available():
        print("\nVerifMSI not available: cross-check SKIPPED (not passed)")
        return
    terms = set(ALL.values())
    for _, _, u, c in rows:
        for best in (u, c):
            if best:
                terms.add(best[1])
    wires = 0
    bad = []
    for term in sorted(terms, key=repr):
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
    print("\n== scale: ISW chain of depth n, all rules")
    names = [("in", f"x{i}") for i in range(8)]
    for depth in range(2, 6):
        term = names[0]
        for i in range(1, depth + 1):
            term = ("isw", term, names[i])
        t0 = time.time()
        eg, _ = saturate(term, ("R1", "R2", "R3"), iters)
        classes, root = export(eg)
        t_sat = time.time() - t0
        t0 = time.time()
        best, info = kbest(classes, root, k=k, secure=True)
        t_ext = time.time() - t0
        print(
            f"  depth {depth}: {len(classes):>4} classes, "
            f"{sum(len(v) for v in classes.values()):>5} nodes, "
            f"saturate {t_sat:.2f}s, constrained extract {t_ext:.1f}s "
            f"({info['evaluated']} terms), cost {best[0] if best else None}"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--iters", type=int, default=6)
    ap.add_argument("--crosscheck", action="store_true")
    ap.add_argument("--scale", action="store_true")
    args = ap.parse_args()
    rows = ablation(args.k, args.iters)
    stability(args.iters)
    if args.crosscheck:
        crosscheck(rows)
    if args.scale:
        scale(args.iters, args.k)


if __name__ == "__main__":
    main()
