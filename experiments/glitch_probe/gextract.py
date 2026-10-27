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

Purpose
-------
The glitch-model counterpart of `experiments/resharing/extract.py`. A register that
the e-graph treats as transparent sits in the same class as its operand, so a
one-node-per-class extractor can never pick it. This one keeps the k cheapest TERMS per
class, checks each with the glitch checker, and so can place a register exactly where
it is needed.

A tiny example: for an unregistered DOM gadget, the cheapest term has no registers and
leaks under glitches. The extractor then considers terms with `reg(...)` on the cross
terms, which pass the glitch check, and returns that one (10 = 8 gates + 2 registers).
"""

import itertools
import json

from glitch import GCircuit, check_glitch

# Cost of one operator on its own (gates and registers each cost 1; leaves are free),
# used for the quick lower bound below.
OWN = {"var": 0, "zero": 0, "xor": 1, "and": 1, "reg": 1}


def export(eg, names):
    """(classes, {let-name: class}) from egglog's serializer (private API).

    Algorithm, step by step:
      1. Serialise the e-graph to JSON and read its node table and class table.
      2. For every node (skipping string-literal nodes), turn egglog's operator text
         into one of our node tuples: `var` (the name is read from its string child),
         `zero`, `and` (egglog prints it as `· & ·`), `xor` (`· ^ ·`) or `reg`.
      3. Add each distinct node to its class's list.
      4. Find the root classes: the ones the caller named with `eg.let`, which the
         serialiser tags as `$name`.
    """
    data = json.loads(
        eg._serialize(
            max_functions=None, max_calls_per_function=None, n_inline_leaves=0
        ).to_json()
    )
    nodes, sorts = data["nodes"], {}  # nodes: id -> node info; sorts: class -> type
    for c, info in data["class_data"].items():
        sorts[c] = info.get("type")
    classes = {}  # class id -> list of node tuples
    for node in nodes.values():
        cls = node["eclass"]
        if sorts.get(cls) == "String":
            continue  # a string literal (an input name), not a signal
        op = node["op"]  # egglog's operator text, e.g. "· & ·" or "G.var"
        kids = [nodes[k]["eclass"] for k in node["children"]]  # child class ids
        if op.endswith(".var"):
            # the variable's name is the operator text of its one string child
            entry = ("var", json.loads(nodes[node["children"][0]]["op"]))
        elif op.endswith(".zero"):
            entry = ("zero",)
        elif op == "· & ·":  # egglog prints the infix AND this way
            entry = ("and", tuple(kids))
        elif op == "· ^ ·":  # ... and the infix XOR
            entry = ("xor", tuple(kids))
        elif op.endswith(".reg"):
            entry = ("reg", tuple(kids))
        else:
            raise ValueError(f"unexpected egglog op {op!r}")
        classes.setdefault(cls, [])
        if entry not in classes[cls]:
            classes[cls].append(entry)
    roots = {
        info["let"].lstrip("$"): c  # "$o0" -> "o0"
        for c, info in data["class_data"].items()
        if info.get("let") in {f"${n}" for n in names}
    }
    return classes, roots


def term_circuit(terms):
    """Build a `GCircuit` whose outputs are the given terms (nested tuples).

    A term is `("var", name)`, `("zero",)`, `("reg", t)` or `("and"|"xor", t1, t2)`. The
    circuit hash-conses wires, so a repeated subterm becomes one wire.
    """
    c = GCircuit()

    def go(t):
        """Add term `t` to the circuit and return its wire name (recursive)."""
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
    """Cost of a circuit: gates plus registers (each counts 1)."""
    return c.count("and", "xor", "reg")


def kbest(classes, root, secrets, free, k=8, secure=True, max_rounds=30):
    """Best `(cost, term)` for the `root` class, plus how many terms were evaluated.

    Algorithm, step by step (the same scheme as `resharing/extract.py`):
      1. Each class keeps a sorted list of its `k` cheapest admissible terms.
      2. Repeat rounds: for every class and node, build candidate terms from the child
         classes' lists, choosing each child independently per occurrence.
      3. Skip a candidate already seen, or whose cheap lower bound cannot beat the
         worst entry of a full list.
      4. Evaluate it: build its circuit, count gates + registers, and run the
         glitch-extended checker on every wire. In `secure` mode, drop it if any probe
         leaks.
      5. Otherwise insert it into the class's list (sorted by cost), keep `k`, and mark
         that something changed.
      6. Stop when a round changes nothing, or after `max_rounds`. Return the cheapest
         term of the root class (or None) and the number of distinct terms evaluated.
    """
    lists = {c: [] for c in classes}  # class -> sorted [(cost, term)]
    seen = {c: set() for c in classes}  # class -> candidates already tried
    cache = {}  # term -> (cost, leaks), so each term is evaluated once

    def evaluate(t):
        """Cost and glitch-leak flag of term `t` (cached)."""
        if t not in cache:
            circ = term_circuit([t])
            # leaks if NOT all probes are secure
            leaks = not all(check_glitch(circ, secrets, free).values())
            cache[t] = (term_cost(circ), leaks)
        return cache[t]

    for _ in range(max_rounds):
        changed = False  # did any list change in this round?
        for c, nodes in classes.items():
            cur = lists[c]  # this class's current best terms
            for node in nodes:
                for t in _candidates(node, lists):
                    if t in seen[c]:
                        continue
                    # full list and even the optimistic cost is no better: skip
                    if len(cur) >= k and _lb(t, evaluate) >= cur[-1][0]:
                        continue
                    seen[c].add(t)
                    cost, leaks = evaluate(t)
                    if secure and leaks:
                        continue  # a leaking term is cut (it leaks in any context)
                    if len(cur) < k or cost < cur[-1][0]:
                        cur.append((cost, t))
                        cur.sort(key=lambda p: (p[0], repr(p[1])))  # cheapest first
                        del cur[k:]  # keep only the k cheapest
                        changed = True
        if not changed:
            break
    return lists[root][0] if lists[root] else None, len(cache)


def _candidates(node, lists):
    """Yield the terms one e-node can produce from its children's current lists.

    Leaves yield themselves. `reg` wraps each child term (but never a register
    directly around a register, which adds cost and hides nothing more). A binary
    operator yields one term per PAIR of child terms, so each operand is chosen
    independently, per occurrence.
    """
    op = node[0]
    if op in ("var", "zero"):
        yield node
    elif op == "reg":
        for _, t in lists[node[1][0]]:  # each term of the child class
            if t[0] != "reg":  # reg(reg(t)) adds a register and hides nothing more
                yield ("reg", t)
    else:
        c1, c2 = node[1]  # the two child classes
        for (_, t1), (_, t2) in itertools.product(lists[c1], lists[c2]):
            yield (op, t1, t2)


def _lb(t, evaluate):
    """Cheap lower bound on a term's cost: own cost plus its costliest child."""
    if t[0] in ("var", "zero"):
        return 0
    # `t[1:]` are the child terms; `evaluate(s)[0]` is a child's cost
    return OWN[t[0]] + max(evaluate(s)[0] for s in t[1:])
