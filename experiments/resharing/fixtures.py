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
