"""The larger front-end programs compute what their specifications say.

Each program in `complex/` is checked against an independent reference (the Ascon and
PRESENT S-box tables from their specifications, or plain integer arithmetic) on every
input. This guards the benchmarks themselves: a table of costs means nothing if the
program is not the circuit it claims to be.
"""

import itertools
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lang import evaluate, parse  # noqa: E402

DIR = HERE / "complex"
ASCON = [
    0x4, 0xB, 0x1F, 0x14, 0x1A, 0x15, 0x9, 0x2, 0x1B, 0x5, 0x8, 0x12, 0x1D, 0x3, 0x6,
    0x1C, 0x1E, 0x13, 0x7, 0xE, 0x0, 0xD, 0x11, 0x18, 0x10, 0xC, 0x1, 0x19, 0x16,
    0xA, 0xF, 0x17,
]  # fmt: skip
PRESENT = [0xC, 5, 6, 0xB, 9, 0, 0xA, 0xD, 3, 0xE, 0xF, 8, 4, 7, 1, 2]


def run(name):
    """Yield (input env, {output: bit}) for every input assignment of the program."""
    prog = parse((DIR / name).read_text())
    for vals in itertools.product((0, 1), repeat=len(prog.inputs)):
        env = dict(zip(prog.inputs, vals, strict=True))
        yield env, {n: int(evaluate(e, env)) for n, e in prog.outputs}


def test_ascon_sbox_matches_spec_table():
    for env, out in run("ascon_sbox.sec"):
        x = sum(env[f"x{i}"] << (4 - i) for i in range(5))  # x0 is the MSB
        y = sum(out[f"y{i}"] << (4 - i) for i in range(5))
        assert y == ASCON[x], (x, y)


def test_present_sbox_matches_spec_table():
    for env, out in run("present_sbox.sec"):
        x = sum(env[f"x{i}"] << i for i in range(4))
        y = sum(out[f"y{i}"] << i for i in range(4))
        assert y == PRESENT[x], (x, y)


def test_adder_multiplier_comparator_mux_are_arithmetically_right():
    for env, out in run("add2.sec"):
        a, b = env["a0"] + 2 * env["a1"], env["b0"] + 2 * env["b1"]
        s = a + b + env["cin"]
        assert out["s0"] + 2 * out["s1"] + 4 * out["cout"] == s
    for env, out in run("mul2.sec"):
        a, b = env["a0"] + 2 * env["a1"], env["b0"] + 2 * env["b1"]
        assert sum(out[f"p{i}"] << i for i in range(4)) == a * b
    for env, out in run("cmp2.sec"):
        a, b = env["a0"] + 2 * env["a1"], env["b0"] + 2 * env["b1"]
        assert out["gt"] == int(a > b) and out["eq"] == int(a == b)
    for env, out in run("mux4.sec"):
        sel = env["s0"] + 2 * env["s1"]
        assert out["y"] == env[f"d{sel}"]
