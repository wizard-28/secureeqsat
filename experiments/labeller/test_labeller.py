"""Agreement tests: the bitsliced labeller must reproduce the reference checker.

The reference is `masked.check_first_order` (itself cross-validated against
VerifMSI, design/0005) and, on e-graphs, `constrained.class_safety_reference`.
Any disagreement on any wire or class is a failure. The labeller is also
cross-checked against VerifMSI directly (RULE 1b in
experiments/oracle_crosscheck/crosscheck.py).

Purpose
-------
The labeller is a re-implementation for speed, so the only thing that matters is
that it gives the SAME answers as the slow, trusted checker. These tests check that
on the hand fixtures, on 300 random circuits, and on saturated e-graphs, and they
also check that it catches unsound merges and rejects malformed input.
Run with: uv run pytest experiments/labeller -q
"""

import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "constrained_extraction"))

from constrained import class_safety, class_safety_reference  # noqa: E402
from egraph import RULES_CORE, RULES_FULL, saturate  # noqa: E402
from labeller import (  # noqa: E402
    InconsistentClassError,
    TruthSpace,
    check_first_order_bitsliced,
    class_safety_bitsliced,
    class_tables,
)
from masked import (  # noqa: E402
    FREE_AND,
    FREE_BUF,
    SECRET_GROUPS_AND,
    SECRET_GROUPS_BUF,
    Circuit,
    build_dom_and,
    build_isw_and,
    build_isw_and_wrong_order,
    build_masked_buffer,
    build_naive_unmasked_intermediate,
    check_first_order,
)
from run import build_isw_egraph  # noqa: E402

# (label, builder, secret groups, free variables, expected: is every wire secure?)
FIXTURES = [
    ("isw", build_isw_and, SECRET_GROUPS_AND, FREE_AND, True),
    ("isw_wrong_order", build_isw_and_wrong_order, SECRET_GROUPS_AND, FREE_AND, False),
    ("dom", build_dom_and, SECRET_GROUPS_AND, FREE_AND, True),
    ("naive", build_naive_unmasked_intermediate, SECRET_GROUPS_AND, FREE_AND, False),
    ("buffer", build_masked_buffer, SECRET_GROUPS_BUF, FREE_BUF, True),
]


# ---- circuits ----------------------------------------------------------


@pytest.mark.parametrize(
    "build,secrets,free,secure",
    [f[1:] for f in FIXTURES],  # drop the label; it is used for the test ids below
    ids=[f[0] for f in FIXTURES],
)
def test_fixture_verdicts_match_reference(build, secrets, free, secure):
    """On each hand fixture the fast labeller equals the reference checker.

    It also confirms the fixture's known verdict (secure or insecure), so the test
    does not depend on the reference alone.
    """
    circ = build()
    ours = check_first_order_bitsliced(circ, secrets, free)
    assert ours == check_first_order(circ, secrets, free)
    # Independently of the reference: the known-good/known-bad label holds.
    # `all(...)` is True only if every wire is safe; `is secure` compares to the label
    assert all(ours.values()) is secure


def _random_circuit(rng, secrets, randoms, gates):
    """Random AND/XOR circuit over the secret shares and randoms (maybe a constant).

    With probability 0.3 a constant wire is added to the pool, so the constant paths
    of both checkers are exercised too.
    """
    c = Circuit()
    pool = [c.add_input(x) for shares in secrets.values() for x in shares]
    pool += [c.add_input(r) for r in randoms]
    if rng.random() < 0.3:  # about 30% of circuits contain a constant
        pool.append(c.add_const(rng.randint(0, 1)))
    for _ in range(gates):
        op = rng.choice(["and", "xor", "xor"])  # XOR twice as likely as AND
        pool.append(c.add_gate(op, rng.choice(pool), rng.choice(pool)))
    return c


def test_random_circuits_match_reference():
    """300 random circuits: the two checkers agree on every single wire.

    The comparison is made non-vacuous at the end: the circuits must contain plenty
    of both secure and insecure wires, otherwise "they agree" would mean little.
    """
    rng = random.Random(20261007)  # fixed seed: the same 300 circuits every run
    wires = unsafe = 0  # running totals across all circuits
    for _ in range(300):
        n_secrets = rng.randint(1, 3)  # 1 to 3 secrets
        secrets = {f"s{i}": [f"s{i}_0", f"s{i}_1"] for i in range(n_secrets)}
        randoms = [f"r{i}" for i in range(rng.randint(0, 3))]  # 0 to 3 randoms
        free = [shares[0] for shares in secrets.values()] + randoms
        circ = _random_circuit(rng, secrets, randoms, rng.randint(3, 14))
        ref = check_first_order(circ, secrets, free)  # trusted reference
        ours = check_first_order_bitsliced(circ, secrets, free)  # fast labeller
        assert ours == ref, f"disagreement on circuit {circ.wires}"
        wires += len(ref)
        unsafe += sum(not ok for ok in ref.values())  # counts wires marked unsafe
    # The comparison must not be vacuous: both verdicts occur in quantity.
    assert unsafe > 100
    assert wires - unsafe > 1000


# ---- e-graphs ----------------------------------------------------------


@pytest.mark.parametrize("rules", [RULES_CORE, RULES_FULL], ids=["core", "full"])
def test_egraph_labels_match_class_safety(rules):
    """On a saturated ISW e-graph the fast labels equal the reference labels.

    Also checks that `constrained.class_safety` really delegates to the fast
    labeller, and that the labels are mixed (some safe, some unsafe).
    """
    eg, _c0, _c1 = build_isw_egraph()  # `_c0`, `_c1`: output classes, unused here
    saturate(eg, rules)
    randoms = ["r"]
    ref = class_safety_reference(eg, SECRET_GROUPS_AND, randoms)
    ours = class_safety_bitsliced(eg, SECRET_GROUPS_AND, randoms)
    assert ours == ref
    # constrained.class_safety is wired to the bitsliced labeller.
    assert class_safety(eg, SECRET_GROUPS_AND, randoms) == ref
    assert any(ours.values())  # at least one safe class
    assert not all(ours.values())  # and at least one unsafe class


def test_chain_egraph_labels_match_reference():
    """Two chained ISW gadgets (3 secrets, 2 randoms), core rules."""
    from measure import build_chain

    eg, secrets, randoms = build_chain(2)  # chain of depth 2
    saturate(eg, RULES_CORE)
    ref = class_safety_reference(eg, secrets, randoms)
    assert class_safety_bitsliced(eg, secrets, randoms) == ref
    assert any(ref.values())
    assert not all(ref.values())


def test_full_rules_expose_the_unmasked_secret_class():
    """The refolded `b0 ^ b1` (the secret b) is a class, and it is unsafe.

    Algorithm: build the truth table of the secret b as `b0 ^ b1` (one bitwise XOR of
    the two share tables), find the class whose table equals it after saturation with
    the full rules, and check that exactly one such class exists and is unsafe. This
    is the leaking wire of the core finding.
    """
    eg, _c0, _c1 = build_isw_egraph()
    saturate(eg, RULES_FULL)
    space = TruthSpace(SECRET_GROUPS_AND, FREE_AND)
    secret_b = space.var("b0") ^ space.var("b1")  # table of the secret b itself
    tables = class_tables(eg, space)
    matches = [c for c, t in tables.items() if t == secret_b]
    assert len(matches) == 1  # exactly one class computes the secret b
    assert class_safety_bitsliced(eg, SECRET_GROUPS_AND, ["r"])[matches[0]] is False


def test_unsound_merge_is_detected():
    """Merging two different functions makes `class_tables` raise an error."""
    eg, _c0, _c1 = build_isw_egraph()
    saturate(eg, RULES_CORE)
    eg.merge(eg.add_var("a0"), eg.add_var("a1"))  # a0 == a1 is false
    space = TruthSpace(SECRET_GROUPS_AND, FREE_AND)
    with pytest.raises(InconsistentClassError):
        class_tables(eg, space)


# ---- input validation ----------------------------------------------------


def test_unknown_input_is_rejected():
    """An input that is neither a free variable nor a share is a clear error."""
    c = Circuit()
    c.add_input("mystery")
    with pytest.raises(ValueError, match="mystery"):
        check_first_order_bitsliced(c, SECRET_GROUPS_AND, FREE_AND)


def test_reconstructed_share_listed_as_free_is_rejected():
    """A share derived from share 0 must not also be listed as a free variable."""
    with pytest.raises(ValueError, match="a1"):
        TruthSpace(SECRET_GROUPS_AND, FREE_AND + ["a1"])


def test_oversized_space_is_refused():
    """A space bigger than 2**26 points is refused instead of exhausting memory."""
    randoms = [f"r{i}" for i in range(30)]  # 30 randoms plus 2 secrets: far over 26
    with pytest.raises(ValueError, match="too much memory"):
        TruthSpace(SECRET_GROUPS_AND, ["a0", "b0", *randoms])
