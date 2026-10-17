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
UNEVALUABLE = float("inf")


class InconsistentClassError(Exception):
    """Two terms in one class reconstruct different values."""


class Evaluator:
    """Memoised cost and leak check for terms."""

    def __init__(self, max_bits=None):
        self.max_bits = max_bits
        self._cache = {}
        self.over_cap = 0

    def __call__(self, term):
        if term not in self._cache:
            low = lower([term])
            names = secrets_of(term)
            kw = {} if self.max_bits is None else {"max_bits": self.max_bits}
            try:
                verdict = check_first_order_bitsliced(
                    low.circ, secret_groups(names), free_vars(names, low.randoms), **kw
                )
            except ValueError:  # beyond the labeller's 2**max_bits cap
                self.over_cap += 1
                self._cache[term] = (UNEVALUABLE, None)
                return self._cache[term]
            leaks = [w for w, ok in verdict.items() if not ok]
            self._cache[term] = (cost_of(low), leaks)
        return self._cache[term]

    @property
    def evaluated(self):
        return len(self._cache)


def value_table(term, names):
    return tuple(
        value(term, dict(zip(names, bits, strict=True)))
        for bits in itertools.product((0, 1), repeat=len(names))
    )


def kbest(classes, root, k=16, secure=True, max_rounds=40, evaluator=None):
    """Return (best_term_or_None, info) for the root class.

    classes: {class_id: [node]} from `layer.export`.
    """
    ev = evaluator or Evaluator()
    lists = {c: [] for c in classes}  # sorted [(cost, term)]
    seen = {c: set() for c in classes}
    names = sorted({n[1] for nodes in classes.values() for n in nodes if n[0] == "in"})
    tables = {}
    rounds = 0
    changed = True
    while changed and rounds < max_rounds:
        rounds += 1
        changed = False
        for c, nodes in classes.items():
            cur = lists[c]
            for node in nodes:
                for term in _candidates(node, lists):
                    if term in seen[c]:
                        continue
                    if len(cur) >= k and _lower_bound(term, ev) >= cur[-1][0]:
                        continue  # cannot enter the list; may be retried later
                    seen[c].add(term)
                    cost, leaks = ev(term)
                    if leaks is None:
                        continue  # too large to label: never admitted
                    tab = value_table(term, names)
                    if tables.setdefault(c, tab) != tab:
                        raise InconsistentClassError(f"class {c}: {term!r}")
                    if secure and leaks:
                        continue
                    if len(cur) < k or cost < cur[-1][0]:
                        cur.append((cost, term))
                        cur.sort(key=lambda p: (p[0], repr(p[1])))
                        del cur[k:]
                        changed = True
    info = {
        "rounds": rounds,
        "evaluated": ev.evaluated,
        "over_cap": ev.over_cap,
        "converged": not changed,
    }
    best = lists[root][0] if lists[root] else None
    return best, info


def _candidates(node, lists):
    op = node[0]
    if op == "in":
        yield node
    elif op == "refresh":
        for _, t in lists[node[1][0]]:
            if t[0] != "refresh":  # a second refresh never helps (same distribution)
                yield ("refresh", t)
    elif op == "not":
        for _, t in lists[node[1][0]]:
            if t[0] != "not":  # not(not(t)) is t, which the class already holds
                yield ("not", t)
    else:
        c1, c2 = node[1]
        for (_, t1), (_, t2) in itertools.product(lists[c1], lists[c2]):
            yield (op, t1, t2)


def _lower_bound(term, ev):
    """Cheap lower bound on a candidate's cost: own cost + costliest child."""
    if term[0] == "in":
        return 0
    return OWN_COST[term[0]] + max(ev(t)[0] for t in term[1:])
