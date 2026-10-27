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

Purpose
-------
This is the FAST version of the security checker (finding F5, ADR 0015). The
reference checker `masked.check_first_order` evaluates the circuit once per input
combination in a Python loop. This module does the same job much faster by using
Python's arbitrary-size integers as bit arrays: bit i of a wire's integer is that
wire's value for input combination number i. One `&` or `^` between two such
integers then computes a gate for ALL combinations at once.

A worked example (one secret `b`, free variables a0 and b0, so 2 secret blocks of
4 bits each, 8 bits in total; written lowest bit first):
    a0     = 0 1 0 1 | 0 1 0 1     (free variable 0 toggles every 1 bit)
    b0     = 0 0 1 1 | 0 0 1 1     (free variable 1 toggles every 2 bits)
    b      = 0 0 0 0 | 1 1 1 1     (the secret toggles every block)
    b1     = b0 ^ b = 0 0 1 1 | 1 1 0 0           (one bitwise XOR)
    v=a0&b1          = 0 0 0 1 | 0 1 0 0           (one bitwise AND)
Each block of `v` has exactly one 1, so `v` is safe. The same arithmetic is what
the "bitsliced check by hand" slide in the explainer video walks through (the slide
lists the four cases in a different order, which does not change the counts).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "premise_test"))

DEFAULT_MAX_BITS = 26  # 2**26 bits = 8 MiB per table


class InconsistentClassError(Exception):
    """Two nodes in one e-class compute different Boolean functions."""


def _replicate(pattern, width, total):
    """Tile a `width`-bit pattern until it covers `total` bits (both powers of 2).

    Algorithm: while the pattern is shorter than `total`, OR a copy of itself
    shifted left by its own width. Each step doubles the covered width, so it takes
    log2(total / width) steps. Example: pattern 0b01, width 2, total 8:
    0b01 -> 0b0101 -> 0b01010101.
    """
    while width < total:
        # `pattern << width` moves the copy past the existing bits; `|=` merges it
        pattern |= pattern << width
        width *= 2  # the pattern now covers twice as many bits
    return pattern


def _half_pattern(h, total):
    """`total`-bit table that is 0 for h bits, then 1 for h bits, repeating.

    This is the truth table of the input variable that sits at index bit
    log2(h): the variable is 0 for the first h inputs, 1 for the next h, and so on.
    Example: h=2, total=8 gives bits (lowest first) 0 0 1 1 0 0 1 1.

    Algorithm: `((1 << h) - 1)` is h ones; shifting it left by h puts them in the
    upper half of a 2h-bit unit (so the lower h bits are 0); `_replicate` tiles that
    unit across the whole table.
    """
    return _replicate(((1 << h) - 1) << h, 2 * h, total)


class TruthSpace:
    """The (secret, free-variable) assignment space and its input truth tables.

    secret_groups: {secret: [share_names]}; shares[0] is the free uniform share,
                   every further share is reconstructed as shares[0] ^ secret
                   (exactly as in `check_first_order`).
    free_vars:     all uniform free inputs: shares[0] of every secret plus every
                   fresh random.

    Layout of the index of a bit: the low `len(free_vars)` bits of the index select
    the free-variable assignment, the high `len(secrets)` bits select the secret
    assignment. So each secret assignment owns one contiguous BLOCK of
    `2**len(free_vars)` bits.
    """

    def __init__(self, secret_groups, free_vars, max_bits=DEFAULT_MAX_BITS):
        """Build the input tables, refusing spaces that are too large or malformed.

        Raises ValueError if the space exceeds `2**max_bits` points, if `free_vars`
        has duplicates, if a secret's first share is not a free variable, or if a
        later share is (wrongly) also listed as free.
        """
        self.secrets = list(secret_groups)  # secret names, e.g. ["a", "b"]
        self.free_vars = list(free_vars)  # free input names, e.g. ["a0", "b0", "r"]
        nbits = len(self.secrets) + len(self.free_vars)  # index width, e.g. 5
        if nbits > max_bits:
            raise ValueError(
                f"assignment space has 2**{nbits} points (> 2**{max_bits}); "
                "the bitsliced labeller would need too much memory"
            )
        if len(set(self.free_vars)) != len(self.free_vars):
            raise ValueError("free_vars contains duplicates")

        self.block = 1 << len(self.free_vars)  # bits per secret assignment, e.g. 8
        self.nblocks = 1 << len(self.secrets)  # number of secret assignments, e.g. 4
        self.size = self.block * self.nblocks  # total bits in a table, e.g. 32
        self.full = (1 << self.size) - 1  # all ones: the truth table of constant 1
        self._block_mask = (1 << self.block) - 1  # `block` ones, to cut out one block

        # Truth table of every free variable: variable j toggles every 2**j bits.
        tables = {
            v: _half_pattern(1 << j, self.size) for j, v in enumerate(self.free_vars)
        }
        # Truth table of every secret: secret k toggles every block << k bits, i.e.
        # it is constant within a block and flips from one block to the next.
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
                # share k = share 0 XOR secret: one bitwise XOR of two whole tables
                tables[x] = tables[shares[0]] ^ secret_tt[s]
        self._inputs = tables  # input name -> truth table (a Python int)

    def var(self, name):
        """Truth table of the input `name` (a free variable or a derived share)."""
        try:
            return self._inputs[name]
        except KeyError:
            raise ValueError(
                f"input {name!r} is neither a free variable nor a share"
            ) from None

    def const(self, value):
        """Truth table of a constant: all ones for a truthy `value`, else all zeros."""
        return self.full if value else 0

    def is_safe(self, table):
        """True iff the table's count of 1s is identical in every secret block.

        Algorithm, step by step:
          1. Cut out block 0 (secrets all 0): `table & mask` keeps the low `block`
             bits, and `.bit_count()` counts the 1s. That is the baseline.
          2. For every other block k, shift the table right by `k * block` so block k
             sits at the bottom, mask it, and count its 1s.
          3. The wire is safe iff every block has the same count as the baseline.
        """
        mask = self._block_mask
        base = (table & mask).bit_count()  # 1s in block 0
        return all(
            # `>> (k * block)` brings block k down to the lowest bits
            ((table >> (k * self.block)) & mask).bit_count() == base
            for k in range(1, self.nblocks)
        )


# ---- circuits --------------------------------------------------------


def circuit_tables(circ, space):
    """{wire_name: truth table} for a `masked.Circuit`.

    Algorithm: walk the wires in creation order. An input takes its table from
    `space`, a constant becomes all-ones or all-zeros, and an XOR or AND is one
    bitwise `^` or `&` of the two operand tables (which already exist because
    operands are created first).
    """
    tables = {}  # wire name -> integer truth table
    for name, op, payload in circ.wires:
        if op == "input":
            tables[name] = space.var(name)
        elif op == "const":
            tables[name] = space.const(payload)
        elif op == "xor":
            # one XOR computes the gate for every input combination at once
            tables[name] = tables[payload[0]] ^ tables[payload[1]]
        elif op == "and":
            tables[name] = tables[payload[0]] & tables[payload[1]]
        else:
            raise ValueError(op)
    return tables


def check_first_order_bitsliced(
    circ, secret_groups, free_vars, max_bits=DEFAULT_MAX_BITS
):
    """Drop-in for `masked.check_first_order`: returns {wire_name: bool_safe}.

    Builds the truth space, computes every wire's table, and applies `is_safe` to
    each. The verdicts are identical to the reference checker's; only the speed
    differs (this is cross-validated against it and against VerifMSI).
    """
    space = TruthSpace(secret_groups, free_vars, max_bits)
    return {w: space.is_safe(t) for w, t in circuit_tables(circ, space).items()}


# ---- e-graphs --------------------------------------------------------


def _node_table(eg, node, tables, space):
    """Table of one e-node, or None if a child's table is not known yet.

    A leaf takes its table from `space`; a gate combines its two child classes'
    tables with one bitwise operation. If either child class has no table yet,
    the answer is None (the caller will try again after more tables are known).
    """
    op = node[0]
    if op == "var":
        return space.var(node[1])
    if op == "const":
        return space.const(node[1])
    a, b = node[1]  # the two child classes
    ta = tables.get(eg.find(a))  # child tables, None if not computed yet
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

    Algorithm, step by step:
      1. Repeatedly sweep all classes. For a class without a table, try each node;
         the first node whose children all have tables fixes the class's table.
      2. Stop when a sweep adds no new table (a fixed point), so every class
         reachable from the leaves has a table.
      3. If `check` is True, recompute the table of EVERY node and compare it with
         its class's table. Equal functions in one class is the e-graph's promise,
         so a difference means a rewrite rule merged two different functions.
    """
    eg.rebuild()
    classes = [eg.find(c) for c in eg._nodes]  # canonical class ids
    tables = {}  # class -> integer truth table
    changed = True
    while changed:  # fixed-point loop: sweep until nothing new appears
        changed = False
        for c in classes:
            if c in tables:
                continue  # already has a table
            for node in eg._nodes[c]:
                t = _node_table(eg, node, tables, space)
                if t is not None:
                    tables[c] = t
                    changed = True
                    break  # one node is enough: all nodes in a class are equal
    if check:
        for c in classes:
            for node in eg._nodes[c]:
                t = _node_table(eg, node, tables, space)
                # a node whose table differs from the class table is an unsound merge
                if t is not None and t != tables[c]:
                    raise InconsistentClassError(
                        f"class {c}: node {node!r} computes a different function"
                    )
    return tables


def class_safety_bitsliced(eg, secrets, randoms, check=True, max_bits=None):
    """Drop-in for `constrained.class_safety`: {class: bool}.

    Classes with no computable table are labelled unsafe, as `class_safety`
    labels classes it cannot materialise.

    Algorithm: the free variables are the first share of each secret plus the
    randoms; build the truth space; compute one table per class with
    `class_tables`; label each class by `is_safe` of its table (or unsafe if it has
    no table).
    """
    # first share of each secret (the free one) plus the fresh randoms
    free = [shares[0] for shares in secrets.values()] + list(randoms)
    space = TruthSpace(secrets, free, max_bits or DEFAULT_MAX_BITS)
    tables = class_tables(eg, space, check=check)
    return {
        eg.find(c): (eg.find(c) in tables and space.is_safe(tables[eg.find(c)]))
        for c in eg._nodes
    }
