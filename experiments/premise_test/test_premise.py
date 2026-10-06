"""Regression tests for the SecureEqSat premise test.

These lock in two things:

1. The first-order probing checker classifies known-secure and known-insecure
   masked circuits correctly (including the distribution-vs-sequence subtlety
   and the ISW XOR-ordering subtlety discovered while building it).
2. The project premise: unrestricted equality saturation + cost-minimal
   extraction yields a functionally equivalent but probing-INSECURE circuit,
   and the insecure circuit is cheaper than the secure one.
"""

from egraph import RULES_CORE, RULES_FULL, extract, materialize, saturate
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
from run import build_isw_egraph, equivalent

INPUTS = ["a0", "a1", "b0", "b1", "r"]


def _extract(eg, c0, c1):
    best, _cost = extract(eg)
    out = Circuit()
    materialize(eg, best, [eg.find(c0), eg.find(c1)], out)
    return out


def _build_isw_wrong_order():
    """ISW function with r folded in too late (an insecure circuit)."""
    c = Circuit()
    a0 = c.add_input("a0")
    a1 = c.add_input("a1")
    b0 = c.add_input("b0")
    b1 = c.add_input("b1")
    r = c.add_input("r")
    p1 = c.add_gate("and", a0, b0)
    c0 = c.add_gate("xor", p1, r)
    p2 = c.add_gate("and", a0, b1)
    p3 = c.add_gate("and", a1, b0)
    p4 = c.add_gate("and", a1, b1)
    t1 = c.add_gate("xor", p2, p3)
    t2 = c.add_gate("xor", t1, p4)
    c1 = c.add_gate("xor", t2, r)
    c.outputs = [c0, c1]
    return c


# ---- checker correctness ---------------------------------------------


def test_checker_accepts_secure_masked_buffer():
    safe = check_first_order(build_masked_buffer(), SECRET_GROUPS_BUF, FREE_BUF)
    assert not unsafe_wires(safe)


def test_checker_treats_permuted_uniform_wire_as_safe():
    """Regression: compare distributions, not value sequences.

    a1 = a0 ^ a permutes a0's assignment sequence across secret assignments
    but has an identical uniform distribution, so it must be judged safe.
    """
    safe = check_first_order(build_masked_buffer(), SECRET_GROUPS_BUF, FREE_BUF)
    assert safe["a1"] is True
    assert safe["xor(a0,r)"] is True
    assert safe["xor(a1,r)"] is True


def test_checker_accepts_isw_and():
    safe = check_first_order(build_isw_and(), SECRET_GROUPS_AND, FREE_AND)
    assert not unsafe_wires(safe)


def test_checker_rejects_unmasked_intermediate():
    circ = build_naive_unmasked_intermediate()
    safe = check_first_order(circ, SECRET_GROUPS_AND, FREE_AND)
    bad = set(unsafe_wires(safe))
    assert "xor(a0,a1)" in bad  # unmasked secret a
    assert "xor(b0,b1)" in bad  # unmasked secret b
    assert "and(xor(a0,a1),xor(b0,b1))" in bad  # unmasked a & b


def test_isw_security_depends_on_folding_random_early():
    """The same ISW function is secure or not depending on XOR ordering.

    Locked in because it is the structure-sensitivity argument the project
    relies on, and because the checker caught it as a fixture bug.
    """
    wrong = _build_isw_wrong_order()
    assert unsafe_wires(check_first_order(wrong, SECRET_GROUPS_AND, FREE_AND))

    right = build_isw_and()
    assert not unsafe_wires(check_first_order(right, SECRET_GROUPS_AND, FREE_AND))


# ---- premise ----------------------------------------------------------


def test_core_rules_keep_extraction_secure():
    eg, c0, c1 = build_isw_egraph()
    saturate(eg, RULES_CORE)
    out = _extract(eg, c0, c1)
    ok, *_ = equivalent(build_isw_and(), out, INPUTS)
    assert ok
    assert not unsafe_wires(check_first_order(out, SECRET_GROUPS_AND, FREE_AND))


def test_unrestricted_rules_produce_cheaper_insecure_circuit():
    """THE PREMISE: cost-minimal extraction admits insecure circuits."""
    eg, c0, c1 = build_isw_egraph()
    saturate(eg, RULES_FULL)
    out = _extract(eg, c0, c1)

    ok, *_ = equivalent(build_isw_and(), out, INPUTS)
    assert ok, "extraction must remain functionally correct"

    safe = check_first_order(out, SECRET_GROUPS_AND, FREE_AND)
    assert unsafe_wires(safe), (
        "premise: unrestricted EqSat must admit insecure extractions"
    )
    assert out.gate_count() < build_isw_and().gate_count(), (
        "and the insecure circuit must be cheaper, making the failure systematic"
    )
