"""Occurrence-aware, security-constrained extraction over the shared-value layer.

Safety is no longer a per-class label at this layer: every class of sort `S`
reconstructs a secret-dependent value, and whether a choice leaks depends on
how the chosen gadgets are lowered and which sharings meet (design/0016).
Extraction therefore works on *terms*, not on one node per class:

  * each class keeps a k-best list of terms, built bottom-up from its nodes and
    its children's lists, to a fixed point (classes may be cyclic);
  * a child is chosen per occurrence, so `isw(A, A)` can become
    `isw(a, refresh(a))` even though `a` and `refresh(a)` are one class;
  * a term's cost is the exact cost of its lowered circuit (gates + randoms,
    common subterms shared), not an additive estimate;
  * in constrained mode a term enters a list only if its lowered circuit has no
    leaking wire. That is a sound cut: a wire's distribution does not change
    when independent inputs are added around it, so a leaking subterm leaks in
    every context, and no term containing it needs to be considered.

Bounded by `k`: the result is the best term in a k-best frontier, exact only
when the frontier is wide enough; `run.py` reports stability across k.

Every term added to a class must reconstruct the class's value; a mismatch
raises `InconsistentClassError` (an unsound rule).

Purpose
-------
This is the extractor for the value layer (the repair, one level up). On the wire
level one safe/unsafe label per class was enough. Here a class such as
`{z, refresh(z)}` holds terms that differ in safety, so we cannot label the class.
Instead each class keeps its `k` cheapest terms, every term is lowered to a real
circuit and checked, and leaking terms are thrown away.

A tiny example: for the square `isw(z, z)` the class of `z` also holds `refresh(z)`.
The candidate `isw(z, z)` costs 11 but its lowered circuit has the wire `z0*z1`,
which leaks, so it is dropped. The candidate `isw(z, refresh(z))` costs 14 and is
secure, so it is the answer.
"""

import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "labeller"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gadgets import (  # noqa: E402
    cost_of,
    free_vars,
    lower,
    secret_groups,
    secrets_of,
    value,
)
from labeller import check_first_order_bitsliced  # noqa: E402

# Cost of ONE operator on its own (gates + fresh randoms), used for a quick lower
# bound: isw = 8 gates + 1 random = 9; hpc1 = DOM + a refresh = 12; refresh = 2 XOR
# gates + 1 random = 3; xor = 2 share-wise gates; not = 1 gate.
OWN_COST = {
    "in": 0,
    "out": 0,
    "not": 1,
    "xor": 2,
    "refresh": 3,
    "isw": 9,
    "dom": 9,
    "hpc1": 12,
}
UNEVALUABLE = float("inf")  # cost given to terms too large for the labeller to check


class InconsistentClassError(Exception):
    """Two terms in one class reconstruct different values."""


class Evaluator:
    """Memoised cost and leak check for terms.

    Calling an `Evaluator` on a term returns `(cost, leaking_wires)`:
    `cost` is the exact cost of the lowered circuit, and `leaking_wires` is the list
    of wires the checker marked unsafe (`[]` means secure). If the term is too big
    for the labeller, the result is `(inf, None)`. Results are cached per term.
    """

    def __init__(self, max_bits=None):
        """`max_bits` optionally lowers the labeller's size cap (default 2**26)."""
        self.max_bits = max_bits
        self._cache = {}  # term -> (cost, leaks), so each term is evaluated once
        self.over_cap = 0  # how many terms were too large to label

    def __call__(self, term):
        """Lower `term`, check its wires, and return `(cost, leaking_wires)`.

        Algorithm, step by step:
          1. If cached, return the stored answer.
          2. Lower the term (with shared subterms) to a circuit.
          3. Run the bitsliced checker on it. If the assignment space is over the
             cap (a ValueError), record `(inf, None)` and count it as over the cap.
          4. Otherwise record `(cost of the circuit, list of unsafe wires)`.
        """
        if term not in self._cache:
            low = lower([term])  # the term as a real circuit (+ its randoms)
            names = secrets_of(term)  # the secrets it reads, e.g. ["a", "b"]
            # only pass max_bits through if the caller set it
            kw = {} if self.max_bits is None else {"max_bits": self.max_bits}
            try:
                verdict = check_first_order_bitsliced(
                    low.circ, secret_groups(names), free_vars(names, low.randoms), **kw
                )
            except ValueError:  # beyond the labeller's 2**max_bits cap
                self.over_cap += 1
                self._cache[term] = (UNEVALUABLE, None)
                return self._cache[term]
            leaks = [w for w, ok in verdict.items() if not ok]  # unsafe wire names
            self._cache[term] = (cost_of(low), leaks)
        return self._cache[term]

    @property
    def evaluated(self):
        """How many distinct terms have been evaluated so far."""
        return len(self._cache)


def value_table(term, names):
    """The term's unmasked value for every assignment of the secrets `names`.

    Returns a tuple like `(0, 0, 0, 1)` for an AND of two secrets. Two terms are
    equal as values exactly when their tables are equal; `kbest` uses this to catch
    an unsound rule that put two different values in one class.
    """
    return tuple(
        value(term, dict(zip(names, bits, strict=True)))
        # every combination of 0/1 for the n secrets, e.g. (0,0), (0,1), (1,0), (1,1)
        for bits in itertools.product((0, 1), repeat=len(names))
    )


def kbest(classes, root, k=16, secure=True, max_rounds=40, evaluator=None):
    """Return (best_term_or_None, info) for the root class.

    classes: {class_id: [node]} from `layer.export`.

    Algorithm, step by step:
      1. Give every class an empty sorted list of `(cost, term)` pairs, to hold its
         `k` cheapest terms.
      2. Repeat rounds until nothing changes (or `max_rounds`). In a round, for
         every class and every node in it, build candidate terms from the CHILD
         classes' current lists (`_candidates`).
      3. Skip a candidate already seen for this class. If the class's list is full
         (k entries) and the candidate's cheap lower bound already cannot beat the
         worst entry, skip it too (it may be retried in a later round).
      4. Evaluate the candidate (lower it, count cost, check every wire). If it is
         too large to label, never admit it.
      5. Check it reconstructs the same value as the class's other terms; a
         difference raises `InconsistentClassError` (an unsound rule).
      6. In `secure` mode, drop any candidate with a leaking wire. Otherwise insert
         it, keep the list sorted by `(cost, repr(term))`, and truncate to `k`.
         Any insertion counts as a change.
      7. After the loop, the answer is the cheapest term of the ROOT class, or None
         if the root has no admissible term (no secure realisation was found).
    The result is exact only if the frontier `k` is wide enough; `info["converged"]`
    says whether the loop reached a fixed point.
    """
    ev = evaluator or Evaluator()
    lists = {c: [] for c in classes}  # class -> sorted list of (cost, term)
    seen = {c: set() for c in classes}  # class -> candidates already tried
    # every secret name that occurs anywhere, e.g. ["a", "b", "d"]
    names = sorted({n[1] for nodes in classes.values() for n in nodes if n[0] == "in"})
    tables = {}  # class -> its value table, to detect unsound classes
    rounds = 0  # how many rounds were run
    changed = True  # did the last round add anything? (start True to enter the loop)
    while changed and rounds < max_rounds:
        rounds += 1
        changed = False
        for c, nodes in classes.items():
            cur = lists[c]  # this class's current best terms
            for node in nodes:
                for term in _candidates(node, lists):
                    if term in seen[c]:
                        continue
                    # full list and even the optimistic cost is no better: skip
                    if len(cur) >= k and _lower_bound(term, ev) >= cur[-1][0]:
                        continue  # cannot enter the list; may be retried later
                    seen[c].add(term)
                    cost, leaks = ev(term)
                    if leaks is None:
                        continue  # too large to label: never admitted
                    tab = value_table(term, names)
                    # `setdefault` stores the first table for the class and returns it
                    # afterwards, so a different table later is a contradiction
                    if tables.setdefault(c, tab) != tab:
                        raise InconsistentClassError(f"class {c}: {term!r}")
                    if secure and leaks:
                        continue  # a leaking term is cut (it leaks in any context)
                    if len(cur) < k or cost < cur[-1][0]:
                        cur.append((cost, term))
                        cur.sort(key=lambda p: (p[0], repr(p[1])))  # cheapest first
                        del cur[k:]  # keep only the k cheapest
                        changed = True
    info = {
        "rounds": rounds,  # rounds run
        "evaluated": ev.evaluated,  # distinct terms lowered and checked
        "over_cap": ev.over_cap,  # terms too large for the labeller
        "converged": not changed,  # True if a fixed point was reached
    }
    best = lists[root][0] if lists[root] else None  # (cost, term) of the best, or None
    return best, info


def _candidates(node, lists):
    """Yield the terms that one e-node can produce from its children's best lists.

    An input yields itself. `refresh` and `not` wrap each child term (skipping a
    second wrapper of the same kind, which adds nothing). A binary operator yields
    one term for every PAIR of child terms: the product of the two lists. Choosing
    the pair independently is what makes the choice per occurrence.
    """
    op = node[0]
    if op == "in":
        yield node
    elif op == "refresh":
        for _, t in lists[node[1][0]]:  # each term of the child class
            if t[0] != "refresh":  # a second refresh never helps (same distribution)
                yield ("refresh", t)
    elif op == "not":
        for _, t in lists[node[1][0]]:
            if t[0] != "not":  # not(not(t)) is t, which the class already holds
                yield ("not", t)
    else:
        c1, c2 = node[1]  # the two child classes
        # every pairing of a term from the first list with one from the second
        for (_, t1), (_, t2) in itertools.product(lists[c1], lists[c2]):
            yield (op, t1, t2)


def _lower_bound(term, ev):
    """Cheap lower bound on a candidate's cost: own cost + costliest child.

    Lowering shares subterms, so the true cost can be below the sum of the children;
    but it can never be below the operator's own cost plus the single most expensive
    child, which is what this returns. Used to skip hopeless candidates early.
    """
    if term[0] == "in":
        return 0
    # `term[1:]` are the child terms; ev(t)[0] is a child's cost
    return OWN_COST[term[0]] + max(ev(t)[0] for t in term[1:])
