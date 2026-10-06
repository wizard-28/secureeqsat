"""Premise test for the SecureEqSat project.

Question: does unrestricted Boolean equality saturation + cost-minimal
extraction actually turn a secure masked circuit into a functionally
equivalent but probing-insecure one?

Run from this directory:  python3 run.py
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
    bad = unsafe_wires(safe_map)
    return "SECURE" if not bad else f"INSECURE ({len(bad)} unsafe wires)"


def build_isw_egraph():
    eg = EGraph()
    a0 = eg.add_var("a0")
    a1 = eg.add_var("a1")
    b0 = eg.add_var("b0")
    b1 = eg.add_var("b1")
    r = eg.add_var("r")
    p1 = eg.add_and(a0, b0)
    c0 = eg.add_xor(p1, r)
    p2 = eg.add_and(a0, b1)
    p3 = eg.add_and(a1, b0)
    p4 = eg.add_and(a1, b1)
    w1 = eg.add_xor(r, p2)
    w2 = eg.add_xor(w1, p3)
    c1 = eg.add_xor(w2, p4)
    return eg, c0, c1


def equivalent(orig, extracted, inputs):
    for bits in range(1 << len(inputs)):
        ass = {v: (bits >> i) & 1 for i, v in enumerate(inputs)}
        vo = evaluate_safe(orig, ass)
        ve = evaluate_safe(extracted, ass)
        oo = tuple(vo[o] for o in orig.outputs)
        oe = tuple(ve[o] for o in extracted.outputs)
        if oo != oe:
            return False, ass, oo, oe
    return True, None, None, None


def evaluate_safe(circ, ass):
    from masked import evaluate

    missing = [n for n in circ.inputs if n not in ass]
    if missing:
        raise KeyError(f"missing inputs: {missing!r}")
    return evaluate(circ, dict(ass))


def run_case(label, rules, eg, c0, c1):
    t0 = time.time()
    iters, saturated, hit_limit = saturate(eg, rules)
    t_sat = time.time() - t0
    best, cost = extract(eg)
    roots = [eg.find(c0), eg.find(c1)]
    out = Circuit()
    try:
        materialize(eg, best, roots, out)
    except Exception as e:  # noqa
        print(f"[{label}] extraction failed: {e}")
        return None
    safe = check_first_order(out, SECRET_GROUPS_AND, FREE_AND)
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
    bad = unsafe_wires(safe)
    if bad:
        print(f"  unsafe wires ({len(bad)}):")
        for w in bad[:12]:
            print(f"    - {w}")
    print()
    return out


def main():
    print("=" * 72)
    print("STEP 1 - validate the first-order checker on known fixtures")
    print("=" * 72)
    buf = build_masked_buffer()
    sb = check_first_order(buf, SECRET_GROUPS_BUF, FREE_BUF)
    print(f"  masked buffer (a0^r, a1^r):        {fmt_safe(sb)}")

    isw = build_isw_and()
    si = check_first_order(isw, SECRET_GROUPS_AND, FREE_AND)
    print(f"  ISW masked AND:                    {fmt_safe(si)}")
    if unsafe_wires(si):
        print(f"    (unexpected) unsafe: {unsafe_wires(si)!r}")

    naive = build_naive_unmasked_intermediate()
    sn = check_first_order(naive, SECRET_GROUPS_AND, FREE_AND)
    print(f"  naive unmasked-intermediate AND:   {fmt_safe(sn)}")
    if unsafe_wires(sn):
        print(f"    unsafe: {unsafe_wires(sn)!r}")
    print()

    print("=" * 72)
    print("STEP 2 - unconstrained equality saturation of ISW AND")
    print("=" * 72)
    eg, c0, c1 = build_isw_egraph()
    run_case("core rules (no distributivity/factoring)", RULES_CORE, eg, c0, c1)

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
    bad = unsafe_wires(check_first_order(out, SECRET_GROUPS_AND, FREE_AND))
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
