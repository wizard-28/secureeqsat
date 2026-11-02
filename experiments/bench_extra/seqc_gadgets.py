"""Count masked AND gadgets and random bits in seqc's chosen circuits.

    uv run python experiments/bench_extra/seqc_gadgets.py prog.sec [--k K --iters N]

Purpose
-------
The head-to-head compares tools by "AND gadgets" and "fresh random bits". This script
compiles a program with `seqc.compile_program` and counts, for the masked start circuit,
the security-ignored optimum and the security-enforced optimum, the distinct gadget
subterms (`isw`, `dom`, `hpc1`; a shared subterm is one gadget) and the random bits.
"""

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "frontend"))

import seqc  # noqa: E402
from lang import parse  # noqa: E402

GADGETS = ("isw", "dom", "hpc1")


def gadget_count(term):
    """Number of distinct gadget subterms of `term` (shared subterms count once)."""
    seen = set()

    def walk(t):
        if isinstance(t, tuple) and t:
            if t[0] in GADGETS:
                seen.add(t)
            for c in t[1:]:
                walk(c)

    walk(term)
    return len(seen)


def main():
    """Compile the program and print gadgets / randoms for each stage."""
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--iters", type=int, default=6)
    a = ap.parse_args()
    t0 = time.time()
    res = seqc.compile_program(parse(Path(a.source).read_text()), k=a.k, iters=a.iters)
    dt = time.time() - t0
    cells = []
    for label, st in (
        ("start", res.start),
        ("ignored", res.unconstrained),
        ("enforced", res.constrained),
    ):
        cells.append(
            f"{label} gadgets={gadget_count(st.term)} rnd={st.randoms} "
            f"cost={st.cost} {'secure' if st.secure else 'LEAKS'}"
        )
    print(f"{Path(a.source).stem:14s} " + " | ".join(cells) + f" | {dt:.1f}s")


if __name__ == "__main__":
    main()
