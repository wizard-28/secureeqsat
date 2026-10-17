"""Bitsliced exact first-order labeller.

Same security model and the same verdicts as `masked.check_first_order`
(first order, 2 shares, glitch-free, straight-line), computed differently:

  * Every wire's Boolean function is held as ONE truth table over the whole
    (secret, free-variable) assignment space, packed into a Python int. AND
    and XOR of two wires are single bitwise operations on those ints, instead
    of one `evaluate()` call per assignment.
  * Bit index i = sbits * 2**F + fbits, where bit k of `sbits` is secret k and
    bit j of `fbits` is free variable j -- the enumeration order of
    `check_first_order`. Each secret assignment is therefore a contiguous block
    of 2**F bits.
  * A wire is first-order safe iff its number of 1s is the same in every
    secret block (its distribution over the free variables does not depend on
    the secrets). That is one `int.bit_count()` per block.

For an e-graph, first-order safety is a property of the function a class
computes, so each class gets one table, computed bottom-up from its children
in a single fixed point -- no per-class circuit materialisation. As a side
effect, `class_tables(check=True)` verifies that every node in a class computes
the same table, which catches an unsound rewrite rule.

Still exact and still exponential: memory per table is 2**(secrets + free
variables) bits. `max_bits` refuses spaces that would exhaust memory rather
than failing slowly. Beyond that a symbolic labeller is needed (deferred).

Stdlib only.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "premise_test"))

DEFAULT_MAX_BITS = 26  # 2**26 bits = 8 MiB per table


class InconsistentClassError(Exception):
    """Two nodes in one e-class compute different Boolean functions."""


def _replicate(pattern, width, total):
    """Tile a `width`-bit pattern until it covers `total` bits (both powers of 2)."""
    while width < total:
        pattern |= pattern << width
        width *= 2
    return pattern


def _half_pattern(h, total):
    """`total`-bit table that is 0 for h bits, then 1 for h bits, repeating."""
    return _replicate(((1 << h) - 1) << h, 2 * h, total)


class TruthSpace:
    """The (secret, free-variable) assignment space and its input truth tables.

    secret_groups: {secret: [share_names]}; shares[0] is the free uniform share,
                   every further share is reconstructed as shares[0] ^ secret
                   (exactly as in `check_first_order`).
    free_vars:     all uniform free inputs: shares[0] of every secret plus every
                   fresh random.
    """

    def __init__(self, secret_groups, free_vars, max_bits=DEFAULT_MAX_BITS):
        self.secrets = list(secret_groups)
        self.free_vars = list(free_vars)
        nbits = len(self.secrets) + len(self.free_vars)
        if nbits > max_bits:
            raise ValueError(
                f"assignment space has 2**{nbits} points (> 2**{max_bits}); "
                "the bitsliced labeller would need too much memory"
            )
        if len(set(self.free_vars)) != len(self.free_vars):
            raise ValueError("free_vars contains duplicates")

        self.block = 1 << len(self.free_vars)  # bits per secret assignment
        self.nblocks = 1 << len(self.secrets)
        self.size = self.block * self.nblocks
        self.full = (1 << self.size) - 1
        self._block_mask = (1 << self.block) - 1

        tables = {
            v: _half_pattern(1 << j, self.size) for j, v in enumerate(self.free_vars)
        }
        secret_tt = {
            s: _half_pattern(self.block << k, self.size)
            for k, s in enumerate(self.secrets)
        }
        for s, shares in secret_groups.items():
            if not shares or shares[0] not in tables:
                raise ValueError(
                    f"first share of secret {s!r} must be listed in free_vars"
                )
            for x in shares[1:]:
                if x in tables:
                    raise ValueError(
                        f"share {x!r} is reconstructed from {shares[0]!r} and "
                        "must not also be a free variable"
                    )
                tables[x] = tables[shares[0]] ^ secret_tt[s]
        self._inputs = tables

    def var(self, name):
        try:
            return self._inputs[name]
        except KeyError:
            raise ValueError(
                f"input {name!r} is neither a free variable nor a share"
            ) from None

    def const(self, value):
        return self.full if value else 0

    def is_safe(self, table):
        """True iff the table's count of 1s is identical in every secret block."""
        mask = self._block_mask
        base = (table & mask).bit_count()
        return all(
            ((table >> (k * self.block)) & mask).bit_count() == base
            for k in range(1, self.nblocks)
        )


# ---- circuits --------------------------------------------------------


def circuit_tables(circ, space):
    """{wire_name: truth table} for a `masked.Circuit`."""
    tables = {}
    for name, op, payload in circ.wires:
        if op == "input":
            tables[name] = space.var(name)
        elif op == "const":
            tables[name] = space.const(payload)
        elif op == "xor":
            tables[name] = tables[payload[0]] ^ tables[payload[1]]
        elif op == "and":
            tables[name] = tables[payload[0]] & tables[payload[1]]
        else:
            raise ValueError(op)
    return tables


def check_first_order_bitsliced(
    circ, secret_groups, free_vars, max_bits=DEFAULT_MAX_BITS
):
    """Drop-in for `masked.check_first_order`: returns {wire_name: bool_safe}."""
    space = TruthSpace(secret_groups, free_vars, max_bits)
    return {w: space.is_safe(t) for w, t in circuit_tables(circ, space).items()}


# ---- e-graphs --------------------------------------------------------


def _node_table(eg, node, tables, space):
    """Table of one e-node, or None if a child's table is not known yet."""
    op = node[0]
    if op == "var":
        return space.var(node[1])
    if op == "const":
        return space.const(node[1])
    a, b = node[1]
    ta = tables.get(eg.find(a))
    tb = tables.get(eg.find(b))
    if ta is None or tb is None:
        return None
    if op == "xor":
        return ta ^ tb
    if op == "and":
        return ta & tb
    raise ValueError(op)


def class_tables(eg, space, check=True):
    """{canonical class: truth table} for every class reachable from the leaves.

    A class whose every node depends (transitively) on a cycle with no leaf
    gets no entry. With `check=True`, every node whose children are known is
    compared against its class's table; a mismatch raises
    `InconsistentClassError` (an unsound merge).
    """
    eg.rebuild()
    classes = [eg.find(c) for c in eg._nodes]
    tables = {}
    changed = True
    while changed:
        changed = False
        for c in classes:
            if c in tables:
                continue
            for node in eg._nodes[c]:
                t = _node_table(eg, node, tables, space)
                if t is not None:
                    tables[c] = t
                    changed = True
                    break
    if check:
        for c in classes:
            for node in eg._nodes[c]:
                t = _node_table(eg, node, tables, space)
                if t is not None and t != tables[c]:
                    raise InconsistentClassError(
                        f"class {c}: node {node!r} computes a different function"
                    )
    return tables


def class_safety_bitsliced(eg, secrets, randoms, check=True, max_bits=None):
    """Drop-in for `constrained.class_safety`: {class: bool}.

    Classes with no computable table are labelled unsafe, as `class_safety`
    labels classes it cannot materialise.
    """
    free = [shares[0] for shares in secrets.values()] + list(randoms)
    space = TruthSpace(secrets, free, max_bits or DEFAULT_MAX_BITS)
    tables = class_tables(eg, space, check=check)
    return {
        eg.find(c): (eg.find(c) in tables and space.is_safe(tables[eg.find(c)]))
        for c in eg._nodes
    }
