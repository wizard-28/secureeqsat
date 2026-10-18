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
"""

import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "labeller"))

from labeller import DEFAULT_MAX_BITS, TruthSpace  # noqa: E402

STABLE_OPS = ("input", "reg")


class GCircuit:
    """Straight-line circuit with registers. Wires are hash-consed by structure."""

    def __init__(self):
        self.wires = []  # (name, op, args)
        self.outputs = []
        self._names = set()

    def _add(self, name, op, args):
        if name not in self._names:
            self._names.add(name)
            self.wires.append((name, op, args))
        return name

    def add_input(self, name):
        return self._add(name, "input", name)

    def add_const(self, v):
        return self._add(f"const{int(bool(v))}", "const", int(bool(v)))

    def add_gate(self, op, a, b):
        if op not in ("and", "xor"):
            raise ValueError(op)
        return self._add(f"{op}({a},{b})", op, (a, b))

    def add_reg(self, a):
        return self._add(f"reg({a})", "reg", (a,))

    def count(self, *ops):
        return sum(1 for _, op, _ in self.wires if op in ops)


def tables(circ, space):
    out = {}
    for name, op, args in circ.wires:
        if op == "input":
            out[name] = space.var(name)
        elif op == "const":
            out[name] = space.const(args)
        elif op == "reg":
            out[name] = out[args[0]]
        elif op == "xor":
            out[name] = out[args[0]] ^ out[args[1]]
        elif op == "and":
            out[name] = out[args[0]] & out[args[1]]
        else:
            raise ValueError(op)
    return out


def stable_sets(circ):
    """{wire: frozenset of stable wires (inputs, registers) in its cone}."""
    out = {}
    for name, op, args in circ.wires:
        if op in STABLE_OPS:
            out[name] = frozenset([name])
        elif op == "const":
            out[name] = frozenset()
        else:
            out[name] = out[args[0]] | out[args[1]]
    return out


def joint_safe(tabs, space):
    """Is the joint distribution of these tables independent of the secrets?"""
    tabs = list(tabs)
    for k in range(1, len(tabs) + 1):
        for subset in itertools.combinations(tabs, k):
            parity = 0
            for t in subset:
                parity ^= t
            if not space.is_safe(parity):
                return False
    return True


def check_glitch(circ, secret_groups, free_vars, max_bits=DEFAULT_MAX_BITS):
    """{wire: bool} -- glitch-extended first-order verdict per probe."""
    space = TruthSpace(secret_groups, free_vars, max_bits)
    tabs = tables(circ, space)
    sets = stable_sets(circ)
    cache = {}
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
    """{wire: bool} -- the standard glitch-free first-order verdict per wire."""
    space = TruthSpace(secret_groups, free_vars, max_bits)
    return {w: space.is_safe(t) for w, t in tables(circ, space).items()}
