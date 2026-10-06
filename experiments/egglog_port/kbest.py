"""The payoff question, answered by enumeration.

Unconstrained extraction of the two-gadget chain gives a cheaper but insecure
circuit; the hand-written composition is 16 gates and secure.  Does ANY
extraction up to k-best secure the chain for fewer than 16 gates?

`egglog.extract_multiple` enumerates extraction variants, so we can take the
k-best variants of each output, form all pairs, and record the cheapest secure
pair.  This is an approximate constrained extraction (a k-best frontier rather
than an exact optimum) — good enough to decide whether the payoff exists at all.

Usage:
    uv run python experiments/egglog_port/kbest.py --rules full --k 40
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "experiments" / "premise_test"))

from masked import Circuit, check_first_order, unsafe_wires  # noqa: E402
from port import (  # noqa: E402
    FREE_CHAIN,
    SECRETS_CHAIN,
    isw_and,
    make_egraph,
    node_to_wire,
    parse_extracted,
)
from port import B as PortB  # noqa: E402


def build_chain(eg):
    v = PortB.var
    a0, a1 = v("a0"), v("a1")
    b0, b1 = v("b0"), v("b1")
    d0, d1 = v("d0"), v("d1")
    r1, r2 = v("r1"), v("r2")
    t0, t1 = isw_and(a0, a1, b0, b1, r1)
    u0, u1 = isw_and(t0, t1, d0, d1, r2)
    return eg.let("u0", u0), eg.let("u1", u1)


def circuit_of(t0, t1):
    circ = Circuit()
    circ.outputs = [
        node_to_wire(parse_extracted(str(t0)), circ),
        node_to_wire(parse_extracted(str(t1)), circ),
    ]
    return circ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", choices=("core", "full"), default="full")
    ap.add_argument("--k", type=int, default=40)
    ap.add_argument("--iters", type=int, default=4)
    args = ap.parse_args()

    eg = make_egraph(args.rules)
    e0, e1 = build_chain(eg)
    t = time.time()
    eg.run(args.iters)
    print(f"saturation: run({args.iters}) [{args.rules}] in {time.time() - t:.2f}s")
    print(f"function sizes: {eg.all_function_sizes()}")

    v0 = eg.extract_multiple(e0, args.k)
    v1 = eg.extract_multiple(e1, args.k)
    print(f"variants: {len(v0)} for u0, {len(v1)} for u1  (k={args.k})")

    best_any = None  # (gates, secure)
    best_secure = None
    tested = 0
    t = time.time()
    for a in v0:
        for b in v1:
            if a is None or b is None:
                continue
            circ = circuit_of(a, b)
            gates = circ.gate_count()
            secure = not unsafe_wires(
                check_first_order(circ, SECRETS_CHAIN, FREE_CHAIN)
            )
            tested += 1
            if best_any is None or gates < best_any[0]:
                best_any = (gates, secure)
            if secure and (best_secure is None or gates < best_secure[0]):
                best_secure = (gates, secure)
    print(f"tested {tested} pairs in {time.time() - t:.1f}s")
    print(
        f"cheapest extraction overall : {best_any[0]} gates, "
        f"{'SECURE' if best_any[1] else 'INSECURE'}"
    )
    if best_secure is None:
        print("cheapest SECURE extraction  : none found in the k-best frontier")
    else:
        print(f"cheapest SECURE extraction  : {best_secure[0]} gates")
        print("reference hand-written chain: 16 gates, secure")
        delta = best_secure[0] - 16
        print(
            f"payoff vs hand-written      : {delta:+d} gate(s)"
            + ("  <-- WIN" if delta < 0 else "")
        )


if __name__ == "__main__":
    main()
