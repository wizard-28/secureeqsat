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

Purpose
-------
This is how the project scales past the exact checkers. Instead of lowering and
checking every candidate circuit (which is exponential), it uses a theorem: a circuit
built ONLY from PINI gadgets is secure. So two cheap steps suffice: (1) mark which
e-classes can be built from PINI gadgets, (2) extract the cheapest PINI-only circuit,
one node per class, with no enumeration.

A tiny example: for the square `isw(z, refresh(z))` the node `isw` is not PINI, so the
class is not composable through it. After the gadget-swap rule R2 the class also holds
`hpc1(z, z)`, which is PINI, so the class IS composable and the extractor returns that,
at a higher cost (the price of the guarantee).
"""

import sys
from functools import cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "resharing"))

from gadgets import GADGETS  # noqa: E402
from pini import gadget_is_pini  # noqa: E402

# Cost of one operator on its own (gates + fresh randoms); the same table as the
# resharing extractor's, used here as the additive cost of a node.
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
INF = float("inf")  # "no cost known yet"


@cache
def pini_operators():
    """Operators whose lowering passes the exact 1-PINI check.

    The result is cached (`@cache`), so each gadget is checked exhaustively only once.
    Expected: xor, not, refresh and hpc1 pass; isw and dom fail. `out` is added by
    hand because it has no gates (see the comment below).
    """
    verified = {
        op for op in ("xor", "not", "refresh", *GADGETS) if gadget_is_pini(op)[0]
    }
    # `out` bundles several output sharings into one root and has no gates:
    # each output is its own composite, so it adds no probe.
    return frozenset(verified | {"out"})


def composable_classes(classes, ops=None):
    """Least fixed point: classes with a PINI node over composable children.

    Algorithm, step by step:
      1. Start with no class marked composable.
      2. Sweep the classes repeatedly. A class becomes composable if it has a node that
         is an input, OR a node whose operator is PINI and whose children are ALL
         already composable.
      3. Stop when a sweep marks nothing new. The marked classes are the answer.
    """
    ops = pini_operators() if ops is None else ops
    good = set()  # classes known to be composable
    changed = True
    while changed:
        changed = False
        for c, nodes in classes.items():
            if c in good:
                continue
            for node in nodes:
                # an input, or a PINI node whose child classes are all `good`
                if node[0] == "in" or (
                    node[0] in ops and all(k in good for k in node[1])
                ):
                    good.add(c)
                    changed = True
                    break  # one qualifying node is enough for this class
    return good


def extract_composable(classes, root, ops=None):
    """One node per class, PINI nodes only, cheapest by summed own cost.

    Returns the extracted term (a tree whose repeated subterms are shared by
    lowering) or None if the root is not composable.

    Algorithm, step by step (a cost fixed point, as in ordinary extraction):
      1. Repeatedly sweep every node of every class.
      2. An input costs 0. A PINI node whose child classes all already have a cost costs
         its own cost plus the sum of its children's costs. Any other node is ignored.
      3. Keep the cheapest node per class; stop when nothing improves.
      4. If the root class got no node, it is not composable: return None. Otherwise
         rebuild the chosen tree recursively from the root.
    """
    ops = pini_operators() if ops is None else ops
    cost, best = {}, {}  # class -> cheapest cost / the node achieving it
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
                    continue  # a non-PINI node, or a child with no cost yet
                if nc < cost.get(c, INF):
                    cost[c], best[c] = nc, node
                    changed = True
    if root not in best:
        return None  # the root has no PINI-only realisation

    def build(c):
        """Rebuild the chosen term for class `c` as a nested tuple."""
        node = best[c]
        if node[0] == "in":
            return node  # an input leaf, e.g. ("in", "a")
        # `(op, *children)` builds ("isw", left_tree, right_tree); the children are
        # class ids, rebuilt recursively
        return (node[0], *(build(k) for k in node[1]))

    return build(root)
