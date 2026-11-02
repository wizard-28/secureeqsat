"""Recount the one-node-per-class (DAG) extractions of `square` under each rule set.

    uv run python experiments/bench_extra/dag_extractions.py

Purpose
-------
Independent re-derivation of the numbers in `design/0021` (338 acyclic extractions, 16
secure, under R1 + R3) and of the claim that refresh removal alone (R3) leaves no secure
one-node-per-class choice. It enumerates every assignment of one node to each reachable
class, drops cyclic ones, builds the shared term and asks the in-house checker whether
the lowered circuit leaks. Enumeration code is separate from `extract.py`.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ("resharing", "premise_test", "oracle_crosscheck"):
    sys.path.insert(0, str(ROOT / "experiments" / sub))

from extract import Evaluator  # noqa: E402
from fixtures import FIXTURES  # noqa: E402
from layer import export, saturate  # noqa: E402


def children(node):
    """Child class ids of an e-node (inputs have none)."""
    return () if node[0] == "in" else node[1]


def assignments(classes, root):
    """Yield {class: chosen node} for every choice of one node per reachable class."""

    def rec(assign, pending):
        if not pending:
            yield dict(assign)
            return
        c, rest = pending[0], pending[1:]
        for node in classes[c]:
            assign[c] = node
            new = []
            for k in children(node):
                if k not in assign and k not in rest and k not in new:
                    new.append(k)
            yield from rec(assign, rest + new)
            del assign[c]

    yield from rec({}, [root])


def acyclic(assign, root):
    """True iff the chosen nodes contain no cycle (depth-first search)."""
    state = {}

    def dfs(c):
        if state.get(c) == 1:
            return False
        if state.get(c) == 2:
            return True
        state[c] = 1
        ok = all(dfs(k) for k in children(assign[c]))
        state[c] = 2
        return ok

    return dfs(root)


def build(assign, c, memo):
    """The nested-tuple term for class `c` under `assign`, shared per class."""
    if c not in memo:
        node = assign[c]
        if node[0] == "in":
            memo[c] = node
        else:
            memo[c] = (node[0], *[build(assign, k, memo) for k in node[1]])
    return memo[c]


def main():
    """Print, per rule set, the acyclic extractions and how many are secure."""
    term = FIXTURES["square"]
    print("square =", term)
    for rules in [("R3",), ("R1", "R3"), ("R2", "R3"), ("R1", "R2", "R3")]:
        eg, _ = saturate(term, rules, 6)
        classes, root = export(eg)
        ev = Evaluator()
        total = secure = 0
        example = None
        for assign in assignments(classes, root):
            if not acyclic(assign, root):
                continue
            total += 1
            t = build(assign, root, {})
            cost, leaks = ev(t)
            if not leaks:
                secure += 1
                example = min(example or (cost, t), (cost, t), key=lambda p: p[0])
        name = "+".join(rules)
        print(f"{name:9s} classes={len(classes):3d} acyclic={total:5d} secure={secure}")
        if example:
            print("    cheapest secure example:", example)


if __name__ == "__main__":
    main()
