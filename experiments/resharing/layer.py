"""The shared-value layer in egglog (design/0016).

E-classes of sort `S` are equal iff their terms reconstruct the same unmasked
value. At this layer the masking-specific equivalences become ordinary rules:

  R1  Boolean identities on values: XOR comm/assoc; for each AND gadget g,
      comm, assoc, distributivity over XOR and its reverse (factoring);
      NOT involution and g(~x, y) = y ^ g(x, y) in both directions.
      Idempotence (x & x = x) and constants are deliberately NOT included
      (see RESULTS.md, "Known limitations").
  R2  gadget equivalences: isw(x, y) = dom(x, y) = hpc1(x, y).
  R3  refresh: refresh(x) = x, plus refresh seeded at every gadget input, so
      every operand class carries a refresh self-loop that extraction may take
      or not, per occurrence.

Saturation runs in egglog; `export` reads the saturated e-graph back through
egglog's serializer (`EGraph._serialize`, a private API pinned by uv.lock to
egglog 14.0.0 and guarded by a test).

Purpose
-------
This file defines the VALUE-LEVEL e-graph: its sort `S` (a secret value held as a
sharing), the three rule sets, and the two operations the rest of the project
needs: `saturate` (grow the e-graph) and `export` (read it back as plain Python
data). Extraction itself is in `extract.py`; lowering to wires is in `gadgets.py`.

Why a separate layer? Refresh and gadget swaps preserve the secret but not the
wires, so they are not congruences on wire terms and cannot be e-graph rules there
(design/0010, 0016). Here a class means "this secret value", so they can be.

Notation used in the rules: `x`, `y`, `z` are pattern variables (any term of sort
`S`). `rewrite(L).to(R)` says "wherever L matches, R is equal to it".
"""

from __future__ import annotations

import json

from egglog import EGraph, Expr, StringLike, rewrite, ruleset
from gadgets import GADGETS


class S(Expr):
    """The egglog sort of shared values: a secret together with how it is produced.

    The bodies are `...` because egglog only needs the signatures; the rules below
    give the operators their meaning. `inp` is a secret input; `xor`, `isw`, `dom`
    and `hpc1` take another value; `refresh` and `not_` take none; `out` bundles two
    values into one root.
    """

    @classmethod
    def inp(cls, name: StringLike) -> S: ...
    def xor(self, other: S) -> S: ...
    def isw(self, other: S) -> S: ...
    def dom(self, other: S) -> S: ...
    def hpc1(self, other: S) -> S: ...
    def refresh(self) -> S: ...
    def not_(self) -> S: ...
    def out(self, other: S) -> S: ...


def _g(kind, x, y):
    """Apply the AND gadget named `kind` ("isw", "dom" or "hpc1") to `x` and `y`.

    `getattr(x, "isw")` is the method `x.isw`, so `_g("isw", x, y)` is `x.isw(y)`.
    This lets one rule definition be written once and repeated for every gadget.
    """
    return getattr(x, kind)(y)


@ruleset
def r1(x: S, y: S, z: S):
    """R1: Boolean identities on whole values (the rule set of ordinary algebra)."""
    yield rewrite(x.xor(y)).to(y.xor(x))  # XOR commutativity
    yield rewrite(x.xor(y).xor(z)).to(x.xor(y.xor(z)))  # XOR associativity, one way
    yield rewrite(x.xor(y.xor(z))).to(x.xor(y).xor(z))  # ... and the other way
    yield rewrite(x.not_().not_()).to(x)  # NOT is its own inverse
    for g in GADGETS:  # the same rules for each AND gadget g
        # a NOT can be pulled out of an AND:  (~x) & y  =  y ^ (x & y)
        yield rewrite(_g(g, x.not_(), y)).to(y.xor(_g(g, x, y)))
        yield rewrite(y.xor(_g(g, x, y))).to(_g(g, x.not_(), y))
        yield rewrite(_g(g, x, y)).to(_g(g, y, x))  # AND commutativity
        yield rewrite(_g(g, _g(g, x, y), z)).to(_g(g, x, _g(g, y, z)))  # AND assoc
        yield rewrite(_g(g, x, _g(g, y, z))).to(_g(g, _g(g, x, y), z))
        # distributivity over XOR, and its reverse (factoring)
        yield rewrite(_g(g, x, y.xor(z))).to(_g(g, x, y).xor(_g(g, x, z)))
        yield rewrite(_g(g, x, y).xor(_g(g, x, z))).to(_g(g, x, y.xor(z)))


@ruleset
def r2(x: S, y: S):
    """R2: the three AND gadgets compute the same secret value, so they are equal."""
    yield rewrite(x.isw(y)).to(x.dom(y))
    yield rewrite(x.dom(y)).to(x.hpc1(y))
    yield rewrite(x.hpc1(y)).to(x.isw(y))


@ruleset
def r3(x: S, y: S):
    """R3: refresh does not change the secret value (and may be inserted anywhere).

    The first rule makes `refresh(x)` and `x` one class (this is the self-loop that
    extraction may take or leave per occurrence). The two rules in the loop seed a
    refresh on either operand of every gadget, so there is always a refreshed
    candidate available.
    """
    yield rewrite(x.refresh()).to(x)
    for g in GADGETS:
        yield rewrite(_g(g, x, y)).to(_g(g, x.refresh(), y))
        yield rewrite(_g(g, x, y)).to(_g(g, x, y.refresh()))


RULESETS = {"R1": r1, "R2": r2, "R3": r3}  # name -> rule set, e.g. "R3" -> r3


def to_expr(term):
    """Convert a nested-tuple term (see `gadgets.py`) into an egglog `S` expression.

    Algorithm: recurse. An input becomes `S.inp(name)`; `refresh` and `not` call that
    method on the converted child; every other operator (xor, isw, dom, hpc1, out)
    calls the method of the same name on the left child with the right child.
    """
    op = term[0]
    if op == "in":
        return S.inp(term[1])
    if op == "refresh":
        return to_expr(term[1]).refresh()
    if op == "not":
        return to_expr(term[1]).not_()
    # getattr(left, "isw")(right) is left.isw(right): dispatch by operator name
    return getattr(to_expr(term[1]), op)(to_expr(term[2]))


def saturate(term, rule_classes, iters=8):
    """Build an egglog e-graph for `term`, run the chosen rule classes.

    Returns (egraph, root_handle). `rule_classes` is a subset of RULESETS keys.

    Algorithm, step by step:
      1. Create a fresh e-graph and add the term, naming it "root".
      2. If any rule classes were chosen, combine them into one schedule with `|`
         (run together each round), in sorted order so the result is deterministic.
      3. Run that schedule `iters` times (`schedule * iters` means "repeat").
    With no rule classes the e-graph just holds the original term.
    """
    eg = EGraph()
    root = eg.let("root", to_expr(term))  # handle to the term's class
    if rule_classes:
        schedule = None
        for name in sorted(rule_classes):
            # `a | b` runs both rule sets in the same round
            schedule = RULESETS[name] if schedule is None else schedule | RULESETS[name]
        eg.run(schedule * iters)
    return eg, root


def export(eg):
    """Read a saturated egglog e-graph as plain data.

    Returns (classes, root_class) where classes maps a class id to a list of
    nodes; a node is (op, child_class_ids) for operators and ("in", name) for
    inputs.

    Algorithm, step by step:
      1. Ask egglog to serialise the e-graph to JSON (a private API, pinned by the
         lockfile and covered by a test).
      2. Collect, for every egglog node, its class and operator. Skip the nodes that
         only hold string literals (input names), which belong to egglog's String
         sort and are not values of ours.
      3. An `inp` node has one child, a string node; read the name from that child's
         operator (JSON text, so `json.loads` removes the quotes).
      4. Any other operator becomes `(op, tuple of child class ids)`; `not_` is
         renamed `not` (`rstrip("_")`).
      5. Add each distinct node to its class's list, then find the root class (the
         one tagged "$root", the handle created in `saturate`).
    """
    ser = eg._serialize(
        max_functions=None, max_calls_per_function=None, n_inline_leaves=0
    )
    data = json.loads(ser.to_json())
    nodes = data["nodes"]  # node id -> {"eclass": ..., "op": ..., "children": [...]}
    # class id -> the egglog sort of that class, e.g. "S" or "String"
    sorts = {c: info.get("type") for c, info in data["class_data"].items()}
    classes = {}  # class id -> list of nodes, the result
    root = None
    for nid, node in nodes.items():
        cls = node["eclass"]  # the class this node belongs to
        if sorts.get(cls) == "String":
            continue  # a string literal (an input's name), not a value
        # operator names look like "S.xor"; keep the part after the last dot
        op = node["op"].rsplit(".", 1)[-1]
        if op == "inp":
            (child,) = node["children"]  # exactly one child: the name string
            entry = ("in", json.loads(nodes[child]["op"]))  # '"a"' -> "a"
        elif op in ("xor", "refresh", "not_", "out", *GADGETS):
            op = op.rstrip("_")  # "not_" -> "not"
            entry = (op, tuple(nodes[c]["eclass"] for c in node["children"]))
        else:
            raise ValueError(f"unexpected egglog node {nid}: {node['op']!r}")
        classes.setdefault(cls, [])
        if entry not in classes[cls]:  # keep each distinct node once
            classes[cls].append(entry)
    for cls, info in data["class_data"].items():
        if info.get("let") == "$root":  # the class we named "root" in `saturate`
            root = cls
    if root is None:
        raise ValueError("root class not found in the serialized e-graph")
    return classes, root
