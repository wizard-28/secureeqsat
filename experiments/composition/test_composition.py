"""Tests for the composition analysis (design/0019).

Purpose
-------
These tests pin down the PINI story: which gadgets are PINI, that composable
extraction returns secure circuits on every fixture and on random PINI-only terms, that
it works beyond the exact checkers' range, and (if VerifMSI is installed) that
VerifMSI agrees on the gadget verdicts and certifies a large circuit. A negative control
checks that the certificate is not vacuous. Run with:
    uv run pytest experiments/composition -q
"""

import random
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for sub in ("composition", "resharing", "labeller", "premise_test"):
    sys.path.insert(0, str(ROOT / "experiments" / sub))

from analysis import (  # noqa: E402
    composable_classes,
    extract_composable,
    pini_operators,
)
from extract import Evaluator  # noqa: E402
from fixtures import FIXTURES, TIGHT, chi  # noqa: E402
from gadgets import GADGETS  # noqa: E402
from labeller import DEFAULT_MAX_BITS  # noqa: E402
from layer import export, saturate  # noqa: E402
from masked import Circuit  # noqa: E402
from pini import check_pini, gadget_is_pini  # noqa: E402
from run_composition import (  # noqa: E402
    ORACLE_PY,
    bits_of,
    random_pini_term,
    verifmsi_certify,
    verifmsi_pini,
)

A, B = ("in", "a"), ("in", "b")  # secret input terms
Z = ("xor", A, B)  # a share-wise XOR of a and b
ALL_OPS = (
    "xor",
    "not",
    "refresh",
    *GADGETS,
)  # every operator whose PINI status we check


def leaks(term):
    """True iff the term's lowered circuit has at least one leaking wire."""
    return bool(Evaluator()(term)[1])


@pytest.mark.parametrize("op", ALL_OPS)
def test_gadget_pini_verdicts(op):
    """XOR, NOT, refresh and HPC1 are PINI; ISW and DOM are not."""
    expected = op in ("xor", "not", "refresh", "hpc1")
    assert gadget_is_pini(op)[0] == expected


def test_output_share_with_the_wrong_index_is_not_pini():
    """Condition (b): output share i may only use input shares of index i."""
    c = Circuit()
    x0, x1 = c.add_input("x0"), c.add_input("x1")
    c.outputs = [c.add_gate("and", x1, x1), c.add_gate("and", x0, x0)]  # swapped
    ok, bad = check_pini(c, ["x0", "x1"], [])
    assert not ok and all("output share" in why for why in bad.values())


def test_pini_operators_are_exactly_the_verified_ones():
    """The analysis uses exactly xor, not, refresh, hpc1 and out as PINI operators."""
    assert pini_operators() == frozenset({"xor", "not", "refresh", "hpc1", "out"})


def test_square_needs_a_pini_gadget_to_be_composable():
    """Only ISW (not PINI): square is not composable; with R2 it becomes HPC1."""
    eg, _ = saturate(FIXTURES["square"], ("R3",), 6)
    classes, root = export(eg)
    assert root not in composable_classes(classes)  # only isw: not PINI
    eg, _ = saturate(FIXTURES["square"], ("R2", "R3"), 6)
    classes, root = export(eg)
    term = extract_composable(classes, root)
    assert term is not None and term[0] == "hpc1" and not leaks(term)


@pytest.mark.parametrize("name", sorted({**FIXTURES, **TIGHT}))
def test_composable_extraction_is_secure_on_every_fixture(name):
    """The composable extraction returns a secure circuit for every fixture."""
    eg, _ = saturate({**FIXTURES, **TIGHT}[name], ("R2",), 6)
    classes, root = export(eg)
    term = extract_composable(classes, root)
    assert term is not None and not leaks(term)


def test_random_pini_terms_never_leak():
    """Soundness: no random PINI-only term leaks (and enough were tested)."""
    rng = random.Random(190)  # fixed seed
    checked = 0
    for _ in range(150):
        t = random_pini_term(rng, 3, [("in", s) for s in "abd"])
        if t[0] == "in" or bits_of(t)[0] > DEFAULT_MAX_BITS:
            continue  # skip trivial terms and ones too large for the exact checker
        checked += 1
        assert not leaks(t), t
    assert checked > 100  # the test must not be vacuous


def test_composition_reaches_beyond_the_exact_range():
    """A 8-bit chi row exceeds the exact checker's cap, yet composition handles it."""
    eg, _ = saturate(chi(8), ("R2",), 2)
    classes, root = export(eg)
    term = extract_composable(classes, root)
    assert term is not None and bits_of(term)[0] > DEFAULT_MAX_BITS
    assert Evaluator()(term)[1] is None  # the exact checker refuses it


# Skip the VerifMSI tests (rather than fail them) when it is not installed.
needs_oracle = pytest.mark.skipif(not ORACLE_PY.exists(), reason="VerifMSI absent")


@needs_oracle
@pytest.mark.parametrize("op", ALL_OPS)
def test_pini_verdicts_agree_with_verifmsi(op):
    """Our PINI verdict equals VerifMSI's own PINI verdict for every gadget."""
    assert verifmsi_pini(op) == gadget_is_pini(op)[0]


@needs_oracle
def test_verifmsi_certifies_a_large_composable_circuit():
    """VerifMSI's symbolic check certifies every wire of a large composable circuit."""
    eg, _ = saturate(chi(8), ("R2",), 2)
    classes, root = export(eg)
    ok, missing = verifmsi_certify(extract_composable(classes, root))
    assert missing == 0 and ok > 100


@needs_oracle
def test_verifmsi_certificate_is_not_vacuous():
    """Negative control: a leaking circuit must not be fully certified."""
    assert leaks(("isw", Z, Z))
    _, missing = verifmsi_certify(("isw", Z, Z))
    assert missing > 0
