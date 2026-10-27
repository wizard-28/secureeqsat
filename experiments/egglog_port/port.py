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

Purpose
-------
The in-house e-graph (`experiments/premise_test/egraph.py`) is a small test
harness. This file reruns the same experiment on egglog 14, a real e-graph
engine, to show that the leak is not an artifact of our own code. It also times
the two-gadget chain, which blows up the in-house harness but is easy for egglog.

How it works: the ISW gadget is written as an egglog expression, egglog saturates
it with the same kind of rewrite rules, egglog's own `extract` picks the cheapest
term, and that term is parsed back into a `Circuit` and checked with the in-house
checker (`masked.check_first_order`). Nothing here constrains extraction by
security: it demonstrates the problem. The repair lives in
`experiments/constrained_extraction` and `experiments/resharing`.

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

# Which inputs are shares of which secret (shares[0] is the free uniform share), and
# which bits are free (the first share of each secret plus every fresh random).
SECRETS_AB = {"a": ["a0", "a1"], "b": ["b0", "b1"]}
SECRETS_CHAIN = {"a": ["a0", "a1"], "b": ["b0", "b1"], "d": ["d0", "d1"]}
FREE_CHAIN = ["a0", "b0", "d0", "r1", "r2"]


class B(Expr):
    """The egglog expression type for Boolean terms.

    The method bodies are `...` because egglog only needs their signatures: it
    treats them as uninterpreted constructors that the rewrite rules reason about.
    Python operators build terms, so `a ^ b` is XOR and `a & b` is AND.
    """

    @classmethod
    def var(cls, name: StringLike) -> B: ...
    @classmethod
    def zero(cls) -> B: ...
    def __xor__(self, other: B) -> B: ...
    def __and__(self, other: B) -> B: ...


def make_egraph(rules: str) -> EGraph:
    """Create an egglog e-graph holding the Boolean rewrite rules.

    Args:
        rules: "core" or "full".

    "core" registers XOR commutativity and associativity, `a ^ a = 0`,
    `a ^ 0 = a` and AND commutativity. "full" adds distributivity and its reverse
    (factoring), the share-refolding rules that cause the leak. These are fewer
    rules than the in-house e-graph's (no idempotence or annihilator), and the
    leak appears all the same.
    """
    eg = EGraph()

    @eg.register
    def _rules(a: B, b: B, c: B):  # noqa: ANN202 - egglog rule generator
        # a, b, c are pattern VARIABLES: each rule fires for any terms in their place.
        # `rewrite(lhs).to(rhs)` says "wherever lhs appears, rhs is equal to it".
        yield rewrite(a ^ b).to(b ^ a)  # XOR commutativity
        yield rewrite((a ^ b) ^ c).to(a ^ (b ^ c))  # XOR associativity
        yield rewrite(a ^ a).to(B.zero())  # x ^ x = 0
        yield rewrite(a ^ B.zero()).to(a)  # x ^ 0 = x
        yield rewrite(a & b).to(b & a)  # AND commutativity
        if rules == "full":
            # distributivity and its reverse: the share-refolding rules
            yield rewrite(a & (b ^ c)).to((a & b) ^ (a & c))
            yield rewrite((a & b) ^ (a & c)).to(a & (b ^ c))

    return eg


def isw_and(x0, x1, y0, y1, r):
    """2-share ISW masked AND, with the fresh random folded in early.

    Takes shares (x0, x1) and (y0, y1) and one random `r` (all `B` terms, or
    `Node` terms) and returns the two output shares `(c0, c1)`:
        c0 = x0&y0 ^ r
        c1 = ((r ^ x0&y1) ^ x1&y0) ^ x1&y1
    The XOR order matters: r must enter before the cross terms are combined.
    """
    c0 = (x0 & y0) ^ r  # output share 0: one product masked by r
    # output share 1: r enters FIRST, so each partial sum is masked by r
    c1 = ((r ^ (x0 & y1)) ^ (x1 & y0)) ^ (x1 & y1)
    return c0, c1


# ---- turning an extracted egglog term back into a circuit -------------


class Node:
    """Tiny expression tree used to evaluate egglog's printed extraction.

    Supports `&` and `^` like `B`, so evaluating egglog's printed Python-style
    expression in a sandbox builds a `Node` tree instead of an egglog term.
    """

    def __init__(self, op, args):
        """Store the operator ("var", "const", "and" or "xor") and its operands."""
        # op e.g. "xor"; args e.g. (Node, Node) for a gate or ("a0",) for a variable
        self.op, self.args = op, args

    def __and__(self, other):
        """Build an AND node."""
        return Node("and", (self, other))

    def __xor__(self, other):
        """Build an XOR node."""
        return Node("xor", (self, other))


class _Var:
    """Stand-in for `B` when evaluating egglog's printed terms (builds `Node`s)."""

    @staticmethod
    def var(name):
        """A variable leaf."""
        return Node("var", (name,))

    @staticmethod
    def zero():
        """The constant 0 leaf."""
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

    Algorithm, step by step:
      1. Parse the text into Python statements with `ast`.
      2. Execute each statement except the last (the `_B_n = ...` bindings) in a
         restricted namespace where `B` means `_Var`, so every `B.var(...)`,
         `&` and `^` builds a `Node` and each binding becomes a named `Node`.
      3. Evaluate the last statement, the final expression, in the same namespace.
         It reuses the bound `Node`s by reference, so shared subterms stay shared.
      4. Return that `Node` tree.
    """
    import ast

    tree = ast.parse(text)  # list of statements in `tree.body`
    # The names the printed text may use. `B` is rebound to `_Var`, so
    # `B.var("a0")` builds a Node. Later `_B_n = ...` bindings are added here too.
    ns = {"B": _Var}
    # Run every binding statement (`_B_n = ...`) in a restricted namespace.
    for stmt in tree.body[:-1]:
        # wrap one statement as a tiny module so it can be compiled on its own
        code = compile(ast.Module(body=[stmt], type_ignores=[]), "<extract>", "exec")
        # empty `__builtins__` removes access to open(), import, etc.: only `ns` works
        exec(code, {"__builtins__": {}}, ns)  # noqa: S102 - engine output
    # The last statement is the final result expression.
    last = tree.body[-1]
    if not isinstance(last, ast.Expr):
        raise ValueError(f"unexpected trailing statement in extraction: {last!r}")
    code = compile(ast.Expression(body=last.value), "<extract>", "eval")
    return eval(code, {"__builtins__": {}}, ns)  # noqa: S307


def node_to_wire(node, circ):
    """Add the `Node` tree to `circ` as wires and return the root wire's name.

    The circuit shares identical gates, so repeated subtrees become one wire.
    """
    if node.op == "var":
        return circ.add_input(node.args[0])  # args[0] is the variable's name
    if node.op == "const":
        return circ.add_const(node.args[0])  # args[0] is 0 or 1
    # a gate: first build its two operand subtrees (recursion), then the gate itself
    a = node_to_wire(node.args[0], circ)  # wire name of the left operand
    b = node_to_wire(node.args[1], circ)  # wire name of the right operand
    return circ.add_gate(node.op, a, b)


def report(label, circ, secrets, free):
    """Print a circuit's gate count and security verdict; return True if secure.

    Shows up to three leaking wires so a reader can see what leaked.
    """
    bad = unsafe_wires(check_first_order(circ, secrets, free))  # leaking wire names
    state = "SECURE" if not bad else f"INSECURE ({len(bad)} wire(s))"
    print(
        f"  {label}: {circ.gate_count()} gates "
        f"({circ.and_count()} AND + {circ.xor_count()} XOR), {state}"
    )
    for w in bad[:3]:
        print(f"      leaking: {w}")
    return not bad


def run_isw(rules: str, iters: int):
    """Saturate one ISW gadget in egglog, extract the cheapest, and report it.

    Algorithm, step by step:
      1. Build an egglog e-graph with the chosen rules.
      2. Build the ISW gadget as an expression and register its two outputs.
      3. Run the rewrite rules for `iters` iterations (saturation).
      4. Ask egglog for the cheapest term of each output (cost-only extraction).
      5. Parse each printed term back into a tree and add it to a `Circuit`.
      6. Report the gate count and whether the circuit leaks.
    """
    eg = make_egraph(rules)  # an egglog e-graph with the chosen rewrite rules
    a0, a1 = (
        B.var("a0"),
        B.var("a1"),
    )  # shares of a, as egglog terms (not circuit wires)
    b0, b1 = B.var("b0"), B.var("b1")  # shares of b
    r = B.var("r")  # the gadget's fresh random bit
    c0, c1 = isw_and(a0, a1, b0, b1, r)  # the two output shares, as terms
    # `eg.let(name, term)` adds the term to the e-graph and returns a handle to it
    e0, e1 = eg.let("c0", c0), eg.let("c1", c1)
    t = time.time()  # start time, for timing saturation
    eg.run(iters)  # apply the rewrite rules `iters` times
    print(f"egglog run({iters}) [{rules} rules] in {time.time() - t:.2f}s")
    # egglog's own (cost-only) extraction, printed as text, then parsed back.
    texts = [str(eg.extract(e0)), str(eg.extract(e1))]  # one printed term per output
    print(f"  extracted c0 = {texts[0]}")
    print(f"  extracted c1 = {texts[1]}")
    circ = Circuit()
    for text in texts:
        circ.outputs.append(node_to_wire(parse_extracted(text), circ))
    report("egglog unconstrained extraction (ISW)", circ, SECRETS_AB, ["a0", "b0", "r"])


def run_chain(rules: str, iters: int):
    """Same as `run_isw`, but for a chain of two ISW gadgets (a AND b) AND d.

    Runs saturation one iteration at a time so each iteration's time is visible,
    which is how the chain blowup was measured against the in-house harness.
    """
    eg = make_egraph(rules)
    a0, a1 = B.var("a0"), B.var("a1")  # shares of secret a
    b0, b1 = B.var("b0"), B.var("b1")  # shares of secret b
    d0, d1 = B.var("d0"), B.var("d1")  # shares of secret d
    r1, r2 = B.var("r1"), B.var("r2")  # one fresh random per gadget
    t0, t1 = isw_and(a0, a1, b0, b1, r1)  # shares of (a AND b)
    u0, u1 = isw_and(t0, t1, d0, d1, r2)  # shares of ((a AND b) AND d)
    e0, e1 = eg.let("u0", u0), eg.let("u1", u1)  # handles to the two outputs
    for n in range(1, iters + 1):  # n = iteration number, 1-based
        t = time.time()  # per-iteration timer
        eg.run(1)  # exactly one saturation round
        print(f"  iteration {n}: {time.time() - t:.2f}s")
    print(f"  function sizes: {eg.all_function_sizes()}")
    texts = [str(eg.extract(e0)), str(eg.extract(e1))]
    circ = Circuit()
    for text in texts:
        circ.outputs.append(node_to_wire(parse_extracted(text), circ))
    report("egglog unconstrained extraction (chain)", circ, SECRETS_CHAIN, FREE_CHAIN)


def main():
    """Command-line entry: choose the circuit (isw or chain), rules and iterations."""
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
