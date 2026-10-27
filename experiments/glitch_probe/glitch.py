"""Glitch-extended first-order probing checker (feasibility probe, design/0017).

Model (robust probing with glitches, first order, 2 shares):
    A probe on a wire observes every *stable* signal in its combinational
    cone: primary inputs and register outputs, up to the nearest register.
    The circuit is glitch-extended first-order secure iff, for every wire, the
    joint distribution of its stable set is independent of the secrets.

This mirrors VerifMSI's own semantics (`hw.py`: a gate's `leakageOut` is the
union of its inputs'; a register's is its input's expression), which the
cross-check in `glitch_driver.py` uses as the independent reference.

Joint distributions are checked through parities: the distribution of a bit
vector is determined by the biases of the XOR of every non-empty subset of its
bits (Walsh-Hadamard), so a stable set S is safe iff every subset parity is
first-order safe. That reuses the bitsliced labeller's per-table test.
Cost is 2**|S| table checks per wire; fine for gadget-sized cones.

Purpose
-------
In the basic model a probe sees one wire's value. In hardware, glitches let a probe
effectively see every signal the wire was built from, back to the nearest register or
input (its "stable set"). This module adds registers to circuits and checks security
under that stronger model. Two verdicts are available per wire: the glitch-extended
one (`check_glitch`) and the ordinary one (`check_glitch_free`).

A worked example: for the wire `w = (a0 & b1) ^ r` with no register, the stable set
is {a0, b1, r}. The probe sees all three at once. Putting a register on `a0 & b1`
makes the stable set of `w` just {reg(a0&b1), r}, so a0 and b1 are no longer seen.
"""

import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "labeller"))

from labeller import DEFAULT_MAX_BITS, TruthSpace  # noqa: E402

# The wire kinds that a glitch-extended probe can SEE as stable signals: an input, and
# the output of a register (which holds its value steady).
STABLE_OPS = ("input", "reg")


class GCircuit:
    """Straight-line circuit with registers. Wires are hash-consed by structure.

    Like `masked.Circuit`, but with a fourth wire kind, "reg" (a register). Each wire
    is stored once as `(name, op, args)`; adding an identical wire twice returns the
    same name.
    """

    def __init__(self):
        """Create an empty circuit."""
        # (name, op, args), e.g. ("reg(and(a0,b1))", "reg", ("and(a0,b1)",))
        self.wires = []
        self.outputs = []  # names of the output wires
        self._names = set()  # names already used, to avoid adding a wire twice

    def _add(self, name, op, args):
        """Add a wire unless one with this name exists; return the name."""
        if name not in self._names:
            self._names.add(name)
            self.wires.append((name, op, args))
        return name

    def add_input(self, name):
        """Declare an input wire."""
        return self._add(name, "input", name)

    def add_const(self, v):
        """Add the constant 0 or 1 (any truthy value gives 1)."""
        # int(bool(v)) turns any value into exactly 0 or 1
        return self._add(f"const{int(bool(v))}", "const", int(bool(v)))

    def add_gate(self, op, a, b):
        """Add an AND or XOR of the wires named `a` and `b`."""
        if op not in ("and", "xor"):
            raise ValueError(op)
        return self._add(f"{op}({a},{b})", op, (a, b))

    def add_reg(self, a):
        """Add a register holding the value of wire `a`."""
        return self._add(f"reg({a})", "reg", (a,))

    def count(self, *ops):
        """Number of wires whose op is one of `ops`, e.g. `count("and", "xor")`."""
        return sum(1 for _, op, _ in self.wires if op in ops)


def tables(circ, space):
    """Truth table (a Python int) of every wire, as in the bitsliced labeller.

    Algorithm: walk the wires in order. An input takes its table from `space`, a
    constant becomes all ones or zeros, a register has the SAME table as its input
    (it only delays the value, it does not change it), and an XOR or AND is one
    bitwise `^` or `&` of the operand tables.
    """
    out = {}  # wire name -> integer truth table
    for name, op, args in circ.wires:
        if op == "input":
            out[name] = space.var(name)
        elif op == "const":
            out[name] = space.const(args)
        elif op == "reg":
            out[name] = out[args[0]]  # a register passes its input's value through
        elif op == "xor":
            out[name] = out[args[0]] ^ out[args[1]]
        elif op == "and":
            out[name] = out[args[0]] & out[args[1]]
        else:
            raise ValueError(op)
    return out


def stable_sets(circ):
    """{wire: frozenset of stable wires (inputs, registers) in its cone}.

    Algorithm: an input or register is its own stable signal (so its set is just
    itself, which is what makes a register CUT the cone). A constant sees nothing. A
    gate sees everything its two operands see, so its set is the union of theirs.
    """
    out = {}  # wire name -> its stable set
    for name, op, args in circ.wires:
        if op in STABLE_OPS:
            out[name] = frozenset([name])  # a one-element set containing itself
        elif op == "const":
            out[name] = frozenset()  # an empty set: a constant leaks nothing
        else:
            out[name] = out[args[0]] | out[args[1]]  # `|` on sets is union
    return out


def joint_safe(tabs, space):
    """Is the joint distribution of these tables independent of the secrets?

    Algorithm, step by step:
      1. For every non-empty subset of the tables (sizes 1 to n), XOR its tables
         together to get one "parity" table. (The joint distribution of several
         bits is fixed by the biases of all these parities.)
      2. Ask the labeller whether that parity is safe (same count of 1s in every
         secret block).
      3. If any parity is unsafe, the joint distribution depends on the secret.
    There are 2**n - 1 subsets, so this is only used on small stable sets.
    """
    tabs = list(tabs)
    for k in range(1, len(tabs) + 1):  # subset sizes 1 .. n
        for subset in itertools.combinations(tabs, k):  # all subsets of size k
            parity = 0  # XOR of the subset's tables; starts as all zeros
            for t in subset:
                parity ^= t  # `^=` XORs table t into the running parity
            if not space.is_safe(parity):
                return False
    return True


def check_glitch(circ, secret_groups, free_vars, max_bits=DEFAULT_MAX_BITS):
    """{wire: bool} -- glitch-extended first-order verdict per probe.

    Algorithm, step by step:
      1. Build the truth space and every wire's table.
      2. Compute each wire's stable set.
      3. For each wire, take the tables of the signals in its stable set (equal tables
         counted once) and ask `joint_safe`. The answer is cached per stable set, since
         many wires share one.
    """
    space = TruthSpace(secret_groups, free_vars, max_bits)
    tabs = tables(circ, space)  # wire -> truth table
    sets = stable_sets(circ)  # wire -> its stable set
    cache = {}  # stable set -> verdict, so each distinct set is checked once
    out = {}
    for name, _, _ in circ.wires:
        s = sets[name]
        if s not in cache:
            # equal tables are one signal: dedupe so a register of an input
            # does not count twice
            cache[s] = joint_safe(sorted({tabs[w] for w in s}), space)
        out[name] = cache[s]
    return out


def check_glitch_free(circ, secret_groups, free_vars, max_bits=DEFAULT_MAX_BITS):
    """{wire: bool} -- the standard glitch-free first-order verdict per wire.

    Same test as `labeller.check_first_order_bitsliced` (a wire is safe iff the count
    of 1s in its table is equal in every secret block), but registers are understood.
    """
    space = TruthSpace(secret_groups, free_vars, max_bits)
    return {w: space.is_safe(t) for w, t in tables(circ, space).items()}
