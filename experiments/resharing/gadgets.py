"""Gadget lowering: shared-value terms to 2-share wire circuits.

A *shared-value term* (design/0016) names what a sharing reconstructs to and
which gadget produces it, but not its shares. Lowering instantiates a term as a
`masked.Circuit`, allocating a fresh random for every gadget instance that
needs one. Identical subterms are lowered once (common-subexpression sharing),
so a term reused twice reuses the same sharing -- which is exactly the case in
which a refresh can be needed.

Terms are nested tuples:

    ("in", name)          shares name0, name1 of secret `name`
    ("xor", x, y)         share-wise XOR: (x0 ^ y0, x1 ^ y1)
    ("not", x)            share-wise NOT: (x0 ^ 1, x1)
    ("out", x, y)         bundles several outputs into one root (no gates)
    ("refresh", x)        (x0 ^ r, x1 ^ r)
    ("isw", x, y)         ISW AND, r folded into every c1 intermediate
    ("dom", x, y)         DOM-indep AND, glitch-free model (registers elided)
    ("hpc1", x, y)        HPC1 = DOM with its second operand refreshed

Gadget structures are transcribed from `masked.build_isw_and` and
`masked.build_dom_and` (both already cross-checked against VerifMSI). HPC1 is
"a DOM-AND gadget and additionally refreshing one of the inputs" (Knichel and
Moradi, *Low-Latency Hardware Private Circuits*, CCS 2022, sec. 4.1, fetched
2026-10-11), with 2 random bits at first order; HPC2 is not modelled because
its share equations were not fetched (UNVERIFIED).

Glitch-free model only: HPC1's reason to exist is robustness to glitches,
which this model does not see.

Purpose
-------
This is the bridge between the two layers of the project. The VALUE layer (the
egglog e-graph in `layer.py`) talks about secrets and gadgets. The WIRE layer (the
checker) needs real gates. `lower` translates the first into the second so that a
candidate can be costed (gates + random bits) and security-checked.

A worked example: the term `("isw", ("in", "a"), ("in", "b"))` lowers to the inputs
a0, a1, b0, b1 and one random r1, then the 8 gates of the ISW gadget. The term
`("xor", ("in", "a"), ("in", "b"))` lowers to just two gates, `a0^b0` and `a1^b1`,
and no random.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "premise_test"))

from masked import Circuit  # noqa: E402

GADGETS = ("isw", "dom", "hpc1")  # the AND gadgets (R2 equates them)
# How many fresh random bits each operator consumes when lowered. HPC1 needs 2: one
# for its DOM core and one for the refresh of its second operand.
RANDOMS_PER_OP = {
    "in": 0,
    "xor": 0,
    "not": 0,
    "out": 0,
    "refresh": 1,
    "isw": 1,
    "dom": 1,
    "hpc1": 2,
}


class Lowering:
    """Lower one or more terms into a single circuit with shared subterms.

    Attributes:
        circ: the `Circuit` being built.
        randoms: names of the fresh random inputs allocated so far, e.g. ["r1", "r2"].
        _memo: term -> its (share0, share1) wire names, so a repeated subterm is
            lowered once and every user gets the SAME sharing.
    """

    def __init__(self):
        """Start with an empty circuit, no randoms and an empty memo table."""
        self.circ = Circuit()
        self.randoms = []  # e.g. ["r1", "r2"]
        self._memo = {}  # e.g. {("in", "a"): ("a0", "a1")}

    def fresh(self):
        """Allocate a new fresh random input (r1, r2, ...) and return its wire name."""
        name = f"r{len(self.randoms) + 1}"  # next unused name, e.g. "r3"
        self.randoms.append(name)
        return self.circ.add_input(name)

    def lower(self, term):
        """Return the (share0, share1) wire names of `term`.

        For an `out` bundle, the concatenated share pairs of its children.

        Algorithm, step by step:
          1. If this exact term was lowered before, return the stored shares (this is
             what makes a term used twice reuse one sharing).
          2. Otherwise dispatch on the operator:
               in       -> declare inputs `name0` and `name1`.
               xor      -> lower both children, XOR the shares pairwise.
               not      -> XOR share 0 with the constant 1, leave share 1 alone.
               out      -> lower both children and concatenate the share tuples.
               refresh  -> lower the child, then `_refresh` it.
               isw/dom  -> lower both operands, then build that gadget.
               hpc1     -> like dom, but the second operand is refreshed first.
          3. Remember the result in the memo and return it.
        """
        if term in self._memo:
            return self._memo[term]
        op = term[0]  # the operator name, e.g. "isw"
        c = self.circ  # shorthand for the circuit being built
        if op == "in":
            out = (c.add_input(f"{term[1]}0"), c.add_input(f"{term[1]}1"))
        elif op == "xor":
            x0, x1 = self.lower(term[1])  # shares of the left operand
            y0, y1 = self.lower(term[2])  # shares of the right operand
            out = (c.add_gate("xor", x0, y0), c.add_gate("xor", x1, y1))
        elif op == "not":
            x0, x1 = self.lower(term[1])
            # NOT flips the secret by flipping ONE share: (x0 ^ 1) ^ x1 = ~(x0 ^ x1)
            out = (c.add_gate("xor", x0, c.add_const(1)), x1)
        elif op == "out":
            # tuple + tuple concatenates: (x0, x1) + (y0, y1) = (x0, x1, y0, y1)
            out = self.lower(term[1]) + self.lower(term[2])
        elif op == "refresh":
            out = self._refresh(self.lower(term[1]))
        elif op in GADGETS:
            x = self.lower(term[1])  # (share0, share1) of the first operand
            y = self.lower(term[2])  # (share0, share1) of the second operand
            if op == "isw":
                out = self._isw(x, y)
            elif op == "dom":
                out = self._dom(x, y)
            else:  # hpc1: DOM whose second operand is refreshed first
                out = self._dom(x, self._refresh(y))
        else:
            raise ValueError(f"unknown operator {op!r}")
        self._memo[term] = out
        return out

    def _refresh(self, x):
        """Refresh a sharing: XOR one fresh random into BOTH shares.

        `(x0, x1) -> (x0 ^ r, x1 ^ r)`. The secret x0 ^ x1 is unchanged because the
        two copies of r cancel, but the shares are now independent of the old ones.
        """
        r = self.fresh()
        return (self.circ.add_gate("xor", x[0], r), self.circ.add_gate("xor", x[1], r))

    def _isw(self, x, y):
        """ISW masked AND of two sharings; returns the output share pair.

        Same wiring as `masked.build_isw_and`: r masks the first output share, and
        enters the second output's XOR chain FIRST so every partial sum is masked.
        """
        c, r = self.circ, self.fresh()  # c: circuit; r: this gadget's fresh random
        (x0, x1), (y0, y1) = x, y  # unpack the two share pairs
        c0 = c.add_gate("xor", c.add_gate("and", x0, y0), r)  # x0*y0 ^ r
        w1 = c.add_gate("xor", r, c.add_gate("and", x0, y1))  # r ^ x0*y1
        w2 = c.add_gate("xor", w1, c.add_gate("and", x1, y0))  # ... ^ x1*y0
        c1 = c.add_gate("xor", w2, c.add_gate("and", x1, y1))  # ... ^ x1*y1
        return c0, c1

    def _dom(self, x, y):
        """DOM-indep masked AND (glitch-free, registers omitted); returns shares.

        Same wiring as `masked.build_dom_and`: each cross product is masked by r
        before being combined with the same-domain product.
        """
        c, r = self.circ, self.fresh()
        (x0, x1), (y0, y1) = x, y
        y2 = c.add_gate("xor", c.add_gate("and", x0, y1), r)  # x0*y1 masked by r
        u2 = c.add_gate("xor", c.add_gate("and", x1, y0), r)  # x1*y0 masked by r
        c0 = c.add_gate("xor", c.add_gate("and", x0, y0), y2)  # output share 0
        c1 = c.add_gate("xor", c.add_gate("and", x1, y1), u2)  # output share 1
        return c0, c1


def secrets_of(term, acc=None):
    """Sorted secret names the term reads.

    Walks the term recursively and collects the name of every ("in", name) leaf.
    `acc` is the accumulating set (created on the first call). Example:
    `("isw", ("in", "a"), ("in", "b"))` gives `["a", "b"]`.
    """
    if acc is None:
        acc = set()
    if term[0] == "in":
        acc.add(term[1])
    else:
        for t in term[1:]:  # every element after the operator name is a subterm
            secrets_of(t, acc)
    return sorted(acc)


def lower(terms):
    """Lower a list of root terms; returns the Lowering (circuit, randoms).

    Each root's output shares become outputs of the circuit. Sharing is kept across
    roots because they all use one `Lowering` (and hence one memo table).
    """
    low = Lowering()
    for t in terms:
        low.circ.outputs.extend(low.lower(t))  # append the root's share wires
    return low


def cost_of(low):
    """Cost model of design/0016: one gate = one random = 1.

    So the cost of a lowered circuit is its number of gates plus the number of
    fresh random bits it uses.
    """
    return low.circ.gate_count() + len(low.randoms)


def secret_groups(names):
    """Secret-group dict for the checker: each secret has shares `<s>0` and `<s>1`.

    Example: `["a", "b"]` gives `{"a": ["a0", "a1"], "b": ["b0", "b1"]}`.
    """
    return {s: [f"{s}0", f"{s}1"] for s in names}


def free_vars(names, randoms):
    """Free (uniform) variables for the checker: share 0 of each secret + randoms.

    Example: `(["a", "b"], ["r1"])` gives `["a0", "b0", "r1"]`.
    """
    return [f"{s}0" for s in names] + list(randoms)


def value(term, env):
    """The unmasked Boolean value a term reconstructs to, given secret values.

    Args:
        term: a shared-value term.
        env: `{secret_name: 0 or 1}`.

    A refresh does not change the value, NOT flips it, and `out` returns a tuple of
    its two children's values. XOR uses `^`, any AND gadget uses `&`.
    """
    op = term[0]
    if op == "in":
        return env[term[1]]
    if op == "refresh":
        return value(term[1], env)  # same secret, different shares
    if op == "not":
        return 1 - value(term[1], env)  # 1 - v flips a 0/1 value
    a, b = value(term[1], env), value(term[2], env)  # values of the two operands
    if op == "out":
        return (a, b)
    return a ^ b if op == "xor" else a & b  # any gadget (isw/dom/hpc1) is an AND


def show(term):
    """Readable text for a term, e.g. `isw(a, refresh(b))`."""
    op = term[0]
    if op == "in":
        return term[1]
    return f"{op}({', '.join(show(t) for t in term[1:])})"
