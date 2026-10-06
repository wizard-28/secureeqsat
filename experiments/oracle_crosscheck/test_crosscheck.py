"""Cross-check tests — skipped when the external VerifMSI oracle is absent.

The oracle is GPLv3 and lives outside this repository, so these tests are
opt-in by environment presence rather than by a flag:

    bash experiments/oracle_crosscheck/setup_oracles.sh
"""

import pytest
from crosscheck import (
    SECRETS_AB,
    compare,
    fixture_cases,
    isw_reassociation_variants,
    oracle_available,
)

pytestmark = pytest.mark.skipif(
    not oracle_available(),
    reason="VerifMSI oracle not set up (run setup_oracles.sh)",
)


def test_fixtures_agree_two_sided_and_meet_expectations():
    for label, circ, secrets, randoms, expected in fixture_cases():
        r = compare(circ, secrets, randoms)
        assert not r["violations"], (label, r["violations"])
        assert (r["safe_wires"] == r["n_wires"]) == expected, label


def test_isw_reassociation_family_agrees_and_straddles_the_boundary():
    variants = isw_reassociation_variants()
    assert len(variants) == 24
    verdicts = set()
    for label, circ in variants:
        r = compare(circ, SECRETS_AB, ["r"])
        assert not r["violations"], (label, r["violations"])
        verdicts.add(r["safe_wires"] == r["n_wires"])
    # Guards against the family silently becoming all-secure or all-insecure,
    # which would make this test vacuous.
    assert verdicts == {True, False}, "family must straddle the boundary"


def test_random_circuits_agree():
    import random

    from crosscheck import random_circuit

    rng = random.Random(0)
    for i in range(25):
        circ, randoms = random_circuit(rng, n_randoms=3, n_gates=10)
        r = compare(circ, SECRETS_AB, randoms)
        assert not r["violations"], (f"random_{i}", r["violations"])
