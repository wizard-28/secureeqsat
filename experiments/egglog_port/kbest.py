"""The payoff question, answered by enumeration.

Unconstrained extraction of the two-gadget chain gives a cheaper but insecure
circuit; the hand-written composition is 16 gates and secure.  Does ANY
extraction up to k-best secure the chain for fewer than 16 gates?

`egglog.extract_multiple` enumerates extraction variants, so we can take the
k-best variants of each output, form all pairs, and record the cheapest secure
pair.  This is an approximate constrained extraction (a k-best frontier rather
than an exact optimum) — good enough to decide whether the payoff exists at all.

Purpose
-------
Finding F4 ("no payoff from plain Boolean rewriting at chain scale"). The chain
is two ISW gadgets, (a AND b) AND d, with two outputs u0 and u1. For each output
egglog returns up to k of its cheapest extractions; every pairing (u0 variant, u1
variant) is turned into a circuit, costed, and security-checked with the in-house
checker. With k = 40 this is up to 6 x 40 = 240 pairs.

What it does NOT show: it is a sample of the cheapest extractions, not an
exhaustive search, so "none found" means none in the k-best frontier, not none
anywhere. Only the in-house checker is used here (not VerifMSI).

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
    """Add the two-gadget ISW chain (a AND b) AND d to the egglog e-graph.

    The first gadget (random r1) produces shares (t0, t1) of a AND b; the second
    (random r2) ANDs that with d. Returns the e-graph handles for the two output
    shares, named "u0" and "u1".
    """
    v = PortB.var  # shorthand: v("a0") makes the egglog variable term a0
    a0, a1 = v("a0"), v("a1")  # shares of secret a
    b0, b1 = v("b0"), v("b1")  # shares of secret b
    d0, d1 = v("d0"), v("d1")  # shares of secret d
    r1, r2 = v("r1"), v("r2")  # fresh randoms: r1 for gadget 1, r2 for gadget 2
    t0, t1 = isw_and(a0, a1, b0, b1, r1)  # shares of a AND b (gadget 1's outputs)
    u0, u1 = isw_and(t0, t1, d0, d1, r2)  # shares of (a AND b) AND d (gadget 2)
    return eg.let("u0", u0), eg.let("u1", u1)


def circuit_of(t0, t1):
    """Turn two extracted egglog terms (one per output share) into one `Circuit`.

    Each term is printed, parsed back into a tree, and added as wires. The
    circuit shares identical gates, so the gate count is a real shared count.
    """
    circ = Circuit()
    # str(term) is egglog's printed expression; parse it into a tree; add the tree
    # to the circuit as wires and keep the root wire's name as an output
    circ.outputs = [
        node_to_wire(parse_extracted(str(t0)), circ),
        node_to_wire(parse_extracted(str(t1)), circ),
    ]
    return circ


def main():
    """Saturate the chain, enumerate k-best extractions, and test every pairing.

    Prints the cheapest extraction overall (and whether it is secure), the
    cheapest SECURE extraction if any, and how it compares to the hand-written
    16-gate chain.

    Algorithm, step by step:
      1. Build an egglog e-graph and add the two-gadget chain.
      2. Run saturation for `--iters` iterations.
      3. Ask egglog for the k cheapest distinct extractions of output u0 and of
         output u1 (`extract_multiple`).
      4. For every pair (one u0 variant, one u1 variant): build the circuit, count
         its gates, and run the security checker.
      5. Keep the cheapest circuit overall, and the cheapest one that is secure.
      6. Print both, and the difference from the hand-written 16-gate secure chain
         (a negative difference would be a win; none was found).
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", choices=("core", "full"), default="full")
    ap.add_argument("--k", type=int, default=40)
    ap.add_argument("--iters", type=int, default=4)
    args = ap.parse_args()

    eg = make_egraph(args.rules)  # egglog e-graph holding the rewrite rules
    e0, e1 = build_chain(eg)  # handles to the chain's two output shares
    t = time.time()  # start time, for timing saturation
    eg.run(args.iters)  # saturate for the requested number of iterations
    print(f"saturation: run({args.iters}) [{args.rules}] in {time.time() - t:.2f}s")
    print(f"function sizes: {eg.all_function_sizes()}")

    # Up to k cheapest extractions for each of the two outputs.
    # the k cheapest extractions (variants) of each output, as egglog terms;
    # a list can be shorter than k if egglog finds fewer distinct ones
    v0 = eg.extract_multiple(e0, args.k)
    v1 = eg.extract_multiple(e1, args.k)
    print(f"variants: {len(v0)} for u0, {len(v1)} for u1  (k={args.k})")

    best_any = (
        None  # cheapest pair seen so far, as (gates, is_secure), e.g. (14, False)
    )
    best_secure = None  # cheapest SECURE pair so far, same shape; None = none found
    tested = 0  # how many pairs were checked, e.g. 240
    t = time.time()
    # Try every pairing of a u0 variant with a u1 variant.
    for a in v0:
        for b in v1:
            if a is None or b is None:
                continue
            circ = circuit_of(a, b)  # the circuit made of this pair
            gates = circ.gate_count()  # its cost: number of AND/XOR gates
            # True if the checker found NO leaking wire
            secure = not unsafe_wires(
                check_first_order(circ, SECRETS_CHAIN, FREE_CHAIN)
            )
            tested += 1
            if best_any is None or gates < best_any[0]:  # new cheapest overall
                best_any = (gates, secure)
            if secure and (best_secure is None or gates < best_secure[0]):
                best_secure = (gates, secure)  # new cheapest among the secure ones
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
        delta = (
            best_secure[0] - 16
        )  # gates saved (negative) or lost vs the 16-gate chain
        print(
            f"payoff vs hand-written      : {delta:+d} gate(s)"
            + ("  <-- WIN" if delta < 0 else "")
        )


if __name__ == "__main__":
    main()
