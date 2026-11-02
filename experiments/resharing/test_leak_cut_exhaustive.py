"""Exhaustive small-scope check of Proposition "leak cut" (paper, Sec. IV-B).

Claim: if a subterm's lowered circuit has a leaking wire, every term containing it
leaks. This enumerates ALL terms over inputs {a, b} up to a size bound, wraps each
leaking one in EVERY single-step context (unary, or binary with any small partner on
either side), and asserts the context still leaks.

This is a bounded exhaustive check, not a proof (a machine-checked proof needs a
prover that the dev container does not provide; see RESULTS.md).
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "experiments" / "oracle_crosscheck"))
sys.path.insert(0, str(ROOT / "experiments" / "premise_test"))

from extract import Evaluator  # noqa: E402

A, B = ("in", "a"), ("in", "b")
UNARY = ("not", "refresh")
BINARY = ("xor", "isw", "dom", "hpc1")


def terms(size):
    """All terms with exactly `size` operator nodes (leaves cost 0) over {a, b}."""
    if size == 0:
        return [A, B]
    out = []
    for op in UNARY:
        out += [(op, t) for t in terms(size - 1)]
    for op in BINARY:
        for k in range(size):
            for x in terms(k):
                for y in terms(size - 1 - k):
                    out.append((op, x, y))
    return out


def contexts(t):
    """Every one-step context of `t`, with partners drawn from the inputs."""
    out = [(op, t) for op in UNARY]
    for op in BINARY:
        for p in (A, B, ("refresh", A)):
            out += [(op, t, p), (op, p, t)]
    return out


def test_leak_is_monotone_in_context_exhaustively():
    ev = Evaluator()
    leaking = checked = 0
    for size in range(0, 4):
        for t in terms(size):
            if not ev(t)[1]:
                continue
            leaking += 1
            for c in contexts(t):
                checked += 1
                assert ev(c)[1], (t, c)
    assert leaking >= 2000 and checked >= 50000  # the test must not be vacuous
