"""First-order security-constrained extraction (prototype of design/0006).

Standard e-graph extraction minimises cost and is indifferent to security; the
premise test shows it selects a cheaper insecure circuit. This module adds the
constraint:

  * `class_safety`  labels every e-class by whether the Boolean FUNCTION it
    represents is independent of the secrets (first order, glitch-free). It
    uses the bitsliced labeller (experiments/labeller, design/0015); the
    original per-class implementation is kept as `class_safety_reference`.
  * `extract_constrained` runs the cost fixed point restricted to nodes whose
    children are internally materialisable, where a class may be materialised
    internally only if it is safe.
  * `materialize_constrained` instantiates the result, exempting the roots
    (outputs) from the safety requirement, as probing security constrains
    internal wires.

Nothing here is novel yet; it is the feasibility prototype for ADR 0006.

Purpose
-------
This is the REPAIR (finding F3). The e-graph still contains every equivalent form,
leaky ones included, and no rule is banned. What changes is the final extraction
step: a class whose function depends on a secret may never become an internal
wire, so the extractor can no longer pick the cheaper leaking circuit.

Why one label per class is enough here: at the wire level, whether a wire leaks
depends only on the Boolean function it computes, so every node in a class gets
the same verdict. (This stops being true once re-sharing rules such as refresh
are added; that case is handled in `experiments/resharing`.)

Typical use, as in `run_constrained.py`:
    safety = class_safety(eg, secrets, randoms)
    best, cost = extract_constrained(eg, safety)
    choices = root_choices(eg, cost, roots)
    materialize_constrained(eg, best, choices, roots, circuit)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "premise_test"))
sys.path.insert(0, str(ROOT / "experiments" / "labeller"))

from egraph import MaterializeError, extract, materialize  # noqa: E402
from labeller import class_safety_bitsliced  # noqa: E402
from masked import Circuit, check_first_order  # noqa: E402

INF = float("inf")  # "no safe way to build this class": larger than any real cost
DEFAULT_WEIGHTS = {"and": 2, "xor": 1}  # per-gate cost, same model as egraph.extract


def free_vars_for(secrets, randoms):
    """The free (uniform) bits: the first share of each secret plus the randoms.

    Args:
        secrets: `{secret_name: [share_names]}`.
        randoms: the fresh random input names only.
    """
    # `shares[0]` is the first share of each secret, which is the one that is free
    # (uniform); e.g. {"a": ["a0","a1"], "b": ["b0","b1"]} + ["r"] -> ["a0","b0","r"]
    return [shares[0] for shares in secrets.values()] + list(randoms)


def class_safety(eg, secrets, randoms):
    """{class: bool} — is the function computed by this class independent of secrets?

    `randoms` are the fresh randoms only; the first share of every secret is
    added automatically. Computed by the bitsliced labeller: one truth table
    per class, bottom-up, with a check that every node in a class computes the
    same function (an unsound merge raises `InconsistentClassError`).

    This is a thin wrapper so callers keep one stable name; the work is in
    `labeller.class_safety_bitsliced`. See `experiments/labeller` for how the
    truth tables are packed into integers.
    """
    return class_safety_bitsliced(eg, secrets, randoms)


def class_safety_reference(eg, secrets, randoms):
    """The original labeller, kept as the reference for `class_safety`.

    Safety is a property of the function, so any representative term suffices;
    we materialise the cheapest one and ask the checker about the root wire.
    Exponential per class: prefer `class_safety`.

    Algorithm, step by step:
      1. Compute the free bits and extract one (cheapest) representative node per
         class, ignoring security. These are only used to build a test circuit.
      2. For each class, build a small circuit whose output is that class.
         (If it cannot be built, call the class unsafe.)
      3. Run the full in-house checker on that circuit and read the verdict for
         its output wire. That verdict is the class's label.
    It is slow because the checker enumerates every assignment for every class.
    Kept so tests can confirm the fast labeller gives identical labels.
    """
    free = free_vars_for(secrets, randoms)  # the free bits, e.g. ["a0", "b0", "r"]
    eg.rebuild()
    representatives, _ = extract(eg)  # unconstrained, only used to materialise
    safety = {}  # class id -> True if its function is independent of the secrets
    for c in list(eg._nodes):
        c = eg.find(c)
        if c in safety:  # already labelled (two ids can point at one class)
            continue
        circ = Circuit()  # a throwaway circuit whose output is this class
        try:
            materialize(eg, representatives, [c], circ)
        except (MaterializeError, KeyError):
            safety[c] = False  # cannot materialise -> treat as unsafe
            continue
        verdict = check_first_order(circ, secrets, free)  # {wire name: safe?}
        # the verdict for the circuit's single OUTPUT wire is the class's label
        safety[c] = bool(verdict[circ.outputs[0]])
    return safety


def extract_constrained(eg, safety, weights=None, max_iters=500):
    """Cost fixed point where only safe classes may be materialised internally.

    Returns (best_internal, cost_internal).  Classes that are unsafe, or that
    depend on an unsafe class, get no entry (infinite cost).

    Algorithm, step by step (the same fixed point as `egraph.extract`, with one
    extra rule):
      1. Start with no cost known for any class.
      2. Repeat: for every class, SKIP it if the labeller marked it unsafe, since
         an unsafe class may not appear as an internal wire.
      3. For a safe class, cost each of its nodes: leaves cost 0; an AND or XOR
         costs its weight plus the cost of both child classes, but only if both
         children already have a (finite) cost. A child that is unsafe, or that
         depends on an unsafe class, never gets a cost, so such nodes are never
         chosen.
      4. Keep the cheapest node per class. Stop when a full pass improves nothing.
    The roots (outputs) are NOT handled here; see `root_choices`.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS
    eg.rebuild()
    cost = {}  # safe class -> cheapest cost so far, e.g. {3: 0, 7: 2}
    best = {}  # safe class -> node achieving it, e.g. {7: ("and", (3, 4))}
    for _ in range(max_iters):
        changed = False  # did any class improve in this pass?
        for c in list(eg._nodes):
            c = eg.find(c)
            # `.get(c, False)`: a class with no label counts as unsafe
            if not safety.get(c, False):
                continue  # may not appear as an internal wire
            for node in eg._nodes[c]:
                if node[0] in ("var", "const"):
                    nc = 0  # nc = this node's total cost; leaves are free
                else:
                    a, b = node[1]  # the two child classes
                    # `.get(..., INF)`: no entry yet means "cannot build safely"
                    ca = cost.get(eg.find(a), INF)
                    cb = cost.get(eg.find(b), INF)
                    if ca == INF or cb == INF:
                        continue  # a child cannot be built safely (yet)
                    nc = weights[node[0]] + ca + cb  # gate weight + children's costs
                if nc < cost.get(c, INF):  # cheaper than anything seen (or first)
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

    Algorithm, step by step:
      1. For each root class, look at every node in it.
      2. A leaf costs 0. A gate is usable only if both its child classes have a
         finite SAFE cost (from `extract_constrained`); its cost is its weight
         plus the children's costs.
      3. Choose the cheapest usable node. If none is usable, the choice is
         `(None, INF)`, meaning no secure realisation exists for that output.
    Returns `{root_class: (node, cost)}`.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS
    out = {}  # root class -> (chosen node, its cost), e.g. {9: (("xor", (4, 5)), 5)}
    for r in roots:
        r = eg.find(r)
        node_best, cost_best = None, INF  # cheapest usable node so far (none yet)
        for node in eg._nodes[r]:
            if node[0] in ("var", "const"):
                nc = 0
            else:
                a, b = node[1]
                # children must be safely buildable; the root itself need not be
                ca = cost.get(eg.find(a), INF)
                cb = cost.get(eg.find(b), INF)
                if ca == INF or cb == INF:
                    continue
                nc = weights[node[0]] + ca + cb
            if nc < cost_best:
                cost_best, node_best = nc, node
        out[r] = (node_best, cost_best)  # (None, INF) means no secure option
    return out


def materialize_constrained(eg, best_internal, choices, roots, circuit):
    """Instantiate a constrained extraction; internal wires use safe nodes.

    Algorithm, step by step:
      1. For each root class, take the node chosen by `root_choices` (raise
         `MaterializeError` if there is none: no secure option exists).
      2. Build that node: a leaf becomes an input or constant; a gate first builds
         both of its child classes, then adds the gate.
      3. Children are built with `build_internal`, which uses ONLY the safe nodes
         in `best_internal`, shares a wire per class, and raises an error on a
         cycle or on a class that was never safely buildable.
      4. Append the resulting root wire to the circuit's outputs.
    The result contains no wire that the labeller marked unsafe, except possibly
    the outputs themselves.
    """
    wire_of = {}  # class -> wire already built, e.g. {3: "a0", 7: "and(a0,b1)"}
    visiting = set()  # classes on the current recursion path (cycle detection)

    def build_internal(c):
        """Build class `c` as an INTERNAL wire (it must be safe)."""
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
        """Add `node` to the circuit, building its child classes first."""
        op = node[0]
        if op == "var":
            return circuit.add_input(node[1])
        if op == "const":
            return circuit.add_const(node[1])
        a, b = node[1]  # the two child classes
        wa = build_internal(a)  # wire names of the children, built SAFELY first
        wb = build_internal(b)
        return circuit.add_gate(op, wa, wb)

    for r in roots:
        node, cost = choices[eg.find(r)]  # the node picked for this output
        if node is None:
            raise MaterializeError(f"no secure option for root class {eg.find(r)}")
        circuit.outputs.append(build_node(node))
    return circuit
