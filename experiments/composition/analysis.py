"""Composition analysis and class-level extraction on the shared-value layer.

The analysis (design/0019) labels an e-class *composable* when it holds at
least one node whose operator is a verified 1-PINI gadget and whose children
are all composable; inputs are composable. It is the least fixed point of
that rule over the saturated e-graph -- an e-class analysis computed after
saturation on the exported e-graph.

Why that is enough for security: a circuit built only from d-PINI gadgets is
d-PINI (Cassiers & Standaert, Property 12: "A composite gadget made of d-PINI
composing gadgets is d-PINI"), and a d-PINI gadget is d-probing secure when
its input encodings are independent of each other (Property 11). Our primary
inputs are independent sharings, and composition allows a gadget output to
feed several later gadgets, so sharing a subterm (one node per class) is fine.

So on composable classes safety IS a class label again, and ordinary
one-node-per-class extraction restricted to PINI nodes returns a secure
circuit without any enumeration -- at any size.

The set of PINI operators is not assumed: `pini_operators()` checks every
gadget's lowering with the exact checker in pini.py (and the test suite
cross-checks it with VerifMSI's PINI mode).
"""

import sys
from functools import cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "resharing"))

from gadgets import GADGETS  # noqa: E402
from pini import gadget_is_pini  # noqa: E402

OWN = {
    "in": 0,
    "out": 0,
    "xor": 2,
    "not": 1,
    "refresh": 3,
    "isw": 9,
    "dom": 9,
    "hpc1": 12,
}
INF = float("inf")


@cache
def pini_operators():
    """Operators whose lowering passes the exact 1-PINI check."""
    verified = {
        op for op in ("xor", "not", "refresh", *GADGETS) if gadget_is_pini(op)[0]
    }
    # `out` bundles several output sharings into one root and has no gates:
    # each output is its own composite, so it adds no probe.
    return frozenset(verified | {"out"})


def composable_classes(classes, ops=None):
    """Least fixed point: classes with a PINI node over composable children."""
    ops = pini_operators() if ops is None else ops
    good = set()
    changed = True
    while changed:
        changed = False
        for c, nodes in classes.items():
            if c in good:
                continue
            for node in nodes:
                if node[0] == "in" or (
                    node[0] in ops and all(k in good for k in node[1])
                ):
                    good.add(c)
                    changed = True
                    break
    return good


def extract_composable(classes, root, ops=None):
    """One node per class, PINI nodes only, cheapest by summed own cost.

    Returns the extracted term (a tree whose repeated subterms are shared by
    lowering) or None if the root is not composable.
    """
    ops = pini_operators() if ops is None else ops
    cost, best = {}, {}
    changed = True
    while changed:
        changed = False
        for c, nodes in classes.items():
            for node in nodes:
                if node[0] == "in":
                    nc = 0
                elif node[0] in ops and all(k in cost for k in node[1]):
                    nc = OWN[node[0]] + sum(cost[k] for k in node[1])
                else:
                    continue
                if nc < cost.get(c, INF):
                    cost[c], best[c] = nc, node
                    changed = True
    if root not in best:
        return None

    def build(c):
        node = best[c]
        if node[0] == "in":
            return node
        return (node[0], *(build(k) for k in node[1]))

    return build(root)
