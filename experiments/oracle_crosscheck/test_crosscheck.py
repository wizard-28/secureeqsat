"""Cross-check tests — skipped when the external VerifMSI oracle is absent.

The oracle is GPLv3 and lives outside this repository, so these tests are
opt-in by environment presence rather than by a flag:

    bash experiments/oracle_crosscheck/setup_oracles.sh

Purpose
-------
These tests run the cross-check from `crosscheck.py` as part of the normal suite: the
hand fixtures, the 24 re-orderings of ISW, and 25 random circuits. They fail if our
checkers and VerifMSI ever disagree on a wire. A skip is NOT a pass: without
VerifMSI the trust boundary is unchecked (the test report says so).
"""

import pytest
from crosscheck import (
    SECRETS_AB,
    compare,
    fixture_cases,
    isw_reassociation_variants,
    oracle_available,
)

# Applied to every test in this file: skip them all if VerifMSI is not installed.
pytestmark = pytest.mark.skipif(
    not oracle_available(),
    reason="VerifMSI oracle not set up (run setup_oracles.sh)",
)


def test_fixtures_agree_two_sided_and_meet_expectations():
    """On the five fixtures: no disagreement; each is secure/insecure as expected."""
    for label, circ, secrets, randoms, expected in fixture_cases():
        r = compare(circ, secrets, randoms)
        assert not r["violations"], (label, r["violations"])
        # the circuit is "all secure" when every wire is safe; compare with the label
        assert (r["safe_wires"] == r["n_wires"]) == expected, label


def test_isw_reassociation_family_agrees_and_straddles_the_boundary():
    """All 24 XOR orderings of ISW agree with VerifMSI, and include both verdicts."""
    variants = isw_reassociation_variants()
    assert len(variants) == 24  # 4! orderings of the four terms
    verdicts = set()  # which overall verdicts appeared (True = secure)
    for label, circ in variants:
        r = compare(circ, SECRETS_AB, ["r"])
        assert not r["violations"], (label, r["violations"])
        verdicts.add(r["safe_wires"] == r["n_wires"])
    # Guards against the family silently becoming all-secure or all-insecure,
    # which would make this test vacuous.
    assert verdicts == {True, False}, "family must straddle the boundary"


def test_random_circuits_agree():
    """25 seeded random circuits: no disagreement on any wire."""
    import random

    from crosscheck import random_circuit

    rng = random.Random(0)  # fixed seed: reproducible circuits
    for i in range(25):
        circ, randoms = random_circuit(rng, n_randoms=3, n_gates=10)
        r = compare(circ, SECRETS_AB, randoms)
        assert not r["violations"], (f"random_{i}", r["violations"])
