"""Fixtures for the shared-value layer: shared-value terms (see gadgets.py).

Purpose
-------
The starting circuits for the value-layer experiments, written as nested-tuple
terms. `FIXTURES` are small hand-made programs, each chosen to show one effect of a
rule class (over-refreshing, a needed refresh, factoring, HPC1 gadgets). `TIGHT`
holds Keccak chi rows, which are already close to optimal, to show that nothing
improves when there is no slack.
"""

# The secret inputs a, b, d and the value z = a ^ b, as terms.
A, B, D = ("in", "a"), ("in", "b"), ("in", "d")
Z = ("xor", A, B)  # a share-wise XOR of a and b: a masked value used twice below

FIXTURES = {
    # control: the hand-written two-gadget chain of the feasibility report
    # (a AND b) AND d with two ISW gadgets: nothing to optimise
    "chain": ("isw", ("isw", A, B), D),
    # the same chain as a conservative compiler would emit: refresh every input
    # (six refreshes in total, most of them redundant)
    "overrefreshed": (
        "isw",
        ("refresh", ("isw", ("refresh", A), ("refresh", B))),
        ("refresh", D),
    ),
    # a product of a value with itself: the refresh is necessary
    # (z & z: without a refresh both operands share one sharing and the gadget leaks)
    "square": ("isw", Z, ("refresh", Z)),
    # a&b ^ a&d: factoring at the value layer
    # (two AND gadgets that can become one: a & (b ^ d))
    "factor": ("xor", ("isw", A, B), ("isw", A, D)),
    # the chain written with HPC1 gadgets
    # (the costlier gadget; swapping it for ISW is the R2 saving)
    "hpc_chain": ("hpc1", ("hpc1", A, B), D),
}


def chi(n, gadget="isw"):
    """Keccak's chi on an n-bit row, one AND gadget per output bit.

    FIPS 202, sec. 3.2.4: A'[x] = A[x] ^ ((A[x+1] ^ 1) & A[x+2]), indices mod n.
    The masked form is the direct one: share-wise NOT, one AND gadget per bit,
    share-wise XOR. All n outputs are bundled into one root with `out`.

    Algorithm, step by step:
      1. Make one secret input x0 ... x{n-1} per bit of the row.
      2. For each bit i build the output `x[i] ^ (gadget(NOT x[i+1], x[i+2]))`.
         Indices wrap around the row, so `% n` makes bit n-1 use bits 0 and 1.
      3. Nest the n outputs into a single root: out(y0, out(y1, ... y{n-1})), built
         from the last output backwards.
    """
    xs = [("in", f"x{i}") for i in range(n)]  # the row's input bits
    ys = [
        # NOT of the next bit, ANDed with the bit after, XORed into this bit
        ("xor", xs[i], (gadget, ("not", xs[(i + 1) % n]), xs[(i + 2) % n]))
        for i in range(n)
    ]
    root = ys[-1]  # start with the last output
    for y in reversed(ys[:-1]):  # wrap each earlier output around it
        root = ("out", y, root)
    return root


# Tight starting points: no redundant refresh, the cheapest gadget, and the
# AND count of the specification's own formula.
TIGHT = {"chi3": chi(3), "chi5": chi(5)}
