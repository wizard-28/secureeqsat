"""Minimal equality-saturation e-graph over Boolean terms.

Deliberately small and dependency-free: enough to test whether unrestricted
Boolean rewriting + cost-minimal extraction can turn a secure masked circuit
into an insecure one.

Terms:
    ('var', name)          leaf variable
    ('const', 0|1)         boolean constant
    ('xor', (a, b))        a ^ b
    ('and', (a, b))        a & b
"""


class EGraph:
    def __init__(self):
        self._parent = {}
        self._nodes = {}  # canonical class -> set of node tuples
        self._memo = {}  # node key -> class
        self._next = 0
        self.c0 = self.add_const(0)
        self.c1 = self.add_const(1)

    # ---- union-find -------------------------------------------------
    def _new(self):
        i = self._next
        self._next += 1
        self._parent[i] = i
        self._nodes[i] = set()
        return i

    def find(self, x):
        p = self._parent
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x

    def _key(self, node):
        if node[0] in ("var", "const"):
            return node
        return (node[0], tuple(self.find(c) for c in node[1]))

    def add_node(self, node):
        key = self._key(node)
        if key in self._memo:
            return self.find(self._memo[key])
        cid = self._new()
        self._nodes[cid].add(key)
        self._memo[key] = cid
        return cid

    def add_var(self, name):
        return self.add_node(("var", name))

    def add_const(self, v):
        return self.add_node(("const", v))

    def add_xor(self, a, b):
        return self.add_node(("xor", (a, b)))

    def add_and(self, a, b):
        return self.add_node(("and", (a, b)))

    # ---- merge / rebuild --------------------------------------------
    def merge(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self._parent[rb] = ra
        self.rebuild()
        return True

    def rebuild(self):
        while True:
            merges = []
            new_memo = {}
            new_nodes = {}
            for c in list(self._nodes.keys()):
                rc = self.find(c)
                for node in self._nodes[c]:
                    key = self._key(node)
                    if key in new_memo:
                        other = new_memo[key]
                        if self.find(other) != rc:
                            merges.append((rc, other))
                    else:
                        new_memo[key] = rc
                        new_nodes.setdefault(rc, set()).add(key)
            if not merges:
                self._memo = new_memo
                self._nodes = new_nodes
                return
            for a, b in merges:
                ra, rb = self.find(a), self.find(b)
                if ra != rb:
                    self._parent[rb] = ra

    def num_classes(self):
        return len({self.find(c) for c in self._nodes})

    def num_nodes(self):
        return sum(len(v) for v in self._nodes.values())

    def all_binary_nodes(self):
        out = []
        for c in list(self._nodes.keys()):
            rc = self.find(c)
            for node in list(self._nodes[c]):
                if node[0] in ("xor", "and"):
                    out.append((rc, node))
        return out


# ---- rewrite rules ---------------------------------------------------
# Each rule takes (eg, class, node) and returns a list of target classes to
# merge with `class`.


def rule_comm(eg, rc, node):
    op, ch = node
    if op in ("xor", "and"):
        return [eg.add_node((op, (ch[1], ch[0])))]
    return []


def rule_assoc(eg, rc, node):
    op, ch = node
    if op not in ("xor", "and"):
        return []
    x, mid = ch
    out = []
    for n2 in list(eg._nodes[eg.find(mid)]):
        if n2[0] == op:
            y, z = n2[1]
            out.append(eg.add_node((op, (eg.add_node((op, (x, y))), z))))
    return out


def rule_identity(eg, rc, node):
    op, ch = node
    out = []
    if op == "xor":
        x, y = ch
        if eg.find(x) == eg.c0:
            out.append(eg.find(y))
        if eg.find(y) == eg.c0:
            out.append(eg.find(x))
    if op == "and":
        x, y = ch
        if eg.find(x) == eg.c1:
            out.append(eg.find(y))
        if eg.find(y) == eg.c1:
            out.append(eg.find(x))
    return out


def rule_involution(eg, rc, node):
    if node[0] == "xor" and eg.find(node[1][0]) == eg.find(node[1][1]):
        return [eg.c0]
    return []


def rule_idempotence(eg, rc, node):
    if node[0] == "and" and eg.find(node[1][0]) == eg.find(node[1][1]):
        return [eg.find(node[1][0])]
    return []


def rule_annihilator(eg, rc, node):
    if node[0] == "and":
        x, y = node[1]
        if eg.find(x) == eg.c0 or eg.find(y) == eg.c0:
            return [eg.c0]
    return []


def rule_distribute(eg, rc, node):
    """x & (y ^ z) -> (x & y) ^ (x & z)   (and its symmetric via comm)"""
    if node[0] != "and":
        return []
    x, mid = node[1]
    out = []
    for n2 in list(eg._nodes[eg.find(mid)]):
        if n2[0] == "xor":
            y, z = n2[1]
            xy = eg.add_node(("and", (x, y)))
            xz = eg.add_node(("and", (x, z)))
            out.append(eg.add_node(("xor", (xy, xz))))
    return out


def rule_factor(eg, rc, node):
    """(x & y) ^ (x & z) -> x & (y ^ z)   (the share-refolding rule)"""
    if node[0] != "xor":
        return []
    p, q = node[1]
    out = []
    for np in list(eg._nodes[eg.find(p)]):
        if np[0] != "and":
            continue
        x, y = np[1]
        for nq in list(eg._nodes[eg.find(q)]):
            if nq[0] != "and":
                continue
            u, v = nq[1]
            if eg.find(x) == eg.find(u):
                out.append(eg.add_node(("and", (x, eg.add_node(("xor", (y, v)))))))
            elif eg.find(x) == eg.find(v):
                out.append(eg.add_node(("and", (x, eg.add_node(("xor", (y, u)))))))
    return out


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
    changed = False
    snapshot = eg.all_binary_nodes()
    for rc, node in snapshot:
        rc = eg.find(rc)
        for target in rule(eg, rc, node):
            if eg.find(rc) != eg.find(target):
                eg.merge(rc, target)
                rc = eg.find(rc)
                changed = True
    return changed


def saturate(eg, rules, max_iters=25, max_classes=60000):
    """Returns (iterations, saturated_bool, hit_limit_bool)."""
    for it in range(max_iters):
        changed = False
        for rule in rules:
            if apply_rule(eg, rule):
                changed = True
            if eg.num_classes() > max_classes:
                return it, False, True
        if not changed:
            return it, True, False
    return max_iters, False, True


# ---- extraction ------------------------------------------------------


def extract(eg, weights=None, max_iters=400):
    """Tree-cost fixed point extraction. Returns (best, cost)."""
    if weights is None:
        weights = {"and": 2, "xor": 1}
    eg.rebuild()
    classes = list(eg._nodes.keys())
    cost = {}
    best = {}
    for _ in range(max_iters):
        changed = False
        for c in classes:
            c = eg.find(c)
            for node in eg._nodes[c]:
                if node[0] in ("var", "const"):
                    nc = 0
                else:
                    a, b = node[1]
                    ca = cost.get(eg.find(a))
                    cb = cost.get(eg.find(b))
                    if ca is None or cb is None:
                        continue
                    nc = weights[node[0]] + ca + cb
                if c not in cost or nc < cost[c]:
                    cost[c] = nc
                    best[c] = node
                    changed = True
        if not changed:
            break
    return best, cost


class MaterializeError(Exception):
    pass


def materialize(eg, best, roots, circuit):
    """Instantiate the chosen node for each class into `circuit` (a Circuit)."""
    wire_of = {}
    visiting = set()

    def build(c):
        c = eg.find(c)
        if c in wire_of:
            return wire_of[c]
        if c in visiting:
            raise MaterializeError(f"cycle in extraction at class {c!r}")
        if c not in best:
            raise MaterializeError(f"no extracted node for class {c!r}")
        visiting.add(c)
        op, payload = best[c]
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
