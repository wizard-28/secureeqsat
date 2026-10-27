"""Minimal equality-saturation e-graph over Boolean terms.

Purpose
-------
A small, readable e-graph written from scratch for the PREMISE TEST: "does
unrestricted Boolean rewriting plus cost-minimal extraction turn a secure masked
circuit into an insecure one?" It is a test harness, not the product. The real
engine used for later work is egglog (see `experiments/egglog_port`); this file
stays small so every line can be audited (design/0004).

Deliberately small and dependency-free: enough to test whether unrestricted
Boolean rewriting + cost-minimal extraction can turn a secure masked circuit
into an insecure one.

Terms (a "node" is one of these tuples):
    ('var', name)          leaf variable
    ('const', 0|1)         boolean constant
    ('xor', (a, b))        a ^ b
    ('and', (a, b))        a & b
where `a` and `b` are e-CLASS ids (integers), not nested terms.

Vocabulary
----------
  e-class   a set of terms known to be equal (identified by an integer id)
  e-node    one way of building a value: an operator plus child e-classes
  saturate  apply rewrite rules until no new equalities appear
  extract   pick, for every class, the cheapest node (a cost model decides)

The pipeline used by `run.py` is: build -> `saturate` -> `extract` ->
`materialize` -> security check.
"""


class EGraph:
    """An e-graph: e-classes (groups of equal terms) kept consistent by union-find.

    Internal state:
        _parent: union-find forest. `_parent[i]` points toward the class that
            currently represents class i.
        _nodes: canonical class id -> set of node tuples in that class.
        _memo: node key -> class id, so identical nodes are never duplicated
            (this is hash-consing).
        _next: next unused class id.
        c0, c1: the classes holding the constants 0 and 1.
    """

    def __init__(self):
        """Create an empty e-graph that already contains the constants 0 and 1."""
        # union-find forest: class id -> parent class id; a root points to itself,
        # e.g. {0: 0, 1: 1, 2: 0} means class 2 has been merged into class 0
        self._parent = {}
        # canonical class id -> its set of node keys,
        # e.g. {0: {("xor", (3, 4))}, 3: {("var", "a0")}}
        self._nodes = {}
        # node key -> the class that holds it (hash-consing table),
        # e.g. {("var", "a0"): 3}
        self._memo = {}
        self._next = 0  # the next unused class id, e.g. 7
        self.c0 = self.add_const(0)  # class id of the constant 0, e.g. 0
        self.c1 = self.add_const(1)  # class id of the constant 1, e.g. 1

    # ---- union-find -------------------------------------------------
    def _new(self):
        """Allocate a fresh, empty e-class and return its id."""
        i = self._next  # the id this class will get, e.g. 7
        self._next += 1
        self._parent[i] = i  # a brand-new class is its own representative
        self._nodes[i] = set()
        return i

    def find(self, x):
        """Return the canonical class id for class `x` (union-find lookup).

        Uses path halving: it shortens the chain of parents as it walks, so
        repeated lookups stay fast.
        """
        p = self._parent  # shorthand for the parent table
        while p[x] != x:  # keep climbing until x is a root (its own parent)
            # path halving: point x at its grandparent, so the next lookup from x
            # (or from anything below it) takes fewer steps
            p[x] = p[p[x]]
            x = p[x]
        return x

    def _key(self, node):
        """Canonical form of a node: children are replaced by their canonical class.

        Two nodes with equal keys are the same node, so they must share a class.
        Leaves ('var', 'const') are their own key.
        """
        if node[0] in ("var", "const"):
            return node  # leaves have no children, e.g. ("var", "a0")
        # same operator, but each child class replaced by its canonical class, so
        # ("xor", (5, 9)) and ("xor", (5, 7)) become equal once classes 7 and 9
        # are merged
        return (node[0], tuple(self.find(c) for c in node[1]))

    def add_node(self, node):
        """Add `node` to the e-graph and return the id of the class holding it.

        If an identical node already exists, its class is returned and nothing is
        added (hash-consing). Otherwise a new class is created for it.
        """
        key = self._key(node)  # canonical form, e.g. ("and", (3, 4))
        if key in self._memo:  # seen before: reuse its class, add nothing
            return self.find(self._memo[key])
        cid = self._new()  # a fresh class id for this new node
        self._nodes[cid].add(key)
        self._memo[key] = cid
        return cid

    def add_var(self, name):
        """Add the input variable `name`; returns its class id."""
        return self.add_node(("var", name))

    def add_const(self, v):
        """Add the constant `v` (0 or 1); returns its class id."""
        return self.add_node(("const", v))

    def add_xor(self, a, b):
        """Add `a ^ b` for classes `a`, `b`; returns the class id."""
        return self.add_node(("xor", (a, b)))

    def add_and(self, a, b):
        """Add `a & b` for classes `a`, `b`; returns the class id."""
        return self.add_node(("and", (a, b)))

    # ---- merge / rebuild --------------------------------------------
    def merge(self, a, b):
        """Declare classes `a` and `b` equal: union them, then restore consistency.

        Returns True if they were different classes (something changed), False if
        they were already the same.
        """
        ra, rb = self.find(a), self.find(b)  # the canonical classes of a and b
        if ra == rb:
            return False  # already the same class: nothing to do
        self._parent[rb] = ra  # union: rb's class now hangs under ra
        self.rebuild()  # merging may make other nodes identical; fix those too
        return True

    def rebuild(self):
        """Restore the e-graph invariant after merges (congruence closure).

        After two classes merge, two nodes that used to differ can have become
        identical (same operator, same child classes). Those nodes' classes must
        merge as well, which can cascade. This repeats until nothing changes, then
        rewrites `_nodes` and `_memo` in canonical form.

        Algorithm, step by step:
          1. Walk every node of every class and compute its canonical key
             (children replaced by their current canonical classes).
          2. Record key -> class in a fresh memo table. If the key was already
             seen in a DIFFERENT class, the two classes hold the same node, so
             they are equal: remember the pair to merge.
          3. If no pairs were found, store the fresh tables and stop.
          4. Otherwise union all remembered pairs (which changes canonical keys)
             and go back to step 1, because those unions can expose new
             duplicates.
        """
        while True:
            merges = []  # pairs of classes found equal this round, e.g. [(3, 8)]
            new_memo = {}  # rebuilt key -> class table, e.g. {("xor", (3, 4)): 3}
            new_nodes = {}  # rebuilt class -> node keys table
            for c in list(self._nodes.keys()):
                rc = self.find(c)  # canonical class owning these nodes
                for node in self._nodes[c]:
                    key = self._key(node)  # recompute with up-to-date child classes
                    if key in new_memo:
                        # Same node already seen in another class: they are equal.
                        other = new_memo[key]
                        if self.find(other) != rc:
                            merges.append((rc, other))
                    else:
                        new_memo[key] = rc
                        new_nodes.setdefault(rc, set()).add(key)
            if not merges:  # stable: nothing more to merge, so keep the new tables
                self._memo = new_memo
                self._nodes = new_nodes
                return
            for a, b in merges:  # union every pair found, then loop again
                ra, rb = self.find(a), self.find(b)
                if ra != rb:
                    self._parent[rb] = ra

    def num_classes(self):
        """Number of distinct e-classes (a size statistic)."""
        # a set of canonical ids: merged classes collapse into one entry
        return len({self.find(c) for c in self._nodes})

    def num_nodes(self):
        """Total number of e-nodes across all classes (a size statistic)."""
        return sum(len(v) for v in self._nodes.values())

    def all_binary_nodes(self):
        """List `(class, node)` for every XOR and AND node. Rules scan this list."""
        out = []  # e.g. [(5, ("xor", (3, 4))), (6, ("and", (3, 4)))]
        for c in list(self._nodes.keys()):  # `list(...)` copies, so merging is safe
            rc = self.find(c)
            for node in list(self._nodes[c]):
                if node[0] in ("xor", "and"):  # skip leaves: rules only rewrite gates
                    out.append((rc, node))
        return out


# ---- rewrite rules ---------------------------------------------------
# Each rule takes (eg, class, node) and returns a list of target classes to
# merge with `class`. A rule never merges anything itself: `apply_rule` does.


def rule_comm(eg, rc, node):
    """Commutativity: a op b -> b op a, for XOR and AND."""
    op, ch = node  # operator, e.g. "xor"; ch = the two child classes, e.g. (3, 4)
    if op in ("xor", "and"):
        # add the node with its children swapped, (4, 3); its class is the target
        return [eg.add_node((op, (ch[1], ch[0])))]
    return []


def rule_assoc(eg, rc, node):
    """Associativity: x op (y op z) -> (x op y) op z, for XOR and AND.

    Looks inside the middle child's class for a node with the same operator.
    Only this direction is written. Together with commutativity it lets the
    e-graph reach every regrouping of a chain of the same operator.

    Algorithm: for a node `x op mid`, look at every node `y op z` of the same
    operator in the class of `mid`. For each, build `x op y`, then `(x op y) op z`,
    and propose that class as equal to this node's class.
    """
    op, ch = node
    if op not in ("xor", "and"):
        return []
    x, mid = ch  # this node is `x op mid`; x and mid are class ids
    out = []  # classes proposed as equal to this node's class
    # every node inside `mid`'s class, since any of them could be `y op z`
    for n2 in list(eg._nodes[eg.find(mid)]):
        if n2[0] == op:  # same operator, so mid can be read as `y op z`
            y, z = n2[1]
            # x op (y op z)  ==  (x op y) op z : build the inner node, then the outer
            out.append(eg.add_node((op, (eg.add_node((op, (x, y))), z))))
    return out


def rule_identity(eg, rc, node):
    """Identity elements: x ^ 0 = x and x & 1 = x."""
    op, ch = node
    out = []  # classes proposed as equal to this node's class
    if op == "xor":
        x, y = ch
        if eg.find(x) == eg.c0:  # 0 ^ y = y, so this node equals y's class
            out.append(eg.find(y))
        if eg.find(y) == eg.c0:  # x ^ 0 = x
            out.append(eg.find(x))
    if op == "and":
        x, y = ch
        if eg.find(x) == eg.c1:  # 1 & y = y
            out.append(eg.find(y))
        if eg.find(y) == eg.c1:  # x & 1 = x
            out.append(eg.find(x))
    return out


def rule_involution(eg, rc, node):
    """XOR with itself cancels: x ^ x = 0.

    (The name is historical. This is the "self-inverse" law of XOR, not an
    involution in the sense of ~~x = x.)
    """
    # both operands in the SAME class means x ^ x, which is always 0
    if node[0] == "xor" and eg.find(node[1][0]) == eg.find(node[1][1]):
        return [eg.c0]
    return []


def rule_idempotence(eg, rc, node):
    """AND is idempotent: x & x = x."""
    # x & x: both operands are the same class, and the result is that class itself
    if node[0] == "and" and eg.find(node[1][0]) == eg.find(node[1][1]):
        return [eg.find(node[1][0])]
    return []


def rule_annihilator(eg, rc, node):
    """AND with zero is zero: x & 0 = 0."""
    if node[0] == "and":
        x, y = node[1]  # the two operand classes
        if eg.find(x) == eg.c0 or eg.find(y) == eg.c0:  # either side is the constant 0
            return [eg.c0]
    return []


def rule_distribute(eg, rc, node):
    """x & (y ^ z) -> (x & y) ^ (x & z)   (and its symmetric via comm)

    Algorithm: for an AND node `x & mid`, look at every XOR node `y ^ z` inside
    the class of `mid`. For each, build the nodes `x & y`, `x & z` and their XOR,
    and propose that XOR's class as equal to this AND's class. Applied after
    `rule_factor`, the two rules let the e-graph move freely between the factored
    and the expanded form.
    """
    if node[0] != "and":
        return []
    x, mid = node[1]  # this node is `x & mid`
    out = []
    for n2 in list(eg._nodes[eg.find(mid)]):  # look for `y ^ z` inside mid's class
        if n2[0] == "xor":
            y, z = n2[1]
            xy = eg.add_node(("and", (x, y)))  # class of x & y
            xz = eg.add_node(("and", (x, z)))  # class of x & z
            out.append(eg.add_node(("xor", (xy, xz))))  # (x&y) ^ (x&z)
    return out


def rule_factor(eg, rc, node):
    """(x & y) ^ (x & z) -> x & (y ^ z)   (the share-refolding rule)

    This is THE rule that causes the leak: it saves a gate, but it refolds the
    two shares of one secret (y ^ z) into a wire that equals the unmasked secret.
    A cost-only extractor therefore prefers it.

    Algorithm, step by step, for a node `p ^ q` (classes p and q):
      1. Look at every AND node `x & y` in class p and every AND node `u & v` in
         class q.
      2. If the two ANDs share a factor (x equals u, or x equals v, as classes),
         the XOR is `x&y ^ x&other`.
      3. Propose the class of `x & (y ^ other)`, built with new nodes, as equal to
         this XOR's class.
    """
    if node[0] != "xor":
        return []
    p, q = node[1]  # this node is `p ^ q`; p and q are classes
    out = []
    for np in list(eg._nodes[eg.find(p)]):  # every way p can be an AND ...
        if np[0] != "and":
            continue
        x, y = np[1]  # ... p = x & y
        for nq in list(eg._nodes[eg.find(q)]):  # ... and every way q can be an AND
            if nq[0] != "and":
                continue
            u, v = nq[1]  # q = u & v
            # Find the common factor x, in either operand position of the second AND.
            if eg.find(x) == eg.find(u):
                out.append(eg.add_node(("and", (x, eg.add_node(("xor", (y, v)))))))
            elif eg.find(x) == eg.find(v):
                out.append(eg.add_node(("and", (x, eg.add_node(("xor", (y, u)))))))
    return out


# CORE: laws that never refold shares. FULL adds distributivity and factoring.
RULES_CORE = [
    rule_comm,
    rule_assoc,
    rule_identity,
    rule_involution,
    rule_idempotence,
    rule_annihilator,
]
RULES_FULL = RULES_CORE + [rule_distribute, rule_factor]


def apply_rule(eg, rule):
    """Apply one rule once over every node, merging what it proposes.

    Works on a snapshot of the node list so that merging while iterating is safe.
    Returns True if any merge happened (the e-graph changed).

    Algorithm, step by step:
      1. Take a snapshot of every (class, node) pair for XOR and AND nodes.
      2. For each pair, ask the rule which classes this node's class should equal.
      3. For each proposed class that is not already the same class, merge them
         (which also triggers `rebuild`) and note that something changed.
    """
    changed = False  # becomes True as soon as any merge actually happens
    snapshot = eg.all_binary_nodes()  # frozen list: merging below must not disturb it
    for rc, node in snapshot:
        rc = eg.find(rc)  # earlier merges may have changed this class's identity
        for target in rule(eg, rc, node):  # classes the rule says equal this one
            if eg.find(rc) != eg.find(target):  # skip proposals already known
                eg.merge(rc, target)
                rc = eg.find(rc)
                changed = True
    return changed


def saturate(eg, rules, max_iters=25, max_classes=60000):
    """Apply all `rules` repeatedly until nothing changes, or a limit is hit.

    Returns `(iterations, saturated, hit_limit)`: how many rounds ran, whether a
    fixed point was reached, and whether it stopped because of `max_iters` or
    `max_classes` (the e-graph can blow up, especially on chains of gadgets).

    Algorithm, step by step:
      1. Repeat up to `max_iters` rounds.
      2. In each round apply every rule once with `apply_rule`; remember whether
         any rule changed the e-graph.
      3. After each rule, if the e-graph has more than `max_classes` classes, give
         up and report that the limit was hit.
      4. If a whole round changed nothing, no rule can add anything new: the
         e-graph is SATURATED, so stop and report success.
    """
    for it in range(max_iters):  # `it` counts rounds, e.g. 0, 1, 2, ...
        changed = False  # did any rule change the e-graph in this round?
        for rule in rules:
            if apply_rule(eg, rule):
                changed = True
            if eg.num_classes() > max_classes:  # blow-up guard
                return it, False, True  # (rounds, not saturated, limit hit)
        if not changed:  # a full round with no change: a fixed point
            return it, True, False  # (rounds, saturated, no limit hit)
    return max_iters, False, True  # ran out of rounds before saturating


# ---- extraction ------------------------------------------------------


def extract(eg, weights=None, max_iters=400):
    """Cost-minimal extraction by fixed-point iteration. Returns `(best, cost)`.

    For each class, find the cheapest node, where a node costs its operator
    weight plus the cost of its children (leaves cost 0). Repeats until no cost
    improves. This is TREE cost: a subterm used twice is paid for twice.

    Args:
        eg: the saturated e-graph.
        weights: `{"and": w, "xor": w}`; defaults to AND=2, XOR=1.
        max_iters: safety limit on improvement rounds.

    Returns:
        best: `{class: chosen_node}`; cost: `{class: cost}`.

    This extractor knows nothing about security: it just minimises cost, which
    is exactly why it picks the cheaper, leaking circuit.

    Algorithm, step by step (a Bellman-Ford style fixed point):
      1. Start with no cost known for any class.
      2. Repeat: for every node of every class, compute the node's cost. A leaf
         (variable or constant) costs 0. An AND or XOR costs its weight plus the
         cost of its two child classes, but only once both children have a cost.
      3. If that is cheaper than the best cost recorded for the class, record the
         node as the class's best and note that something improved.
      4. Stop when a full pass improves nothing (or after `max_iters` passes).
         Each class now holds its cheapest node and that node's cost.
    """
    if weights is None:
        weights = {"and": 2, "xor": 1}  # per-gate cost: an AND counts double
    eg.rebuild()  # make sure the node tables are canonical before costing
    classes = list(eg._nodes.keys())  # every class id, e.g. [0, 1, 2, 5]
    cost = {}  # class -> cheapest known cost, e.g. {0: 0, 5: 4}
    best = {}  # class -> the node that achieves that cost
    for _ in range(max_iters):
        changed = False  # did any class get a cheaper node this pass?
        for c in classes:
            c = eg.find(c)  # canonical class for this id
            for node in eg._nodes[c]:
                if node[0] in ("var", "const"):
                    nc = 0  # nc = this node's total cost; leaves are free
                else:
                    a, b = node[1]  # the two child classes
                    ca = cost.get(eg.find(a))  # child costs; None = not known yet
                    cb = cost.get(eg.find(b))
                    if ca is None or cb is None:
                        continue  # a child has no cost yet; try again next round
                    nc = weights[node[0]] + ca + cb  # gate weight + both children
                if c not in cost or nc < cost[c]:  # first cost, or a cheaper one
                    cost[c] = nc
                    best[c] = node
                    changed = True
        if not changed:
            break
    return best, cost


class MaterializeError(Exception):
    """Raised when extracted choices cannot be turned into a circuit."""


def materialize(eg, best, roots, circuit):
    """Build a real `Circuit` from the chosen nodes, starting at the `roots`.

    Args:
        eg: the e-graph.
        best: `{class: chosen_node}` from `extract`.
        roots: the output classes.
        circuit: an empty `Circuit` to fill in (its outputs are set).

    Each class becomes one wire, shared by every user of that class. Raises
    `MaterializeError` on a cycle or a class with no chosen node.

    Algorithm, step by step (depth-first):
      1. For each root class, call `build`.
      2. `build(c)` returns the existing wire if class c was already built.
      3. Otherwise it looks up the chosen node for c, builds the node's child
         classes first (recursively), then adds the node as an input, constant or
         gate and remembers the wire for c.
      4. A `visiting` set tracks the classes on the current path: meeting one
         again means the chosen nodes form a cycle, which is an error.
    """
    wire_of = {}  # class -> wire name already built, e.g. {3: "a0", 5: "xor(a0,r)"}
    visiting = set()  # classes on the current recursion path, to detect cycles

    def build(c):
        """Return the wire for class `c`, building its children first."""
        c = eg.find(c)
        if c in wire_of:
            return wire_of[c]
        if c in visiting:
            raise MaterializeError(f"cycle in extraction at class {c!r}")
        if c not in best:
            raise MaterializeError(f"no extracted node for class {c!r}")
        visiting.add(c)  # mark c as "in progress" before descending into children
        op, payload = best[c]  # chosen node, e.g. ("xor", (3, 4)) -> op="xor"
        if op == "var":
            w = circuit.add_input(payload)
        elif op == "const":
            w = circuit.add_const(payload)
        elif op == "xor":
            w = circuit.add_gate("xor", build(payload[0]), build(payload[1]))
        elif op == "and":
            w = circuit.add_gate("and", build(payload[0]), build(payload[1]))
        else:
            raise MaterializeError(f"bad op {op!r}")
        visiting.discard(c)
        wire_of[c] = w
        return w

    for r in roots:
        circuit.outputs.append(build(r))
    return circuit
