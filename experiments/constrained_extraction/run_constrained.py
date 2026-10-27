"""Feasibility prototype: does security-constrained extraction work, and what
does the constraint cost?

Runs three extractions over the same saturated ISW e-graph:

  1. the original ISW circuit (reference),
  2. unconstrained cost-minimal extraction (known to be insecure),
  3. first-order security-constrained extraction (this module).

Reports gate counts, security verdicts, and whether the constrained result is
functionally equivalent to ISW.

Purpose
-------
Demonstrates the repair at GADGET scale. Expected output: the original ISW is 8
gates and secure; unconstrained extraction gives 7 gates and leaks; constrained
extraction gives 8 gates and is secure. So the price of security is 1 gate, and
the constrained optimum equals the known ISW construction (it finds no cheaper
secure circuit). Run it with:

    uv run python experiments/constrained_extraction/run_constrained.py
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
    """Print one line (gate counts and SECURE/INSECURE) and return the bad wires.

    Args:
        label: text shown at the start of the line.
        circ: the circuit to report on.
        secrets, randoms: the secret groups and free variables for the checker.
    """
    verdict = check_first_order(circ, secrets, randoms)  # {wire name: safe?}
    bad = unsafe_wires(verdict)  # names of the leaking wires, [] if none
    print(
        f"  {label:34s} {circ.gate_count():2d} gates "
        f"({circ.and_count()} AND + {circ.xor_count()} XOR)   "
        f"{'SECURE' if not bad else f'INSECURE ({len(bad)})'}"
    )
    return bad


def render(eg, best, c, depth=0):
    """Small term renderer for reporting unsafe classes.

    Prints class `c` as a nested expression using the chosen node of each class
    in `best`, for example `((a1 and b0) xor (a1 and b1))`. `depth` is unused.
    """
    c = eg.find(c)  # canonical class id
    node = best.get(c)  # the node chosen for this class, e.g. ("xor", (3, 4))
    if node is None:
        return f"<class {c}>"  # no chosen node: print the id instead
    op = node[0]  # "var", "const", "and" or "xor"
    if op == "var":
        return node[1]
    if op == "const":
        return str(node[1])
    a, b = node[1]
    return f"({render(eg, best, a)} {op} {render(eg, best, b)})"


def main():
    """Run the three extractions on the saturated ISW e-graph and compare them.

    Algorithm, step by step:
      1. Build the ISW AND in an e-graph and saturate it with the FULL rules
         (including the leak-causing factoring rule).
      2. Report the original ISW circuit as the reference.
      3. Unconstrained extraction: pick the cheapest nodes, ignoring security,
         and report it (expected: cheaper and insecure).
      4. Label every class safe or unsafe with `class_safety`.
      5. Constrained extraction: cheapest nodes using only safe classes
         internally (`extract_constrained`), outputs chosen with `root_choices`,
         then built with `materialize_constrained`. Report it (expected: secure).
      6. Check the constrained circuit still computes the ISW function.
      7. Print the labels, a few unsafe classes (these are the wires that expose
         the secret), and the price of security in gates.
    """
    eg, c0, c1 = build_isw_egraph()  # the ISW gadget as an e-graph; c0, c1 = outputs
    saturate(eg, RULES_FULL)  # all rules, including the leak-causing factoring rule
    roots = [eg.find(c0), eg.find(c1)]  # canonical ids of the two output classes
    print(
        f"e-graph after saturation: {eg.num_classes()} classes, "
        f"{eg.num_nodes()} nodes\n"
    )

    print("extractions:")
    describe("1. original ISW AND", build_isw_and(), SECRET_GROUPS_AND, FREE_AND)

    best_u, _ = extract(eg)  # best_u: class -> cheapest node, ignoring security
    out_u = Circuit()  # the unconstrained circuit
    materialize(eg, best_u, roots, out_u)
    bad_u = describe("2. unconstrained (cost-only)", out_u, SECRET_GROUPS_AND, FREE_AND)

    # class id -> True/False; "r" is the only fresh random (first shares are added)
    safety = class_safety(eg, SECRET_GROUPS_AND, ["r"])
    best_i, cost_i = extract_constrained(eg, safety)  # best/cost over SAFE classes
    choices = root_choices(eg, cost_i, roots)  # chosen node for each output class
    out_c = Circuit()  # the constrained circuit
    materialize_constrained(eg, best_i, choices, roots, out_c)
    bad_c = describe("3. security-constrained", out_c, SECRET_GROUPS_AND, FREE_AND)

    # `ok_c, *_` keeps only the first result (True/False: same function as ISW)
    ok_c, *_ = equivalent(build_isw_and(), out_c, INPUTS)
    print(f"\n  constrained output functionally equivalent to ISW: {ok_c}")

    n_safe = sum(1 for v in safety.values() if v)  # how many classes are labelled safe
    print(f"\nsafety labels: {n_safe}/{len(safety)} classes safe")
    print("unsafe classes (function depends on a secret):")
    shown = 0  # how many unsafe classes printed so far (capped at 6 below)
    # sort by the id's text so the printed order is stable between runs
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
