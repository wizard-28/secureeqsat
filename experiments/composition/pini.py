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

Purpose
-------
PINI is a property of ONE gadget that lets us skip checking whole circuits: a circuit
made only of PINI gadgets is secure (see `analysis.py`). This module decides, by brute
force, whether a given gadget is 1-PINI. The expected result (finding F11) is that XOR,
NOT, refresh and HPC1 are PINI, while ISW and DOM are not (they multiply a share of x
with the OTHER index's share of y inside one product).

A worked example of why ISW fails: its internal wire `x0 & y1` depends on share index 0
of x and share index 1 of y, so it needs BOTH indices. 1-PINI allows an internal probe
to depend on at most one index.
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

X, Y = ("in", "x"), ("in", "y")  # the two input sharings used to build a test gadget


def gadget_term(op):
    """The gadget `op` applied to fresh input sharings x (and y).

    Unary operators (refresh, not) take only `x`; every other operator takes `x` and
    `y`. Returns a shared-value term as defined in `resharing/gadgets.py`.
    """
    if op in ("refresh", "not"):
        return (op, X)
    return (op, X, Y)


def _index(share):
    """Share index of an input-share name like 'x0' / 'y1'.

    The index is the last character of the name, read as a digit: 'x0' -> 0, 'y1' -> 1.
    """
    return int(share[-1])


def check_pini(circ, input_shares, randoms):
    """Return (is_pini, {wire: reason}) for a lowered gadget circuit.

    Algorithm, step by step:
      1. For EVERY assignment of all input shares (not only valid sharings: PINI is a
         property for all of them) and every assignment of the randoms, evaluate the
         circuit and count, per wire, how many random assignments give 1. That count is
         the wire's distribution for this input assignment.
      2. `depends_only_on(w, indices)` asks: is that count a FUNCTION of the input
         shares whose index is in `indices`? It groups the input assignments by the
         values of those shares and checks every group has one count.
      3. For each non-input wire: an OUTPUT wire for share i must depend only on index i
         (condition b); an INTERNAL wire must depend on no share, only index 0, or only
         index 1 (condition a, B = {}, {0} or {1}).
      4. The gadget is PINI iff no wire fails. A failing wire gets a reason string.
    """
    outputs = circ.outputs
    # outputs are consecutive share pairs, so output i is share index i % 2:
    # {share-0 wire: 0, share-1 wire: 1, ...}
    out_index = {w: i % 2 for i, w in enumerate(outputs)}
    dists = defaultdict(dict)  # wire -> {input assignment: count of ones}
    for ivals in itertools.product((0, 1), repeat=len(input_shares)):
        base = dict(zip(input_shares, ivals, strict=True))  # this input assignment
        counts = defaultdict(int)  # wire -> number of random assignments giving 1
        for rvals in itertools.product((0, 1), repeat=len(randoms)):
            # `{**a, **b}` merges two dicts: the inputs and the random assignment
            vals = evaluate(circ, {**base, **dict(zip(randoms, rvals, strict=True))})
            for w, _, _ in circ.wires:
                counts[w] += vals[w]  # True counts as 1, False as 0
        for w, _, _ in circ.wires:
            dists[w][ivals] = counts[w]

    def depends_only_on(w, indices):
        """True iff w's count is a function of the shares indexed in `indices`."""
        # positions (in the assignment tuple) of the input shares we are allowed to see
        keep = [k for k, s in enumerate(input_shares) if _index(s) in indices]
        seen = {}  # restricted assignment -> the count it must always give
        for ivals, c in dists[w].items():
            key = tuple(ivals[k] for k in keep)  # the assignment restricted to `keep`
            # `setdefault` stores the first count for this key and returns it later;
            # a different count for the same key means the wire depends on more shares
            if seen.setdefault(key, c) != c:
                return False
        return True

    bad = {}  # wire -> why it violates PINI
    for w, op, _ in circ.wires:
        if op == "input":
            continue  # input shares are not gadget-internal probes
        if w in out_index:
            # condition (b): output share i may only use input shares with index i
            if not depends_only_on(w, {out_index[w]}):
                bad[w] = f"output share {out_index[w]} needs other indices"
        elif not any(depends_only_on(w, b) for b in (set(), {0}, {1})):
            # condition (a): an internal probe may need at most ONE share index
            bad[w] = "internal probe needs both share indices"
    return not bad, bad


def gadget_is_pini(op):
    """Lower the gadget `op` and run `check_pini` on it; returns (is_pini, reasons).

    The input share names are x0, x1 (and y0, y1 for binary gadgets), matching the
    names produced by lowering.
    """
    low = lower([gadget_term(op)])
    names = ["x0", "x1"] + ([] if op in ("refresh", "not") else ["y0", "y1"])
    return check_pini(low.circ, names, low.randoms)
