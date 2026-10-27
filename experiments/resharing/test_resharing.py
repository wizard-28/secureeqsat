"""Tests for the shared-value layer (design/0016).

The headline numbers in RESULTS.md are asserted here, so a regression in the
rules, the lowering or the extraction fails the suite rather than silently
changing a reported result.

Purpose
-------
The tests fall into four groups: (1) LOWERING: a lowered circuit reconstructs the
right value and its costs match the cost model; (2) the EGGLOG LAYER: export
format, refresh sharing a class with its operand, and value-soundness of all rules;
(3) HEADLINE RESULTS: each number reported in `RESULTS.md` (30->18, 20->11, 24->18,
square 11 leaks vs 14 secure, tight circuits unchanged); (4) the TRUST BOUNDARY:
the reported circuits agree with VerifMSI. Run with:
    uv run pytest experiments/resharing -q
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
from fixtures import FIXTURES, TIGHT, chi  # noqa: E402
from gadgets import (  # noqa: E402
    GADGETS,
    cost_of,
    lower,
    secrets_of,
    value,
)
from layer import export, saturate  # noqa: E402
from masked import evaluate  # noqa: E402

A, B, D = ("in", "a"), ("in", "b"), ("in", "d")  # secret input terms
Z = ("xor", A, B)  # a share-wise XOR of a and b

# A variety of small terms used to test lowering: leaves, wrappers, every gadget,
# gadgets fed the same sharing twice, nested gadgets, and all the fixtures.
SMALL_TERMS = [
    A,
    Z,
    ("refresh", A),
    ("not", A),
    ("isw", ("not", A), B),
    *[(g, A, B) for g in GADGETS],
    *[(g, A, A) for g in GADGETS],
    *[(g, (g, A, B), ("xor", A, D)) for g in GADGETS],
    *FIXTURES.values(),
]


def reconstructions(term):
    """Yield (secret env, list of reconstructed outputs) for every assignment.

    Lowers the term, then for every value of the secrets and every value of the free
    bits runs the circuit. For each output PAIR of shares it yields share0 ^ share1,
    the value that pair reconstructs to. Used to check lowered circuits compute the
    right function.
    """
    low = lower([term])
    names = secrets_of(term)
    # the free inputs: share 0 of each secret plus every fresh random
    inputs = [f"{s}0" for s in names] + low.randoms
    outs = low.circ.outputs  # output wires, two per root (share 0, share 1, ...)
    for svals in itertools.product((0, 1), repeat=len(names)):
        env = dict(zip(names, svals, strict=True))  # e.g. {"x0": 1, "x1": 0}
        for fvals in itertools.product((0, 1), repeat=len(inputs)):
            ass = dict(zip(inputs, fvals, strict=True))
            for s in names:
                ass[f"{s}1"] = ass[f"{s}0"] ^ env[s]  # share 1 = share 0 ^ secret
            vals = evaluate(low.circ, ass)
            yield (
                env,
                # step through the outputs two at a time and XOR each pair of shares
                [vals[outs[i]] ^ vals[outs[i + 1]] for i in range(0, len(outs), 2)],
            )


def leaks(term):
    """The list of leaking wires of `term`'s lowered circuit ([] means secure)."""
    return Evaluator()(term)[1]


def best(term, rules, secure, k=8):
    """Best (cost, term) for `term` after saturating with `rules`.

    `rules` is a tuple of rule-class names, `secure` selects the constrained
    extraction. Returns the `(cost, term)` pair, or None if nothing qualifies.
    """
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
        want = value(term, env)  # the unmasked value the term should compute
        for fvals in itertools.product((0, 1), repeat=len(inputs)):
            ass = dict(zip(inputs, fvals, strict=True))
            for s in names:
                ass[f"{s}1"] = ass[f"{s}0"] ^ env[s]
            vals = evaluate(low.circ, ass)
            s0, s1 = low.circ.outputs  # the two output shares
            assert vals[s0] ^ vals[s1] == want


@pytest.mark.parametrize("op", ["xor", "refresh", "not", *GADGETS])
def test_own_cost_matches_lowering(op):
    """OWN_COST feeds the extraction lower bound; it must equal the lowering."""
    term = (op, A) if op in ("refresh", "not") else (op, A, B)
    assert cost_of(lower([term])) == OWN_COST[op]


def test_gadgets_secure_on_independent_inputs():
    """Each AND gadget is secure when its operands are independent sharings."""
    for g in GADGETS:
        assert not leaks((g, A, B)), g


def test_same_sharing_on_both_operands_leaks_without_refresh():
    """Feeding one sharing into both operands leaks, unless one is refreshed."""
    for g in ("isw", "dom"):
        assert leaks((g, A, A)), g  # same sharing twice: leaks
        assert not leaks((g, A, ("refresh", A))), g  # refreshed copy: secure
    assert not leaks(("hpc1", A, A))  # HPC1 refreshes its second operand itself


def test_leaking_subterm_leaks_in_context():
    """The cut used by constrained extraction: leaks are monotone in context."""
    inner = ("isw", Z, Z)  # a leaking subterm
    assert leaks(inner)
    for outer in (("xor", inner, D), ("isw", inner, D), ("dom", D, inner)):
        assert leaks(outer)  # wrapping it in more logic does not hide the leak


# ---- egglog layer -----------------------------------------------------


def test_export_format_guard():
    """Fails loudly if egglog's private serializer changes shape."""
    eg, _ = saturate(("isw", A, ("refresh", B)), (), 1)  # no rules: the term as given
    classes, root = export(eg)
    assert len(classes) == 4  # classes for a, b, refresh(b) and the isw
    assert [n[0] for n in classes[root]] == ["isw"]  # the root holds one isw node
    leaves = sorted(n for nodes in classes.values() for n in nodes if n[0] == "in")
    assert leaves == [("in", "a"), ("in", "b")]


def test_r3_puts_refresh_and_operand_in_one_class():
    """After R3, `refresh(b)` and `b` share a class (the refresh self-loop)."""
    eg, _ = saturate(("isw", A, ("refresh", B)), ("R3",), 4)
    classes, _ = export(eg)
    for c, nodes in classes.items():
        if ("in", "b") in nodes:
            assert ("refresh", (c,)) in nodes  # refresh of class c is inside class c


def test_all_rules_are_value_sound_on_every_fixture():
    """kbest raises InconsistentClassError if any term breaks its class value."""
    for term in FIXTURES.values():
        eg, _ = saturate(term, ("R1", "R2", "R3"), 6)
        classes, root = export(eg)
        assert kbest(classes, root, k=8, secure=False)[0] is not None


def test_inconsistent_class_is_detected():
    """A class holding both a&b and a^b (different values) must raise an error."""
    classes = {
        "x": [("in", "a")],
        "y": [("in", "b")],
        "root": [("isw", ("x", "y")), ("xor", ("x", "y"))],  # a&b merged with a^b
    }
    with pytest.raises(InconsistentClassError):
        kbest(classes, "root", secure=False)


# ---- headline results (RESULTS.md) -------------------------------------


def test_chain_control_has_no_gain():
    """The hand-written chain stays at cost 18, with and without all rules."""
    for rules in ((), ("R1", "R2", "R3")):
        cost, term = best(FIXTURES["chain"], rules, secure=True)
        assert cost == 18 and not leaks(term)


def test_refresh_removal_on_overrefreshed_chain():
    """Without rules the over-refreshed chain costs 30; R3 brings it to 18, secure."""
    assert best(FIXTURES["overrefreshed"], (), secure=True)[0] == 30
    cost, term = best(FIXTURES["overrefreshed"], ("R3",), secure=True)
    assert cost == 18 and not leaks(term)


def test_square_unconstrained_prefers_the_leak_constrained_keeps_refresh():
    """The square: cost 11 leaks (refresh dropped), cost 14 is the secure answer."""
    cost_u, term_u = best(FIXTURES["square"], ("R3",), secure=False)
    assert cost_u == 11 and leaks(term_u)
    cost_c, term_c = best(FIXTURES["square"], ("R3",), secure=True)
    assert cost_c == 14 and not leaks(term_c)


def test_factoring_is_secure_at_the_value_layer():
    """`a&b ^ a&d` goes from 20 to 11 by factoring, and the result is secure."""
    assert best(FIXTURES["factor"], (), secure=True)[0] == 20
    cost, term = best(FIXTURES["factor"], ("R1",), secure=False)
    assert cost == 11 and not leaks(term)


def test_r2_swaps_hpc1_for_cheaper_gadgets():
    """R2 takes the HPC1 chain from 24 to 18 by swapping in a cheaper gadget."""
    cost, term = best(FIXTURES["hpc_chain"], ("R2",), secure=True)
    assert cost == 18 and "hpc1" not in repr(term)


def test_chi_lowering_computes_keccak_chi():
    """FIPS 202 sec. 3.2.4: y[x] = x[x] ^ ((x[x+1] ^ 1) & x[x+2])."""
    for env, ys in reconstructions(chi(3)):
        x = [env[f"x{i}"] for i in range(3)]  # the three input bits of the row
        # each output bit equals the specification's formula (indices wrap mod 3)
        assert ys == [x[i] ^ ((x[(i + 1) % 3] ^ 1) & x[(i + 2) % 3]) for i in range(3)]


@pytest.mark.parametrize("name", sorted(TIGHT))
def test_tight_chi_has_no_gain(name):
    """Keccak chi rows are already tight: no rule combination makes them cheaper."""
    start = Evaluator()(TIGHT[name])  # (cost, leaks) of the starting circuit
    assert not start[1]  # the start is secure
    for rules in ((), ("R1", "R2", "R3")):
        for secure in (False, True):
            cost, term = best(TIGHT[name], rules, secure=secure)
            assert cost == start[0] and not leaks(term)  # same cost, still secure


# ---- trust boundary ---------------------------------------------------


def test_reported_circuits_agree_with_verifmsi():
    """Every circuit the experiments report is confirmed by VerifMSI (if installed)."""
    crosscheck = pytest.importorskip("crosscheck")
    if not crosscheck.oracle_available():
        pytest.skip("VerifMSI oracle not installed")
    from gadgets import secret_groups

    terms = set(FIXTURES.values())  # start with the fixtures themselves
    for rules in ((), ("R3",), ("R1", "R2", "R3")):
        for term in FIXTURES.values():
            for secure in (False, True):
                terms.add(best(term, rules, secure)[1])  # add each best term found
    for term in terms:
        low = lower([term])
        out = crosscheck.compare(low.circ, secret_groups(secrets_of(term)), low.randoms)
        assert out["violations"] == [], term  # no disagreement with VerifMSI
