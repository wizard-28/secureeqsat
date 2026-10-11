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
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "premise_test"))

from masked import Circuit  # noqa: E402

GADGETS = ("isw", "dom", "hpc1")  # the AND gadgets (R2 equates them)
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
    """Lower one or more terms into a single circuit with shared subterms."""

    def __init__(self):
        self.circ = Circuit()
        self.randoms = []
        self._memo = {}

    def fresh(self):
        name = f"r{len(self.randoms) + 1}"
        self.randoms.append(name)
        return self.circ.add_input(name)

    def lower(self, term):
        """Return the (share0, share1) wire names of `term`.

        For an `out` bundle, the concatenated share pairs of its children.
        """
        if term in self._memo:
            return self._memo[term]
        op = term[0]
        c = self.circ
        if op == "in":
            out = (c.add_input(f"{term[1]}0"), c.add_input(f"{term[1]}1"))
        elif op == "xor":
            x0, x1 = self.lower(term[1])
            y0, y1 = self.lower(term[2])
            out = (c.add_gate("xor", x0, y0), c.add_gate("xor", x1, y1))
        elif op == "not":
            x0, x1 = self.lower(term[1])
            out = (c.add_gate("xor", x0, c.add_const(1)), x1)
        elif op == "out":
            out = self.lower(term[1]) + self.lower(term[2])
        elif op == "refresh":
            out = self._refresh(self.lower(term[1]))
        elif op in GADGETS:
            x = self.lower(term[1])
            y = self.lower(term[2])
            if op == "isw":
                out = self._isw(x, y)
            elif op == "dom":
                out = self._dom(x, y)
            else:
                out = self._dom(x, self._refresh(y))
        else:
            raise ValueError(f"unknown operator {op!r}")
        self._memo[term] = out
        return out

    def _refresh(self, x):
        r = self.fresh()
        return (self.circ.add_gate("xor", x[0], r), self.circ.add_gate("xor", x[1], r))

    def _isw(self, x, y):
        c, r = self.circ, self.fresh()
        (x0, x1), (y0, y1) = x, y
        c0 = c.add_gate("xor", c.add_gate("and", x0, y0), r)
        w1 = c.add_gate("xor", r, c.add_gate("and", x0, y1))
        w2 = c.add_gate("xor", w1, c.add_gate("and", x1, y0))
        c1 = c.add_gate("xor", w2, c.add_gate("and", x1, y1))
        return c0, c1

    def _dom(self, x, y):
        c, r = self.circ, self.fresh()
        (x0, x1), (y0, y1) = x, y
        y2 = c.add_gate("xor", c.add_gate("and", x0, y1), r)
        u2 = c.add_gate("xor", c.add_gate("and", x1, y0), r)
        c0 = c.add_gate("xor", c.add_gate("and", x0, y0), y2)
        c1 = c.add_gate("xor", c.add_gate("and", x1, y1), u2)
        return c0, c1


def secrets_of(term, acc=None):
    """Sorted secret names the term reads."""
    if acc is None:
        acc = set()
    if term[0] == "in":
        acc.add(term[1])
    else:
        for t in term[1:]:
            secrets_of(t, acc)
    return sorted(acc)


def lower(terms):
    """Lower a list of root terms; returns the Lowering (circuit, randoms)."""
    low = Lowering()
    for t in terms:
        low.circ.outputs.extend(low.lower(t))
    return low


def cost_of(low):
    """Cost model of design/0016: one gate = one random = 1."""
    return low.circ.gate_count() + len(low.randoms)


def secret_groups(names):
    return {s: [f"{s}0", f"{s}1"] for s in names}


def free_vars(names, randoms):
    return [f"{s}0" for s in names] + list(randoms)


def value(term, env):
    """The unmasked Boolean value a term reconstructs to, given secret values."""
    op = term[0]
    if op == "in":
        return env[term[1]]
    if op == "refresh":
        return value(term[1], env)
    if op == "not":
        return 1 - value(term[1], env)
    a, b = value(term[1], env), value(term[2], env)
    if op == "out":
        return (a, b)
    return a ^ b if op == "xor" else a & b


def show(term):
    op = term[0]
    if op == "in":
        return term[1]
    return f"{op}({', '.join(show(t) for t in term[1:])})"
