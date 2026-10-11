"""Fixtures for the shared-value layer: shared-value terms (see gadgets.py)."""

A, B, D = ("in", "a"), ("in", "b"), ("in", "d")
Z = ("xor", A, B)

FIXTURES = {
    # control: the hand-written two-gadget chain of the feasibility report
    "chain": ("isw", ("isw", A, B), D),
    # the same chain as a conservative compiler would emit: refresh every input
    "overrefreshed": (
        "isw",
        ("refresh", ("isw", ("refresh", A), ("refresh", B))),
        ("refresh", D),
    ),
    # a product of a value with itself: the refresh is necessary
    "square": ("isw", Z, ("refresh", Z)),
    # a&b ^ a&d: factoring at the value layer
    "factor": ("xor", ("isw", A, B), ("isw", A, D)),
    # the chain written with HPC1 gadgets
    "hpc_chain": ("hpc1", ("hpc1", A, B), D),
}


def chi(n, gadget="isw"):
    """Keccak's chi on an n-bit row, one AND gadget per output bit.

    FIPS 202, sec. 3.2.4: A'[x] = A[x] ^ ((A[x+1] ^ 1) & A[x+2]), indices mod n.
    The masked form is the direct one: share-wise NOT, one AND gadget per bit,
    share-wise XOR. All n outputs are bundled into one root with `out`.
    """
    xs = [("in", f"x{i}") for i in range(n)]
    ys = [
        ("xor", xs[i], (gadget, ("not", xs[(i + 1) % n]), xs[(i + 2) % n]))
        for i in range(n)
    ]
    root = ys[-1]
    for y in reversed(ys[:-1]):
        root = ("out", y, root)
    return root


# Tight starting points: no redundant refresh, the cheapest gadget, and the
# AND count of the specification's own formula.
TIGHT = {"chi3": chi(3), "chi5": chi(5)}
