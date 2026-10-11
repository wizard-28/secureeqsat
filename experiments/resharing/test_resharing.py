"""Tests for the shared-value layer (design/0016).

The headline numbers in RESULTS.md are asserted here, so a regression in the
rules, the lowering or the extraction fails the suite rather than silently
changing a reported result.
"""

import itertools
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "experiments" / "labeller"))

from extract import OWN_COST, Evaluator, InconsistentClassError, kbest  # noqa: E402
from fixtures import FIXTURES  # noqa: E402
from gadgets import (  # noqa: E402
    GADGETS,
    cost_of,
    lower,
    secrets_of,
    value,
)
from layer import export, saturate  # noqa: E402
from masked import evaluate  # noqa: E402

A, B, D = ("in", "a"), ("in", "b"), ("in", "d")
Z = ("xor", A, B)

SMALL_TERMS = [
    A,
    Z,
    ("refresh", A),
    *[(g, A, B) for g in GADGETS],
    *[(g, A, A) for g in GADGETS],
    *[(g, (g, A, B), ("xor", A, D)) for g in GADGETS],
    *FIXTURES.values(),
]


def leaks(term):
    return Evaluator()(term)[1]


def best(term, rules, secure, k=8):
    eg, _ = saturate(term, rules, 6)
    classes, root = export(eg)
    return kbest(classes, root, k=k, secure=secure)[0]


# ---- lowering ---------------------------------------------------------


@pytest.mark.parametrize("term", SMALL_TERMS, ids=repr)
def test_lowering_reconstructs_the_value(term):
    """share0 ^ share1 equals the term's value for every input assignment."""
    low = lower([term])
    names = secrets_of(term)
    inputs = [f"{s}0" for s in names] + low.randoms
    for svals in itertools.product((0, 1), repeat=len(names)):
        env = dict(zip(names, svals, strict=True))
        want = value(term, env)
        for fvals in itertools.product((0, 1), repeat=len(inputs)):
            ass = dict(zip(inputs, fvals, strict=True))
            for s in names:
                ass[f"{s}1"] = ass[f"{s}0"] ^ env[s]
            vals = evaluate(low.circ, ass)
            s0, s1 = low.circ.outputs
            assert vals[s0] ^ vals[s1] == want


@pytest.mark.parametrize("op", ["xor", "refresh", *GADGETS])
def test_own_cost_matches_lowering(op):
    """OWN_COST feeds the extraction lower bound; it must equal the lowering."""
    term = ("refresh", A) if op == "refresh" else (op, A, B)
    assert cost_of(lower([term])) == OWN_COST[op]


def test_gadgets_secure_on_independent_inputs():
    for g in GADGETS:
        assert not leaks((g, A, B)), g


def test_same_sharing_on_both_operands_leaks_without_refresh():
    for g in ("isw", "dom"):
        assert leaks((g, A, A)), g
        assert not leaks((g, A, ("refresh", A))), g
    assert not leaks(("hpc1", A, A))  # HPC1 refreshes its second operand itself


def test_leaking_subterm_leaks_in_context():
    """The cut used by constrained extraction: leaks are monotone in context."""
    inner = ("isw", Z, Z)
    assert leaks(inner)
    for outer in (("xor", inner, D), ("isw", inner, D), ("dom", D, inner)):
        assert leaks(outer)


# ---- egglog layer -----------------------------------------------------


def test_export_format_guard():
    """Fails loudly if egglog's private serializer changes shape."""
    eg, _ = saturate(("isw", A, ("refresh", B)), (), 1)
    classes, root = export(eg)
    assert len(classes) == 4
    assert [n[0] for n in classes[root]] == ["isw"]
    leaves = sorted(n for nodes in classes.values() for n in nodes if n[0] == "in")
    assert leaves == [("in", "a"), ("in", "b")]


def test_r3_puts_refresh_and_operand_in_one_class():
    eg, _ = saturate(("isw", A, ("refresh", B)), ("R3",), 4)
    classes, _ = export(eg)
    for c, nodes in classes.items():
        if ("in", "b") in nodes:
            assert ("refresh", (c,)) in nodes


def test_all_rules_are_value_sound_on_every_fixture():
    """kbest raises InconsistentClassError if any term breaks its class value."""
    for term in FIXTURES.values():
        eg, _ = saturate(term, ("R1", "R2", "R3"), 6)
        classes, root = export(eg)
        assert kbest(classes, root, k=8, secure=False)[0] is not None


def test_inconsistent_class_is_detected():
    classes = {
        "x": [("in", "a")],
        "y": [("in", "b")],
        "root": [("isw", ("x", "y")), ("xor", ("x", "y"))],  # a&b merged with a^b
    }
    with pytest.raises(InconsistentClassError):
        kbest(classes, "root", secure=False)


# ---- headline results (RESULTS.md) -------------------------------------


def test_chain_control_has_no_gain():
    for rules in ((), ("R1", "R2", "R3")):
        cost, term = best(FIXTURES["chain"], rules, secure=True)
        assert cost == 18 and not leaks(term)


def test_refresh_removal_on_overrefreshed_chain():
    assert best(FIXTURES["overrefreshed"], (), secure=True)[0] == 30
    cost, term = best(FIXTURES["overrefreshed"], ("R3",), secure=True)
    assert cost == 18 and not leaks(term)


def test_square_unconstrained_prefers_the_leak_constrained_keeps_refresh():
    cost_u, term_u = best(FIXTURES["square"], ("R3",), secure=False)
    assert cost_u == 11 and leaks(term_u)
    cost_c, term_c = best(FIXTURES["square"], ("R3",), secure=True)
    assert cost_c == 14 and not leaks(term_c)


def test_factoring_is_secure_at_the_value_layer():
    assert best(FIXTURES["factor"], (), secure=True)[0] == 20
    cost, term = best(FIXTURES["factor"], ("R1",), secure=False)
    assert cost == 11 and not leaks(term)


def test_r2_swaps_hpc1_for_cheaper_gadgets():
    cost, term = best(FIXTURES["hpc_chain"], ("R2",), secure=True)
    assert cost == 18 and "hpc1" not in repr(term)


# ---- trust boundary ---------------------------------------------------


def test_reported_circuits_agree_with_verifmsi():
    crosscheck = pytest.importorskip("crosscheck")
    if not crosscheck.oracle_available():
        pytest.skip("VerifMSI oracle not installed")
    from gadgets import secret_groups

    terms = set(FIXTURES.values())
    for rules in ((), ("R3",), ("R1", "R2", "R3")):
        for term in FIXTURES.values():
            for secure in (False, True):
                terms.add(best(term, rules, secure)[1])
    for term in terms:
        low = lower([term])
        out = crosscheck.compare(low.circ, secret_groups(secrets_of(term)), low.randoms)
        assert out["violations"] == [], term
