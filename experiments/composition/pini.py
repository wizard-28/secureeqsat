"""Exact first-order PINI checker for small gadgets (design/0019).

Probe-Isolating Non-Interference (Cassiers & Standaert, IEEE TIFS 2020,
ePrint 2018/438, Definition 12): a gadget is d-PINI if for every set P of d1
internal probes and set A of d2 output-share indices with d1 + d2 <= d, there
is a set B of at most d1 indices such that P and the output shares in A can be
simulated from the input shares with indices in A u B.

At d = 1 with 2 shares that is two checks, done here exhaustively:

  (a) one internal probe, no output share: the wire's distribution (over the
      gadget's fresh randoms) depends on the input shares of at most ONE
      share index (B = {} or {0} or {1}), for every input-share assignment;
  (b) one output share i, no internal probe: share i's distribution depends
      only on the input shares with index i.

"Simulatable from S" is checked as: for every assignment of all input shares,
the distribution of the probed value over the randoms is a function of the
assignment restricted to S. Input shares range over all values (PINI is a
property for all input sharings), randoms are uniform.

Glitch-free model only. Exhaustive: 2**(input shares + randoms) per wire.
"""

import itertools
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "premise_test"))
sys.path.insert(0, str(ROOT / "experiments" / "resharing"))

from gadgets import lower  # noqa: E402
from masked import evaluate  # noqa: E402

X, Y = ("in", "x"), ("in", "y")


def gadget_term(op):
    """The gadget `op` applied to fresh input sharings x (and y)."""
    if op in ("refresh", "not"):
        return (op, X)
    return (op, X, Y)


def _index(share):
    """Share index of an input-share name like 'x0' / 'y1'."""
    return int(share[-1])


def check_pini(circ, input_shares, randoms):
    """Return (is_pini, {wire: reason}) for a lowered gadget circuit."""
    outputs = circ.outputs
    out_index = {w: i % 2 for i, w in enumerate(outputs)}
    dists = defaultdict(dict)  # wire -> {input assignment: count of ones}
    for ivals in itertools.product((0, 1), repeat=len(input_shares)):
        base = dict(zip(input_shares, ivals, strict=True))
        counts = defaultdict(int)
        for rvals in itertools.product((0, 1), repeat=len(randoms)):
            vals = evaluate(circ, {**base, **dict(zip(randoms, rvals, strict=True))})
            for w, _, _ in circ.wires:
                counts[w] += vals[w]
        for w, _, _ in circ.wires:
            dists[w][ivals] = counts[w]

    def depends_only_on(w, indices):
        keep = [k for k, s in enumerate(input_shares) if _index(s) in indices]
        seen = {}
        for ivals, c in dists[w].items():
            key = tuple(ivals[k] for k in keep)
            if seen.setdefault(key, c) != c:
                return False
        return True

    bad = {}
    for w, op, _ in circ.wires:
        if op == "input":
            continue  # input shares are not gadget-internal probes
        if w in out_index:
            if not depends_only_on(w, {out_index[w]}):
                bad[w] = f"output share {out_index[w]} needs other indices"
        elif not any(depends_only_on(w, b) for b in (set(), {0}, {1})):
            bad[w] = "internal probe needs both share indices"
    return not bad, bad


def gadget_is_pini(op):
    low = lower([gadget_term(op)])
    names = ["x0", "x1"] + ([] if op in ("refresh", "not") else ["y0", "y1"])
    return check_pini(low.circ, names, low.randoms)
