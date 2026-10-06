"""Feasibility prototype: does security-constrained extraction work, and what
does the constraint cost?

Runs three extractions over the same saturated ISW e-graph:

  1. the original ISW circuit (reference),
  2. unconstrained cost-minimal extraction (known to be insecure),
  3. first-order security-constrained extraction (this module).

Reports gate counts, security verdicts, and whether the constrained result is
functionally equivalent to ISW.
"""

import sys
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
from egraph import RULES_FULL, extract, materialize, saturate  # noqa: E402
from masked import (  # noqa: E402
    FREE_AND,
    SECRET_GROUPS_AND,
    Circuit,
    build_isw_and,
    check_first_order,
    unsafe_wires,
)
from run import build_isw_egraph, equivalent  # noqa: E402

INPUTS = ["a0", "a1", "b0", "b1", "r"]


def describe(label, circ, secrets, randoms):
    verdict = check_first_order(circ, secrets, randoms)
    bad = unsafe_wires(verdict)
    print(
        f"  {label:34s} {circ.gate_count():2d} gates "
        f"({circ.and_count()} AND + {circ.xor_count()} XOR)   "
        f"{'SECURE' if not bad else f'INSECURE ({len(bad)})'}"
    )
    return bad


def render(eg, best, c, depth=0):
    """Small term renderer for reporting unsafe classes."""
    c = eg.find(c)
    node = best.get(c)
    if node is None:
        return f"<class {c}>"
    op = node[0]
    if op == "var":
        return node[1]
    if op == "const":
        return str(node[1])
    a, b = node[1]
    return f"({render(eg, best, a)} {op} {render(eg, best, b)})"


def main():
    eg, c0, c1 = build_isw_egraph()
    saturate(eg, RULES_FULL)
    roots = [eg.find(c0), eg.find(c1)]
    print(
        f"e-graph after saturation: {eg.num_classes()} classes, "
        f"{eg.num_nodes()} nodes\n"
    )

    print("extractions:")
    describe("1. original ISW AND", build_isw_and(), SECRET_GROUPS_AND, FREE_AND)

    best_u, _ = extract(eg)
    out_u = Circuit()
    materialize(eg, best_u, roots, out_u)
    bad_u = describe("2. unconstrained (cost-only)", out_u, SECRET_GROUPS_AND, FREE_AND)

    safety = class_safety(eg, SECRET_GROUPS_AND, ["r"])
    best_i, cost_i = extract_constrained(eg, safety)
    choices = root_choices(eg, cost_i, roots)
    out_c = Circuit()
    materialize_constrained(eg, best_i, choices, roots, out_c)
    bad_c = describe("3. security-constrained", out_c, SECRET_GROUPS_AND, FREE_AND)

    ok_c, *_ = equivalent(build_isw_and(), out_c, INPUTS)
    print(f"\n  constrained output functionally equivalent to ISW: {ok_c}")

    n_safe = sum(1 for v in safety.values() if v)
    print(f"\nsafety labels: {n_safe}/{len(safety)} classes safe")
    print("unsafe classes (function depends on a secret):")
    shown = 0
    for c in sorted(safety, key=lambda x: str(x)):
        if not safety[c] and shown < 6:
            print(f"    {render(eg, best_u, c)}")
            shown += 1
    if shown == 0:
        print("    (none)")

    print("\nsummary:")
    print(
        f"  unconstrained optimum : {out_u.gate_count()} gates, "
        f"{'INSECURE' if bad_u else 'secure'}"
    )
    print(
        f"  constrained optimum   : {out_c.gate_count()} gates, "
        f"{'INSECURE' if bad_c else 'secure'}"
    )
    print(
        f"  price of security     : {out_c.gate_count() - out_u.gate_count()} gate(s)"
    )
    print(
        f"  constrained vs known construction: "
        f"{out_c.gate_count() - build_isw_and().gate_count():+d} gate(s)"
    )


if __name__ == "__main__":
    main()
