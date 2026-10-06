"""egglog port: re-confirm the premise on a real engine, and measure the
two-gadget chain that explodes the in-house harness.

Two questions from the design records:

  * design/0004 — the premise (unconstrained equality saturation yields a
    cheaper but probing-insecure circuit) must be re-confirmed on a real engine,
    not only on the minimal in-house e-graph.
  * design/0009 — is the chain blowup (3,000 classes in 2 iterations in the
    in-house harness) an artifact of an unoptimised engine, or a property of
    the rule set?  This decides whether the project's scalable path is
    engineering or research.

Usage:
    uv run python experiments/egglog_port/port.py --circuit isw
    uv run python experiments/egglog_port/port.py --circuit chain --iters 4
    uv run python experiments/egglog_port/port.py --circuit chain --rules core --iters 6
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from egglog import EGraph, Expr, StringLike, rewrite

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "premise_test"))

from masked import Circuit, check_first_order, unsafe_wires  # noqa: E402

SECRETS_AB = {"a": ["a0", "a1"], "b": ["b0", "b1"]}
SECRETS_CHAIN = {"a": ["a0", "a1"], "b": ["b0", "b1"], "d": ["d0", "d1"]}
FREE_CHAIN = ["a0", "b0", "d0", "r1", "r2"]


class B(Expr):
    @classmethod
    def var(cls, name: StringLike) -> B: ...
    @classmethod
    def zero(cls) -> B: ...
    def __xor__(self, other: B) -> B: ...
    def __and__(self, other: B) -> B: ...


def make_egraph(rules: str) -> EGraph:
    eg = EGraph()

    @eg.register
    def _rules(a: B, b: B, c: B):  # noqa: ANN202 - egglog rule generator
        yield rewrite(a ^ b).to(b ^ a)
        yield rewrite((a ^ b) ^ c).to(a ^ (b ^ c))
        yield rewrite(a ^ a).to(B.zero())
        yield rewrite(a ^ B.zero()).to(a)
        yield rewrite(a & b).to(b & a)
        if rules == "full":
            # distributivity and its reverse: the share-refolding rules
            yield rewrite(a & (b ^ c)).to((a & b) ^ (a & c))
            yield rewrite((a & b) ^ (a & c)).to(a & (b ^ c))

    return eg


def isw_and(x0, x1, y0, y1, r):
    """2-share ISW masked AND, with the fresh random folded in early."""
    c0 = (x0 & y0) ^ r
    c1 = ((r ^ (x0 & y1)) ^ (x1 & y0)) ^ (x1 & y1)
    return c0, c1


# ---- turning an extracted egglog term back into a circuit -------------


class Node:
    """Tiny expression tree used to evaluate egglog's printed extraction."""

    def __init__(self, op, args):
        self.op, self.args = op, args

    def __and__(self, other):
        return Node("and", (self, other))

    def __xor__(self, other):
        return Node("xor", (self, other))


class _Var:
    @staticmethod
    def var(name):
        return Node("var", (name,))

    @staticmethod
    def zero():
        return Node("const", (0,))


def parse_extracted(text):
    """Turn egglog's printed extraction into a Node tree.

    Large terms are printed with shared subterms hoisted into ``_B_n = <expr>``
    bindings followed by a final result expression, and statements can span
    several lines, so statements are split with ``ast`` rather than by newline.
    The printed form uses Python's ``&`` / ``^`` with Python precedence, so a
    closed-namespace eval is faithful.  Sharing is preserved because a binding is
    a single Node object reused by reference, and our Circuit hash-conses gates
    structurally, so gate counts are DAG counts.
    """
    import ast

    tree = ast.parse(text)
    ns = {"B": _Var}
    for stmt in tree.body[:-1]:
        code = compile(ast.Module(body=[stmt], type_ignores=[]), "<extract>", "exec")
        exec(code, {"__builtins__": {}}, ns)  # noqa: S102 - engine output
    last = tree.body[-1]
    if not isinstance(last, ast.Expr):
        raise ValueError(f"unexpected trailing statement in extraction: {last!r}")
    code = compile(ast.Expression(body=last.value), "<extract>", "eval")
    return eval(code, {"__builtins__": {}}, ns)  # noqa: S307


def node_to_wire(node, circ):
    if node.op == "var":
        return circ.add_input(node.args[0])
    if node.op == "const":
        return circ.add_const(node.args[0])
    a = node_to_wire(node.args[0], circ)
    b = node_to_wire(node.args[1], circ)
    return circ.add_gate(node.op, a, b)


def report(label, circ, secrets, free):
    bad = unsafe_wires(check_first_order(circ, secrets, free))
    state = "SECURE" if not bad else f"INSECURE ({len(bad)} wire(s))"
    print(
        f"  {label}: {circ.gate_count()} gates "
        f"({circ.and_count()} AND + {circ.xor_count()} XOR), {state}"
    )
    for w in bad[:3]:
        print(f"      leaking: {w}")
    return not bad


def run_isw(rules: str, iters: int):
    eg = make_egraph(rules)
    a0, a1 = B.var("a0"), B.var("a1")
    b0, b1 = B.var("b0"), B.var("b1")
    r = B.var("r")
    c0, c1 = isw_and(a0, a1, b0, b1, r)
    e0, e1 = eg.let("c0", c0), eg.let("c1", c1)
    t = time.time()
    eg.run(iters)
    print(f"egglog run({iters}) [{rules} rules] in {time.time() - t:.2f}s")
    texts = [str(eg.extract(e0)), str(eg.extract(e1))]
    print(f"  extracted c0 = {texts[0]}")
    print(f"  extracted c1 = {texts[1]}")
    circ = Circuit()
    for text in texts:
        circ.outputs.append(node_to_wire(parse_extracted(text), circ))
    report("egglog unconstrained extraction (ISW)", circ, SECRETS_AB, ["a0", "b0", "r"])


def run_chain(rules: str, iters: int):
    eg = make_egraph(rules)
    a0, a1 = B.var("a0"), B.var("a1")
    b0, b1 = B.var("b0"), B.var("b1")
    d0, d1 = B.var("d0"), B.var("d1")
    r1, r2 = B.var("r1"), B.var("r2")
    t0, t1 = isw_and(a0, a1, b0, b1, r1)
    u0, u1 = isw_and(t0, t1, d0, d1, r2)
    e0, e1 = eg.let("u0", u0), eg.let("u1", u1)
    for n in range(1, iters + 1):
        t = time.time()
        eg.run(1)
        print(f"  iteration {n}: {time.time() - t:.2f}s")
    print(f"  function sizes: {eg.all_function_sizes()}")
    texts = [str(eg.extract(e0)), str(eg.extract(e1))]
    circ = Circuit()
    for text in texts:
        circ.outputs.append(node_to_wire(parse_extracted(text), circ))
    report("egglog unconstrained extraction (chain)", circ, SECRETS_CHAIN, FREE_CHAIN)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circuit", choices=("isw", "chain"), default="isw")
    ap.add_argument("--rules", choices=("core", "full"), default="full")
    ap.add_argument("--iters", type=int, default=4)
    args = ap.parse_args()
    if args.circuit == "isw":
        run_isw(args.rules, args.iters)
    else:
        run_chain(args.rules, args.iters)


if __name__ == "__main__":
    main()
