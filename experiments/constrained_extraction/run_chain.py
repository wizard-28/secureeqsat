"""Does the security constraint leave any room on a larger circuit?

Single-gadget result (run_constrained.py): the constrained optimum equals the
known construction, so the constraint costs 1 gate and buys nothing. That is a
null-result signal at gadget scale. This script asks the same question on a
two-gadget chain (16 gates), where cross-gadget restructuring could help.
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

SECRETS = {"a": ["a0", "a1"], "b": ["b0", "b1"], "d": ["d0", "d1"]}
RANDOMS = ["r1", "r2"]
FREE = ["a0", "b0", "d0", *RANDOMS]
INPUTS = ["a0", "a1", "b0", "b1", "d0", "d1", "r1", "r2"]


def isw_and(c, eg, x0, x1, y0, y1, r):
    """Build one ISW masked AND in `c` (eg is None) or in an e-graph."""
    if eg is None:
        p1 = c.add_gate("and", x0, y0)
        out0 = c.add_gate("xor", p1, r)
        w1 = c.add_gate("xor", r, c.add_gate("and", x0, y1))
        w2 = c.add_gate("xor", w1, c.add_gate("and", x1, y0))
        out1 = c.add_gate("xor", w2, c.add_gate("and", x1, y1))
        return out0, out1
    p1 = eg.add_and(x0, y0)
    out0 = eg.add_xor(p1, r)
    w1 = eg.add_xor(r, eg.add_and(x0, y1))
    w2 = eg.add_xor(w1, eg.add_and(x1, y0))
    out1 = eg.add_xor(w2, eg.add_and(x1, y1))
    return out0, out1


def build_chain_circuit():
    c = Circuit()
    a0, a1 = c.add_input("a0"), c.add_input("a1")
    b0, b1 = c.add_input("b0"), c.add_input("b1")
    d0, d1 = c.add_input("d0"), c.add_input("d1")
    r1, r2 = c.add_input("r1"), c.add_input("r2")
    t0, t1 = isw_and(c, None, a0, a1, b0, b1, r1)
    u0, u1 = isw_and(c, None, t0, t1, d0, d1, r2)
    c.outputs = [u0, u1]
    return c


def build_chain_egraph():
    eg = EGraph()
    a0, a1 = eg.add_var("a0"), eg.add_var("a1")
    b0, b1 = eg.add_var("b0"), eg.add_var("b1")
    d0, d1 = eg.add_var("d0"), eg.add_var("d1")
    r1, r2 = eg.add_var("r1"), eg.add_var("r2")
    t0, t1 = isw_and(None, eg, a0, a1, b0, b1, r1)
    u0, u1 = isw_and(None, eg, t0, t1, d0, d1, r2)
    return eg, u0, u1


def verdict(circ):
    v = check_first_order(circ, SECRETS, FREE)
    return unsafe_wires(v)


def main():
    original = build_chain_circuit()
    print(
        f"original 2-AND chain: {original.gate_count()} gates "
        f"({original.and_count()} AND + {original.xor_count()} XOR), "
        f"{'SECURE' if not verdict(original) else 'INSECURE'}"
    )

    for rules, name in ((RULES_CORE, "core rules"), (RULES_FULL, "full rules")):
        eg, u0, u1 = build_chain_egraph()
        t0 = time.time()
        iters, saturated, hit = saturate(eg, rules, max_iters=12, max_classes=40000)
        t_sat = time.time() - t0
        roots = [eg.find(u0), eg.find(u1)]
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

        best_u, _ = extract(eg)
        out_u = Circuit()
        try:
            materialize(eg, best_u, roots, out_u)
        except Exception as exc:  # noqa: BLE001
            print(f"  unconstrained extraction failed: {exc}")
            continue
        bad_u = verdict(out_u)
        print(
            f"  unconstrained: {out_u.gate_count()} gates, "
            f"{'SECURE' if not bad_u else f'INSECURE ({len(bad_u)} wires)'}"
        )

        t0 = time.time()
        safety = class_safety(eg, SECRETS, RANDOMS)
        t_lab = time.time() - t0
        n_unsafe = sum(1 for v in safety.values() if not v)
        best_i, cost_i = extract_constrained(eg, safety)
        choices = root_choices(eg, cost_i, roots)
        out_c = Circuit()
        try:
            materialize_constrained(eg, best_i, choices, roots, out_c)
        except Exception as exc:  # noqa: BLE001
            print(f"  constrained extraction failed: {exc}")
            continue
        bad_c = verdict(out_c)
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
