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
"""

from __future__ import annotations

import json

from egglog import EGraph, Expr, StringLike, rewrite, ruleset
from gadgets import GADGETS


class S(Expr):
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
    return getattr(x, kind)(y)


@ruleset
def r1(x: S, y: S, z: S):
    yield rewrite(x.xor(y)).to(y.xor(x))
    yield rewrite(x.xor(y).xor(z)).to(x.xor(y.xor(z)))
    yield rewrite(x.xor(y.xor(z))).to(x.xor(y).xor(z))
    yield rewrite(x.not_().not_()).to(x)
    for g in GADGETS:
        yield rewrite(_g(g, x.not_(), y)).to(y.xor(_g(g, x, y)))
        yield rewrite(y.xor(_g(g, x, y))).to(_g(g, x.not_(), y))
        yield rewrite(_g(g, x, y)).to(_g(g, y, x))
        yield rewrite(_g(g, _g(g, x, y), z)).to(_g(g, x, _g(g, y, z)))
        yield rewrite(_g(g, x, _g(g, y, z))).to(_g(g, _g(g, x, y), z))
        yield rewrite(_g(g, x, y.xor(z))).to(_g(g, x, y).xor(_g(g, x, z)))
        yield rewrite(_g(g, x, y).xor(_g(g, x, z))).to(_g(g, x, y.xor(z)))


@ruleset
def r2(x: S, y: S):
    yield rewrite(x.isw(y)).to(x.dom(y))
    yield rewrite(x.dom(y)).to(x.hpc1(y))
    yield rewrite(x.hpc1(y)).to(x.isw(y))


@ruleset
def r3(x: S, y: S):
    yield rewrite(x.refresh()).to(x)
    for g in GADGETS:
        yield rewrite(_g(g, x, y)).to(_g(g, x.refresh(), y))
        yield rewrite(_g(g, x, y)).to(_g(g, x, y.refresh()))


RULESETS = {"R1": r1, "R2": r2, "R3": r3}


def to_expr(term):
    op = term[0]
    if op == "in":
        return S.inp(term[1])
    if op == "refresh":
        return to_expr(term[1]).refresh()
    if op == "not":
        return to_expr(term[1]).not_()
    return getattr(to_expr(term[1]), op)(to_expr(term[2]))


def saturate(term, rule_classes, iters=8):
    """Build an egglog e-graph for `term`, run the chosen rule classes.

    Returns (egraph, root_handle). `rule_classes` is a subset of RULESETS keys.
    """
    eg = EGraph()
    root = eg.let("root", to_expr(term))
    if rule_classes:
        schedule = None
        for name in sorted(rule_classes):
            schedule = RULESETS[name] if schedule is None else schedule | RULESETS[name]
        eg.run(schedule * iters)
    return eg, root


def export(eg):
    """Read a saturated egglog e-graph as plain data.

    Returns (classes, root_class) where classes maps a class id to a list of
    nodes; a node is (op, child_class_ids) for operators and ("in", name) for
    inputs.
    """
    ser = eg._serialize(
        max_functions=None, max_calls_per_function=None, n_inline_leaves=0
    )
    data = json.loads(ser.to_json())
    nodes = data["nodes"]
    sorts = {c: info.get("type") for c, info in data["class_data"].items()}
    classes = {}
    root = None
    for nid, node in nodes.items():
        cls = node["eclass"]
        if sorts.get(cls) == "String":
            continue
        op = node["op"].rsplit(".", 1)[-1]
        if op == "inp":
            (child,) = node["children"]
            entry = ("in", json.loads(nodes[child]["op"]))
        elif op in ("xor", "refresh", "not_", "out", *GADGETS):
            op = op.rstrip("_")
            entry = (op, tuple(nodes[c]["eclass"] for c in node["children"]))
        else:
            raise ValueError(f"unexpected egglog node {nid}: {node['op']!r}")
        classes.setdefault(cls, [])
        if entry not in classes[cls]:
            classes[cls].append(entry)
    for cls, info in data["class_data"].items():
        if info.get("let") == "$root":
            root = cls
    if root is None:
        raise ValueError("root class not found in the serialized e-graph")
    return classes, root
