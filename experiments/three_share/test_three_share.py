"""Tests for the d-share generalisation of Finding 1 (see shares.py, RESULTS.md)."""

import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shares import Gadget, analyse_output, isw_baseline_cost  # noqa: E402


def brute_safe(d, wire):
    """Independent re-check: `wire(a_sh, b_sh, r)` -> bit, by explicit enumeration."""
    pairs = [(i, j) for i in range(d) for j in range(i + 1, d)]
    counts = []
    for a, b in itertools.product((0, 1), repeat=2):
        ones = 0
        for fa in itertools.product((0, 1), repeat=d - 1):
            for fb in itertools.product((0, 1), repeat=d - 1):
                for rr in itertools.product((0, 1), repeat=len(pairs)):
                    ash = [*fa, a ^ (sum(fa) & 1)]
                    bsh = [*fb, b ^ (sum(fb) & 1)]
                    ones += wire(ash, bsh, dict(zip(pairs, rr, strict=True)))
        counts.append(ones)
    return len(set(counts)) == 1


def test_outputs_reconstruct_the_product():
    for d in (2, 3, 4):
        g = Gadget(d)
        acc = 0
        for i in range(d):
            for leaf in g.leaves(i):
                acc ^= g.fn(leaf)
        want = g.var["a0"]
        for k in range(1, d):
            want ^= g.var[f"a{k}"]
        wantb = g.var["b0"]
        for k in range(1, d):
            wantb ^= g.var[f"b{k}"]
        assert acc == want & wantb


def test_two_share_reproduces_the_paper_numbers():
    g = Gadget(2)
    rows = [analyse_output(g, i) for i in range(2)]
    assert isw_baseline_cost(2) == 8
    assert sum(r["min_any"] for r in rows) == 7  # cost-only: 7 gates
    assert sum(r["min_secure"] for r in rows) == 8  # constrained: 8 gates
    assert rows[1]["cheapest_all_leak"]


def test_recombined_xor_matches_independent_enumeration():
    for d in (2, 3):
        g = Gadget(d)
        x01 = g.var["b0"] ^ g.var["b1"]
        assert g.safe(x01) == brute_safe(d, lambda a, b, r: b[0] ^ b[1])
    # b0^b1 is the secret at d=2 (leaks) but a uniform bit at d=3 (safe)
    assert not Gadget(2).safe(Gadget(2).var["b0"] ^ Gadget(2).var["b1"])
    g3 = Gadget(3)
    assert g3.safe(g3.var["b0"] ^ g3.var["b1"])
    assert not g3.safe(g3.var["b0"] ^ g3.var["b1"] ^ g3.var["b2"])  # = b itself
    assert brute_safe(3, lambda a, b, r: a[2] & (b[0] ^ b[1]))  # partial factoring ok
    assert not brute_safe(3, lambda a, b, r: a[2] & (b[0] ^ b[1] ^ b[2]))


def test_three_and_four_shares_have_secure_savings_but_cost_only_still_leaks():
    for d, baseline, any_, sec in ((3, 21, 17, 18), (4, 40, 31, 32)):
        g = Gadget(d)
        rows = [analyse_output(g, i) for i in range(d)]
        assert isw_baseline_cost(d) == baseline
        assert sum(r["min_any"] for r in rows) == any_
        assert sum(r["min_secure"] for r in rows) == sec
        assert sec < baseline  # a secure saving exists beyond d = 2
        assert sec > any_  # but the cost-only optimum still leaks
        assert rows[-1]["cheapest_all_leak"]


def test_built_circuits_agree_with_verifmsi():
    """In-house per-wire verdicts equal VerifMSI's exact check, d = 2..4."""
    import pytest

    sys.path[:0] = [
        str(Path(__file__).resolve().parents[1] / "premise_test"),
        str(Path(__file__).resolve().parents[1] / "oracle_crosscheck"),
    ]
    import crosscheck
    from shares import build_circuit, circuit_safety

    if not crosscheck.oracle_available():
        pytest.skip("VerifMSI not installed (see experiments/oracle_crosscheck)")
    sizes = {2: (8, 7), 3: (17, 16), 4: (28, 27)}  # (secure, cost-only) real gates
    for d, (sec_gates, any_gates) in sizes.items():
        for kind, gates, leaks in (
            ("secure", sec_gates, False),
            ("any", any_gates, True),
        ):
            circ, secrets, randoms = build_circuit(d, kind)
            ours = circuit_safety(d, circ)
            oracle = crosscheck.oracle_verdict(circ, secrets, randoms)
            assert circ.gate_count() == gates
            assert any(not v for v in ours.values()) == leaks
            for name, _, _ in circ.wires:
                assert ours[name] == bool(oracle[name]["independent"]), (d, kind, name)
                if oracle[name]["tps"]:
                    assert ours[name]
