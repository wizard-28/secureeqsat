"""Masked Boolean circuits and a first-order probing-security checker.

Security model (standard, glitch-free, 2 shares):
    For a secret `s` split into shares s0, s1 with s0 uniform and s1 = s0 ^ s,
    and fresh randomness uniform and independent, a circuit is FIRST-ORDER
    PROBING SECURE iff every wire's value distribution is independent of the
    secret(s).

Checker is sound and complete for this model on straight-line circuits:
it enumerates all free-uniform assignments for each secret assignment and
compares each wire's value distribution (as an ordered sequence of all
assignments, which is a canonical encoding of the multiset).
"""


class Circuit:
    def __init__(self):
        self.inputs = []  # input names, in order
        self.wires = []  # (name, op, payload)
        self.outputs = []
        self._names = {}

    def add_input(self, name):
        if name not in self._names:
            self._names[name] = name
            self.inputs.append(name)
            self.wires.append((name, "input", name))
        return self._names[name]

    def add_const(self, v):
        key = f"const{1 if v else 0}"
        if key not in self._names:
            self._names[key] = key
            self.wires.append((key, "const", bool(v)))
        return self._names[key]

    def add_gate(self, op, a, b):
        key = f"{op}({a},{b})"
        if key not in self._names:
            self._names[key] = key
            self.wires.append((key, op, (a, b)))
        return self._names[key]

    def gate_count(self):
        return sum(1 for (_, op, _) in self.wires if op in ("and", "xor"))

    def and_count(self):
        return sum(1 for (_, op, _) in self.wires if op == "and")

    def xor_count(self):
        return sum(1 for (_, op, _) in self.wires if op == "xor")


def evaluate(circ, assignment):
    vals = {}
    for name, op, payload in circ.wires:
        if op == "input":
            vals[name] = bool(assignment[name])
        elif op == "const":
            vals[name] = payload
        elif op == "xor":
            a, b = payload
            vals[name] = vals[a] ^ vals[b]
        elif op == "and":
            a, b = payload
            vals[name] = vals[a] & vals[b]
        else:
            raise ValueError(op)
    return vals


def check_first_order(circ, secret_groups, free_vars):
    """Return {wire_name: bool_safe}.

    secret_groups: {secret_name: [share_input_names]} with shares[0] the free
                   (uniform) share; remaining shares are reconstructed as
                   shares[0] ^ secret.
    free_vars:     all inputs that are uniform and free (one share per secret
                   plus every fresh randomness).
    """
    secrets = list(secret_groups.keys())
    wire_names = [w[0] for w in circ.wires]
    per_secret = []
    for sbits in range(1 << len(secrets)):
        svals = {s: (sbits >> i) & 1 for i, s in enumerate(secrets)}
        seq = {w: [] for w in wire_names}
        for fa in range(1 << len(free_vars)):
            ass = {v: (fa >> j) & 1 for j, v in enumerate(free_vars)}
            for s, shares in secret_groups.items():
                for k in range(1, len(shares)):
                    ass[shares[k]] = ass[shares[0]] ^ svals[s]
            vals = evaluate(circ, ass)
            for w in wire_names:
                seq[w].append(vals[w])
        per_secret.append(seq)
    safe = {}
    for w in wire_names:
        # Compare DISTRIBUTIONS, not ordered sequences: the same uniform wire
        # can appear as a different permutation of values across secret
        # assignments.  For Boolean wires the distribution is determined by
        # the number of 1s over the (fixed-size) free-variable sample space.
        base = sum(per_secret[0][w])
        safe[w] = all(sum(ps[w]) == base for ps in per_secret[1:])
    return safe


def unsafe_wires(safe_map):
    return [w for w, ok in safe_map.items() if not ok]


# ---- fixtures --------------------------------------------------------


def build_isw_and():
    """2-share ISW masked AND. Known first-order secure."""
    c = Circuit()
    a0 = c.add_input("a0")
    a1 = c.add_input("a1")
    b0 = c.add_input("b0")
    b1 = c.add_input("b1")
    r = c.add_input("r")
    p1 = c.add_gate("and", a0, b0)
    c0 = c.add_gate("xor", p1, r)
    p2 = c.add_gate("and", a0, b1)
    p3 = c.add_gate("and", a1, b0)
    p4 = c.add_gate("and", a1, b1)
    # ISW is secure only with r folded in early: every c1-chain intermediate
    # must contain the fresh random, otherwise a0*b1 ^ a1*b0 leaks.
    w1 = c.add_gate("xor", r, p2)
    w2 = c.add_gate("xor", w1, p3)
    c1 = c.add_gate("xor", w2, p4)
    c.outputs = [c0, c1]
    return c


def build_masked_buffer():
    """Two shares of a: (a0 ^ r, a1 ^ r). Known secure."""
    c = Circuit()
    a0 = c.add_input("a0")
    a1 = c.add_input("a1")
    r = c.add_input("r")
    c.outputs = [c.add_gate("xor", a0, r), c.add_gate("xor", a1, r)]
    return c


def build_naive_unmasked_intermediate():
    """A masking built through an unmasked intermediate t = (a0^a1)&(b0^b1).

    Outputs (t ^ r, r) are individually uniform, but the intermediate t is the
    secret product and is a first-order violation.
    """
    c = Circuit()
    a0 = c.add_input("a0")
    a1 = c.add_input("a1")
    b0 = c.add_input("b0")
    b1 = c.add_input("b1")
    r = c.add_input("r")
    x = c.add_gate("xor", a0, a1)  # = secret a
    y = c.add_gate("xor", b0, b1)  # = secret b
    t = c.add_gate("and", x, y)  # = a & b  (unmasked!)
    c.outputs = [c.add_gate("xor", t, r), r]
    return c


SECRET_GROUPS_AND = {"a": ["a0", "a1"], "b": ["b0", "b1"]}
FREE_AND = ["a0", "b0", "r"]
SECRET_GROUPS_BUF = {"a": ["a0", "a1"]}
FREE_BUF = ["a0", "r"]
