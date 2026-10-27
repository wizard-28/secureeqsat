"""Does the security constraint leave any room on a larger circuit?

Single-gadget result (run_constrained.py): the constrained optimum equals the
known construction, so the constraint costs 1 gate and buys nothing. That is a
null-result signal at gadget scale. This script asks the same question on a
two-gadget chain (16 gates), where cross-gadget restructuring could help.

Purpose
-------
Repeats the comparison of `run_constrained.py` on the two-gadget chain
(a AND b) AND d, once with the CORE rules and once with the FULL rules, and prints,
for each: the unconstrained extraction (cheapest, probably leaking), the
constrained extraction (cheapest secure one), how long labelling took, and how
many classes were unsafe. The constrained result does not beat the hand-written
16-gate chain, which is part of finding F4 (no payoff at chain scale).

    uv run python experiments/constrained_extraction/run_chain.py
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "premise_test"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from constrained import (  # noqa: E402
    class_safety,
    extract_constrained,
    materialize_constrained,
    root_choices,
)
from egraph import (  # noqa: E402
    RULES_CORE,
    RULES_FULL,
    EGraph,
    extract,
    materialize,
    saturate,
)
from masked import Circuit, check_first_order, unsafe_wires  # noqa: E402

# Three secrets (a, b, d), two fresh randoms (one per gadget). The free bits are the
# first share of each secret plus the randoms.
SECRETS = {"a": ["a0", "a1"], "b": ["b0", "b1"], "d": ["d0", "d1"]}
RANDOMS = ["r1", "r2"]
FREE = ["a0", "b0", "d0", *RANDOMS]
INPUTS = ["a0", "a1", "b0", "b1", "d0", "d1", "r1", "r2"]


def isw_and(c, eg, x0, x1, y0, y1, r):
    """Build one ISW masked AND in `c` (eg is None) or in an e-graph.

    Args:
        c: a `Circuit` to add gates to (used when `eg` is None).
        eg: an `EGraph` to add nodes to, or None to build a plain circuit.
        x0, x1, y0, y1: the shares of the two operands (wire names or class ids).
        r: the fresh random bit.

    Returns the two output shares `(out0, out1)`:
        out0 = x0&y0 ^ r
        out1 = ((r ^ x0&y1) ^ x1&y0) ^ x1&y1
    The same wiring in both modes, so the circuit and the e-graph describe the
    same gadget. The order of the XORs (r first) is what keeps it secure.
    """
    if eg is None:  # circuit mode: arguments are wire NAMES like "a0"
        p1 = c.add_gate("and", x0, y0)  # x0*y0
        out0 = c.add_gate("xor", p1, r)  # output share 0
        # r enters first: w1 = r ^ x0*y1, then fold in x1*y0, then x1*y1
        w1 = c.add_gate("xor", r, c.add_gate("and", x0, y1))
        w2 = c.add_gate("xor", w1, c.add_gate("and", x1, y0))
        out1 = c.add_gate("xor", w2, c.add_gate("and", x1, y1))  # output share 1
        return out0, out1
    # e-graph mode: arguments are class ids (integers), same wiring as above
    p1 = eg.add_and(x0, y0)
    out0 = eg.add_xor(p1, r)
    w1 = eg.add_xor(r, eg.add_and(x0, y1))
    w2 = eg.add_xor(w1, eg.add_and(x1, y0))
    out1 = eg.add_xor(w2, eg.add_and(x1, y1))
    return out0, out1


def build_chain_circuit():
    """The hand-written two-gadget chain as a plain `Circuit` (16 gates, secure).

    The first gadget ANDs a and b (random r1); its output shares are fed into a
    second gadget that ANDs with d (random r2). Used as the reference.
    """
    c = Circuit()
    a0, a1 = c.add_input("a0"), c.add_input("a1")  # shares of secret a
    b0, b1 = c.add_input("b0"), c.add_input("b1")  # shares of secret b
    d0, d1 = c.add_input("d0"), c.add_input("d1")  # shares of secret d
    r1, r2 = c.add_input("r1"), c.add_input("r2")  # one fresh random per gadget
    t0, t1 = isw_and(c, None, a0, a1, b0, b1, r1)  # shares of a AND b
    u0, u1 = isw_and(c, None, t0, t1, d0, d1, r2)  # shares of (a AND b) AND d
    c.outputs = [u0, u1]
    return c


def build_chain_egraph():
    """The same chain built inside an `EGraph`; returns `(egraph, u0, u1)`."""
    eg = EGraph()
    # every name below is an e-class id (an integer), one per input or intermediate
    a0, a1 = eg.add_var("a0"), eg.add_var("a1")
    b0, b1 = eg.add_var("b0"), eg.add_var("b1")
    d0, d1 = eg.add_var("d0"), eg.add_var("d1")
    r1, r2 = eg.add_var("r1"), eg.add_var("r2")
    t0, t1 = isw_and(None, eg, a0, a1, b0, b1, r1)  # classes for a AND b
    u0, u1 = isw_and(None, eg, t0, t1, d0, d1, r2)  # classes for the final outputs
    return eg, u0, u1


def verdict(circ):
    """Return the list of leaking wires of `circ` for the chain's secrets."""
    v = check_first_order(circ, SECRETS, FREE)  # {wire name: True if safe}
    return unsafe_wires(v)  # just the names whose value is False


def main():
    """Compare unconstrained and constrained extraction on the chain.

    Algorithm, step by step, once for CORE rules and once for FULL rules:
      1. Build the chain in a fresh e-graph and saturate it (with limits, since
         the chain's e-graph grows fast). Warn if a limit was hit.
      2. Unconstrained extraction: cheapest nodes, ignoring security. Report the
         gate count and the verdict.
      3. Label every class safe or unsafe (time it) and count the unsafe ones.
      4. Constrained extraction: cheapest nodes through safe classes only,
         outputs chosen with `root_choices`, then built.
      5. Report the constrained gate count and verdict, the price of security
         (constrained minus unconstrained), and the difference from the original
         16-gate chain.
    """
    original = build_chain_circuit()  # the hand-written reference chain
    print(
        f"original 2-AND chain: {original.gate_count()} gates "
        f"({original.and_count()} AND + {original.xor_count()} XOR), "
        f"{'SECURE' if not verdict(original) else 'INSECURE'}"
    )

    for rules, name in ((RULES_CORE, "core rules"), (RULES_FULL, "full rules")):
        eg, u0, u1 = build_chain_egraph()  # a fresh e-graph for each rule set
        t0 = time.time()  # start time, for timing saturation
        # iters = rounds run; saturated = fixed point reached; hit = a limit stopped it
        iters, saturated, hit = saturate(eg, rules, max_iters=12, max_classes=40000)
        t_sat = time.time() - t0  # seconds spent saturating
        roots = [eg.find(u0), eg.find(u1)]  # canonical ids of the two output classes
        print(
            f"\n[{name}] saturation: {iters} iters, saturated={saturated}, "
            f"hit_limit={hit}, {t_sat:.1f}s, "
            f"{eg.num_classes()} classes / {eg.num_nodes()} nodes"
        )
        if hit:
            print(
                "  resource limit hit; results below are from a partial "
                "saturation and are indicative only"
            )

        best_u, _ = extract(eg)  # cheapest node per class, ignoring security
        out_u = Circuit()  # the unconstrained circuit
        try:
            materialize(eg, best_u, roots, out_u)
        except Exception as exc:  # noqa: BLE001
            print(f"  unconstrained extraction failed: {exc}")
            continue
        bad_u = verdict(out_u)  # its leaking wires, e.g. ["xor(b1,b0)"]
        print(
            f"  unconstrained: {out_u.gate_count()} gates, "
            f"{'SECURE' if not bad_u else f'INSECURE ({len(bad_u)} wires)'}"
        )

        t0 = time.time()  # restart the timer for the labelling step
        safety = class_safety(eg, SECRETS, RANDOMS)  # class id -> True if safe
        t_lab = time.time() - t0  # seconds spent labelling classes
        n_unsafe = sum(1 for v in safety.values() if not v)  # count of unsafe classes
        best_i, cost_i = extract_constrained(eg, safety)  # best/cost over safe classes
        choices = root_choices(eg, cost_i, roots)  # chosen node per output class
        out_c = Circuit()  # the constrained circuit
        try:
            materialize_constrained(eg, best_i, choices, roots, out_c)
        except Exception as exc:  # noqa: BLE001
            print(f"  constrained extraction failed: {exc}")
            continue
        bad_c = verdict(out_c)  # leaking wires of the constrained circuit (expect [])
        print(
            f"  constrained:   {out_c.gate_count()} gates, "
            f"{'SECURE' if not bad_c else f'INSECURE ({len(bad_c)} wires)'}"
            f"   [labelling {t_lab:.1f}s, {n_unsafe}/{len(safety)} unsafe classes]"
        )
        print(
            f"  price of security: {out_c.gate_count() - out_u.gate_count()} gate(s); "
            f"vs original: {out_c.gate_count() - original.gate_count():+d}"
        )


if __name__ == "__main__":
    main()
