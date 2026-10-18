"""Occurrence-aware, glitch-constrained extraction for the probe (design/0017).

With registers TRANSPARENT (`reg(x) = x`), `reg(X)` lands in class X itself: a
self-loop. One-node-per-class extraction, and egglog's own `extract` /
`extract_multiple`, never take it (it only adds cost), so they can never
return a registered circuit -- the same obstruction as `refresh` in
`design/0016`. This extractor works on terms instead: per class, a k-best
list of terms built bottom-up, with a child chosen per occurrence, so
`reg(x)` can be taken where it is needed.

A term enters a list only if its circuit has no leaking probe (glitch-
extended). The cut is sound: a probe's stable set depends only on its own
cone, which a context does not change, so a leaking subterm leaks everywhere.
At first order each output root can be extracted separately: a probe lies in
one root's cone and leaks or not independently of the other root.
"""

import itertools
import json

from glitch import GCircuit, check_glitch

OWN = {"var": 0, "zero": 0, "xor": 1, "and": 1, "reg": 1}


def export(eg, names):
    """(classes, {let-name: class}) from egglog's serializer (private API)."""
    data = json.loads(
        eg._serialize(
            max_functions=None, max_calls_per_function=None, n_inline_leaves=0
        ).to_json()
    )
    nodes, sorts = data["nodes"], {}
    for c, info in data["class_data"].items():
        sorts[c] = info.get("type")
    classes = {}
    for node in nodes.values():
        cls = node["eclass"]
        if sorts.get(cls) == "String":
            continue
        op = node["op"]
        kids = [nodes[k]["eclass"] for k in node["children"]]
        if op.endswith(".var"):
            entry = ("var", json.loads(nodes[node["children"][0]]["op"]))
        elif op.endswith(".zero"):
            entry = ("zero",)
        elif op == "· & ·":
            entry = ("and", tuple(kids))
        elif op == "· ^ ·":
            entry = ("xor", tuple(kids))
        elif op.endswith(".reg"):
            entry = ("reg", tuple(kids))
        else:
            raise ValueError(f"unexpected egglog op {op!r}")
        classes.setdefault(cls, [])
        if entry not in classes[cls]:
            classes[cls].append(entry)
    roots = {
        info["let"].lstrip("$"): c
        for c, info in data["class_data"].items()
        if info.get("let") in {f"${n}" for n in names}
    }
    return classes, roots


def term_circuit(terms):
    c = GCircuit()

    def go(t):
        op = t[0]
        if op == "var":
            return c.add_input(t[1])
        if op == "zero":
            return c.add_const(0)
        if op == "reg":
            return c.add_reg(go(t[1]))
        return c.add_gate(op, go(t[1]), go(t[2]))

    c.outputs = [go(t) for t in terms]
    return c


def term_cost(c):
    return c.count("and", "xor", "reg")


def kbest(classes, root, secrets, free, k=8, secure=True, max_rounds=30):
    lists = {c: [] for c in classes}
    seen = {c: set() for c in classes}
    cache = {}

    def evaluate(t):
        if t not in cache:
            circ = term_circuit([t])
            leaks = not all(check_glitch(circ, secrets, free).values())
            cache[t] = (term_cost(circ), leaks)
        return cache[t]

    for _ in range(max_rounds):
        changed = False
        for c, nodes in classes.items():
            cur = lists[c]
            for node in nodes:
                for t in _candidates(node, lists):
                    if t in seen[c]:
                        continue
                    if len(cur) >= k and _lb(t, evaluate) >= cur[-1][0]:
                        continue
                    seen[c].add(t)
                    cost, leaks = evaluate(t)
                    if secure and leaks:
                        continue
                    if len(cur) < k or cost < cur[-1][0]:
                        cur.append((cost, t))
                        cur.sort(key=lambda p: (p[0], repr(p[1])))
                        del cur[k:]
                        changed = True
        if not changed:
            break
    return lists[root][0] if lists[root] else None, len(cache)


def _candidates(node, lists):
    op = node[0]
    if op in ("var", "zero"):
        yield node
    elif op == "reg":
        for _, t in lists[node[1][0]]:
            if t[0] != "reg":  # reg(reg(t)) adds a register and hides nothing more
                yield ("reg", t)
    else:
        c1, c2 = node[1]
        for (_, t1), (_, t2) in itertools.product(lists[c1], lists[c2]):
            yield (op, t1, t2)


def _lb(t, evaluate):
    if t[0] in ("var", "zero"):
        return 0
    return OWN[t[0]] + max(evaluate(s)[0] for s in t[1:])
