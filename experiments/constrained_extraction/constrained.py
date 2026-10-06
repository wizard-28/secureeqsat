"""First-order security-constrained extraction (prototype of design/0006).

Standard e-graph extraction minimises cost and is indifferent to security; the
premise test shows it selects a cheaper insecure circuit. This module adds the
constraint:

  * `class_safety`  labels every e-class by whether the Boolean FUNCTION it
    represents is independent of the secrets (first order, glitch-free).
  * `extract_constrained` runs the cost fixed point restricted to nodes whose
    children are internally materialisable, where a class may be materialised
    internally only if it is safe.
  * `materialize_constrained` instantiates the result, exempting the roots
    (outputs) from the safety requirement, as probing security constrains
    internal wires.

Nothing here is novel yet; it is the feasibility prototype for ADR 0006.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "premise_test"))

from egraph import MaterializeError, extract, materialize  # noqa: E402
from masked import Circuit, check_first_order  # noqa: E402

INF = float("inf")
DEFAULT_WEIGHTS = {"and": 2, "xor": 1}


def free_vars_for(secrets, randoms):
    return [shares[0] for shares in secrets.values()] + list(randoms)


def class_safety(eg, secrets, randoms):
    """{class: bool} — is the function computed by this class independent of secrets?

    Safety is a property of the function, so any representative term suffices;
    we materialise the cheapest one and ask the checker about the root wire.
    """
    free = free_vars_for(secrets, randoms)
    eg.rebuild()
    representatives, _ = extract(eg)  # unconstrained, only used to materialise
    safety = {}
    for c in list(eg._nodes):
        c = eg.find(c)
        if c in safety:
            continue
        circ = Circuit()
        try:
            materialize(eg, representatives, [c], circ)
        except (MaterializeError, KeyError):
            safety[c] = False  # cannot materialise -> treat as unsafe
            continue
        verdict = check_first_order(circ, secrets, free)
        safety[c] = bool(verdict[circ.outputs[0]])
    return safety


def extract_constrained(eg, safety, weights=None, max_iters=500):
    """Cost fixed point where only safe classes may be materialised internally.

    Returns (best_internal, cost_internal).  Classes that are unsafe, or that
    depend on an unsafe class, get no entry (infinite cost).
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS
    eg.rebuild()
    cost = {}
    best = {}
    for _ in range(max_iters):
        changed = False
        for c in list(eg._nodes):
            c = eg.find(c)
            if not safety.get(c, False):
                continue  # may not appear as an internal wire
            for node in eg._nodes[c]:
                if node[0] in ("var", "const"):
                    nc = 0
                else:
                    a, b = node[1]
                    ca = cost.get(eg.find(a), INF)
                    cb = cost.get(eg.find(b), INF)
                    if ca == INF or cb == INF:
                        continue
                    nc = weights[node[0]] + ca + cb
                if nc < cost.get(c, INF):
                    cost[c] = nc
                    best[c] = node
                    changed = True
        if not changed:
            break
    return best, cost


def root_choices(eg, cost, roots, weights=None):
    """For each root, the cheapest node all of whose children can be built safely.

    The root itself is exempt from the safety requirement: outputs are allowed
    to depend on secrets.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS
    out = {}
    for r in roots:
        r = eg.find(r)
        node_best, cost_best = None, INF
        for node in eg._nodes[r]:
            if node[0] in ("var", "const"):
                nc = 0
            else:
                a, b = node[1]
                ca = cost.get(eg.find(a), INF)
                cb = cost.get(eg.find(b), INF)
                if ca == INF or cb == INF:
                    continue
                nc = weights[node[0]] + ca + cb
            if nc < cost_best:
                cost_best, node_best = nc, node
        out[r] = (node_best, cost_best)
    return out


def materialize_constrained(eg, best_internal, choices, roots, circuit):
    """Instantiate a constrained extraction; internal wires use safe nodes."""
    wire_of = {}
    visiting = set()

    def build_internal(c):
        c = eg.find(c)
        if c in wire_of:
            return wire_of[c]
        if c in visiting:
            raise MaterializeError(f"cycle while building class {c}")
        if c not in best_internal:
            raise MaterializeError(f"class {c} is not safely materialisable")
        visiting.add(c)
        w = build_node(best_internal[c])
        visiting.discard(c)
        wire_of[c] = w
        return w

    def build_node(node):
        op = node[0]
        if op == "var":
            return circuit.add_input(node[1])
        if op == "const":
            return circuit.add_const(node[1])
        a, b = node[1]
        wa = build_internal(a)
        wb = build_internal(b)
        return circuit.add_gate(op, wa, wb)

    for r in roots:
        node, cost = choices[eg.find(r)]
        if node is None:
            raise MaterializeError(f"no secure option for root class {eg.find(r)}")
        circuit.outputs.append(build_node(node))
    return circuit
