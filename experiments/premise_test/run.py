"""Premise test for the SecureEqSat project.

Question: does unrestricted Boolean equality saturation + cost-minimal
extraction actually turn a secure masked circuit into a functionally
equivalent but probing-insecure one?

Purpose
-------
This is the narrative script behind finding F1 (the core result of the project).
It runs two steps and prints a verdict:

  STEP 1  validate the security checker on fixtures whose answer is known
          (a secure masked buffer, the secure ISW AND, and a deliberately
          insecure naive AND). If the checker got these wrong, nothing after it
          would mean anything.
  STEP 2  saturate the secure ISW AND in an e-graph twice: with the CORE rules
          (which never refold shares) and with the FULL rules (which add
          distributivity and factoring). Extract the cheapest circuit each time,
          check it is still the same function, and check whether it is secure.

Expected outcome: the CORE run stays secure at 8 gates; the FULL run yields a
cheaper 7-gate circuit that LEAKS. That is the premise: cost-minimal extraction
selects the cheaper insecure circuit.

Run from this directory:  python3 run.py
(or, from the repo root:  uv run python experiments/premise_test/run.py)
"""

import time

from egraph import RULES_CORE, RULES_FULL, EGraph, extract, materialize, saturate
from masked import (
    FREE_AND,
    FREE_BUF,
    SECRET_GROUPS_AND,
    SECRET_GROUPS_BUF,
    Circuit,
    build_isw_and,
    build_masked_buffer,
    build_naive_unmasked_intermediate,
    check_first_order,
    unsafe_wires,
)


def fmt_safe(safe_map):
    """Format a checker result as "SECURE" or "INSECURE (n unsafe wires)"."""
    bad = unsafe_wires(safe_map)
    return "SECURE" if not bad else f"INSECURE ({len(bad)} unsafe wires)"


def build_isw_egraph():
    """Build the ISW masked AND directly inside a fresh e-graph.

    Mirrors `masked.build_isw_and` gate for gate (same XOR order, r folded in
    early) but creates e-classes instead of circuit wires.

    Returns `(egraph, c0, c1)` where c0 and c1 are the two output classes.
    """
    eg = EGraph()
    # each name below is an e-CLASS id (an integer), not a wire name
    a0 = eg.add_var("a0")  # class of input a0, e.g. 2
    a1 = eg.add_var("a1")
    b0 = eg.add_var("b0")
    b1 = eg.add_var("b1")
    r = eg.add_var("r")  # the fresh random bit
    p1 = eg.add_and(a0, b0)  # a0*b0
    c0 = eg.add_xor(p1, r)  # output class 0 = a0*b0 ^ r
    p2 = eg.add_and(a0, b1)  # cross products
    p3 = eg.add_and(a1, b0)
    p4 = eg.add_and(a1, b1)
    w1 = eg.add_xor(r, p2)  # r first, so every partial sum is masked
    w2 = eg.add_xor(w1, p3)
    c1 = eg.add_xor(w2, p4)  # output class 1
    return eg, c0, c1


def equivalent(orig, extracted, inputs):
    """Check two circuits compute the same outputs for EVERY input assignment.

    Args:
        orig: the original circuit.
        extracted: the circuit produced by extraction.
        inputs: the input names to enumerate.

    Returns `(True, None, None, None)` if they agree everywhere, otherwise
    `(False, assignment, orig_outputs, extracted_outputs)` for the first mismatch.
    This is how we know a rewrite did not change the function.

    Algorithm: for every one of the 2**len(inputs) bit patterns, run both circuits
    and compare the tuple of output values; stop at the first difference.
    """
    # `1 << n` is 2**n: loop over every bit pattern of the n inputs
    for bits in range(1 << len(inputs)):
        # `(bits >> i) & 1` extracts bit i of the pattern, e.g. bits=0b101 with
        # inputs [a0, a1, b0] gives {"a0": 1, "a1": 0, "b0": 1}
        ass = {v: (bits >> i) & 1 for i, v in enumerate(inputs)}
        vo = evaluate_safe(orig, ass)  # every wire of the original circuit
        ve = evaluate_safe(extracted, ass)  # every wire of the extracted circuit
        oo = tuple(vo[o] for o in orig.outputs)  # original outputs, e.g. (True, False)
        oe = tuple(ve[o] for o in extracted.outputs)  # extracted outputs
        if oo != oe:  # a single differing output means the rewrite changed the function
            return False, ass, oo, oe
    return True, None, None, None


def evaluate_safe(circ, ass):
    """Evaluate `circ` on `ass`, raising a clear error if an input is missing."""
    from masked import evaluate

    missing = [n for n in circ.inputs if n not in ass]  # inputs with no value given
    if missing:
        raise KeyError(f"missing inputs: {missing!r}")
    return evaluate(circ, dict(ass))


def run_case(label, rules, eg, c0, c1):
    """Saturate with `rules`, extract, then report cost, equivalence and security.

    Args:
        label: text for the report header.
        rules: the rule list (CORE or FULL).
        eg, c0, c1: the e-graph and its two output classes.

    Returns the extracted `Circuit`, or None if extraction failed.

    Algorithm, step by step:
      1. SATURATE: apply the rules until nothing new appears (or a limit is hit).
      2. EXTRACT: pick the cheapest node in every class (cost only, no security).
      3. MATERIALIZE: turn the chosen nodes for the two output classes into a
         real circuit.
      4. CHECK: run the security checker on that circuit, and check by brute force
         that it still computes the same outputs as the original ISW gadget.
      5. REPORT: print saturation statistics, gate counts, equivalence, the
         security verdict, and up to 12 unsafe wires.
    """
    t0 = time.time()  # start time in seconds, for timing saturation
    # iters = rounds run, saturated = reached a fixed point, hit_limit = stopped early
    iters, saturated, hit_limit = saturate(eg, rules)
    t_sat = time.time() - t0  # seconds spent saturating
    best, cost = extract(eg)  # best: class -> chosen node; cost: class -> its cost
    roots = [eg.find(c0), eg.find(c1)]  # the two output classes (canonical ids)
    out = Circuit()  # will hold the extracted circuit
    try:
        materialize(eg, best, roots, out)
    except Exception as e:  # noqa
        print(f"[{label}] extraction failed: {e}")
        return None
    # The two questions that matter: is it secure, and is it the same function?
    safe = check_first_order(out, SECRET_GROUPS_AND, FREE_AND)  # {wire: True/False}
    # `ok, *_` keeps the first return value (True/False) and ignores the rest
    ok, *_ = equivalent(build_isw_and(), out, ["a0", "a1", "b0", "b1", "r"])
    print(f"[{label}]")
    print(
        f"  saturation: {iters} iters, saturated={saturated}, "
        f"hit_limit={hit_limit}, {t_sat:.2f}s"
    )
    print(f"  e-graph: {eg.num_classes()} classes, {eg.num_nodes()} nodes")
    print(
        f"  extracted: {out.and_count()} AND, {out.xor_count()} XOR, "
        f"{out.gate_count()} gates total"
    )
    print(f"  functionally equivalent to ISW AND: {ok}")
    print(f"  security: {fmt_safe(safe)}")
    bad = unsafe_wires(safe)  # names of leaking wires, e.g. ["xor(b1,b0)"]
    if bad:
        print(f"  unsafe wires ({len(bad)}):")
        for w in bad[:12]:  # show at most the first 12
            print(f"    - {w}")
    print()
    return out


def main():
    """Run STEP 1 (validate the checker), STEP 2 (core vs full rules), then verdict."""
    print("=" * 72)
    print("STEP 1 - validate the first-order checker on known fixtures")
    print("=" * 72)
    buf = build_masked_buffer()  # fixture: expected secure
    sb = check_first_order(buf, SECRET_GROUPS_BUF, FREE_BUF)  # sb = buffer's verdicts
    print(f"  masked buffer (a0^r, a1^r):        {fmt_safe(sb)}")

    isw = build_isw_and()  # fixture: expected secure
    si = check_first_order(isw, SECRET_GROUPS_AND, FREE_AND)  # si = ISW's verdicts
    print(f"  ISW masked AND:                    {fmt_safe(si)}")
    if unsafe_wires(si):
        print(f"    (unexpected) unsafe: {unsafe_wires(si)!r}")

    naive = build_naive_unmasked_intermediate()  # fixture: expected INSECURE
    sn = check_first_order(naive, SECRET_GROUPS_AND, FREE_AND)  # sn = naive verdicts
    print(f"  naive unmasked-intermediate AND:   {fmt_safe(sn)}")
    if unsafe_wires(sn):
        print(f"    unsafe: {unsafe_wires(sn)!r}")
    print()

    print("=" * 72)
    print("STEP 2 - unconstrained equality saturation of ISW AND")
    print("=" * 72)
    eg, c0, c1 = build_isw_egraph()  # c0, c1: output classes of this e-graph
    run_case("core rules (no distributivity/factoring)", RULES_CORE, eg, c0, c1)

    # a second, separate e-graph so the FULL run starts from the same fresh state
    eg2, d0, d1 = build_isw_egraph()
    out = run_case(
        "full rules (with distributivity/factoring)", RULES_FULL, eg2, d0, d1
    )

    print("=" * 72)
    print("VERDICT")
    print("=" * 72)
    if out is None:
        print("  Extraction failed; premise inconclusive (see error above).")
        return
    # `bad` is the list of leaking wires; empty means the extracted circuit is secure
    bad = unsafe_wires(check_first_order(out, SECRET_GROUPS_AND, FREE_AND))
    # `ok` is True when the extracted circuit computes the same function as ISW
    ok, _, _, _ = equivalent(build_isw_and(), out, ["a0", "a1", "b0", "b1", "r"])
    if ok and bad:
        print(
            "  PREMISE HOLDS: unconstrained rewriting produced a"
            " functionally equivalent but INSECURE circuit."
        )
        print(
            "  The cost-optimal extraction introduced the unmasked-secret"
            " wire(s) listed above."
        )
    elif ok and not bad:
        print(
            "  PREMISE NOT DEMONSTRATED on this fixture: extracted circuit"
            " stayed secure."
        )
    else:
        print(
            "  Unexpected: extracted circuit is not functionally equivalent"
            " (rule or extraction bug)."
        )


if __name__ == "__main__":
    main()
