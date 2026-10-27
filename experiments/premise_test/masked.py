"""Masked Boolean circuits and a first-order probing-security checker.

Purpose
-------
This module is the foundation of the whole project. It provides:

  * `Circuit`: a tiny straight-line Boolean circuit (inputs, constants, AND and XOR
    gates), with structural sharing so that gate counts are real DAG counts.
  * `evaluate`: runs a circuit on one assignment of its inputs.
  * `check_first_order`: the in-house SECURITY CHECKER, which says, wire by wire,
    whether a masked circuit leaks a secret to an attacker who probes one wire.
  * Hand-written FIXTURES (known secure and known insecure circuits) used to
    validate the checker itself.

Everything else in the repo (the e-graph experiments, constrained extraction, the
labeller, the VerifMSI cross-check) builds on these definitions.

Security model (standard, glitch-free, 2 shares)
------------------------------------------------
For a secret `s` split into shares s0, s1 with s0 uniform and s1 = s0 ^ s,
and fresh randomness uniform and independent, a circuit is FIRST-ORDER
PROBING SECURE iff every wire's value distribution is independent of the
secret(s). In words: an attacker who sees any single wire learns nothing about
the secret, because the wire looks the same whatever the secret is.

Checker is sound and complete for this model on straight-line circuits:
it enumerates all free-uniform assignments for each secret assignment and
compares each wire's value distribution (as an ordered sequence of all
assignments, which is a canonical encoding of the multiset).

Cost: the checker is exact but EXPONENTIAL in the number of free bits (it tries
every assignment). That is why `experiments/labeller` (bitsliced, faster) and
`experiments/composition` (PINI, no enumeration) exist for bigger circuits.

Trust boundary: no security claim may rest on this checker alone; it is
cross-validated against VerifMSI in `experiments/oracle_crosscheck`.
"""


class Circuit:
    """A straight-line Boolean circuit.

    Every wire is created once and never changes, in dependency order, so a single
    pass over `wires` evaluates the circuit.

    Attributes:
        inputs: input wire names, in the order they were declared.
        wires: list of `(name, op, payload)` in creation order, where `op` is one
            of "input" (payload = the name), "const" (payload = a bool) or
            "and" / "xor" (payload = a pair of operand wire names).
        outputs: names of the wires that are the circuit's outputs.

    Wire names are derived from their definition (for example "xor(a0,r)"), so
    adding the same gate twice returns the same wire. This hash-consing makes
    `gate_count()` count each shared gate once, as hardware would.
    """

    def __init__(self):
        """Create an empty circuit with no inputs, wires or outputs."""
        self.inputs = []  # input names, in order, e.g. ["a0", "a1", "b0", "b1", "r"]
        # every wire as (name, op, payload), e.g. ("xor(a0,r)", "xor", ("a0", "r"))
        self.wires = []
        self.outputs = []  # names of the output wires, e.g. ["xor(and(a0,b0),r)"]
        # key -> wire name; makes identical gates share one wire,
        # e.g. {"a0": "a0", "xor(a0,r)": "xor(a0,r)"}
        self._names = {}

    def add_input(self, name):
        """Declare an input wire called `name` (idempotent) and return its name."""
        if name not in self._names:  # only declare each input once
            self._names[name] = name
            self.inputs.append(name)
            self.wires.append((name, "input", name))
        return self._names[name]

    def add_const(self, v):
        """Add a constant wire (0 or 1) and return its name. Reused if it exists."""
        key = f"const{1 if v else 0}"  # "const1" or "const0": one wire per constant
        if key not in self._names:
            self._names[key] = key
            self.wires.append((key, "const", bool(v)))
        return self._names[key]

    def add_gate(self, op, a, b):
        """Add `op`(a, b), where op is "and" or "xor" and a, b are wire names.

        If an identical gate (same op and operands) already exists it is reused
        instead of duplicated. Returns the name of the (new or existing) wire.
        """
        # The gate's own definition is its name, e.g. "and(a0,b1)". Same op and same
        # operands give the same string, which is what makes sharing work.
        key = f"{op}({a},{b})"
        if key not in self._names:
            self._names[key] = key
            self.wires.append((key, op, (a, b)))
        return self._names[key]

    def gate_count(self):
        """Number of AND and XOR gates (inputs and constants are free)."""
        # Adds 1 for each wire whose op is a gate; `_` ignores the name and payload.
        return sum(1 for (_, op, _) in self.wires if op in ("and", "xor"))

    def and_count(self):
        """Number of AND gates only. In masking each AND is the expensive part."""
        return sum(1 for (_, op, _) in self.wires if op == "and")

    def xor_count(self):
        """Number of XOR gates only. XOR is cheap in masking (it is share-wise)."""
        return sum(1 for (_, op, _) in self.wires if op == "xor")


def evaluate(circ, assignment):
    """Run `circ` once and return `{wire_name: bool}` for every wire.

    Args:
        circ: the circuit.
        assignment: `{input_name: 0 or 1}` giving every input a value.

    Algorithm: walk `circ.wires` once, front to back. An input takes its value from
    `assignment`, a constant takes its stored value, and an AND or XOR takes the
    AND or XOR of the two operand wires' values, which were already computed
    because every wire is created after its operands. Wires are stored in
    dependency order, so one forward pass is enough.
    """
    vals = {}  # wire name -> its value this run, e.g. {"a0": True, "r": False}
    for name, op, payload in circ.wires:  # creation order = dependency order
        if op == "input":
            vals[name] = bool(assignment[name])  # 0/1 from the caller -> True/False
        elif op == "const":
            vals[name] = payload
        elif op == "xor":
            a, b = payload  # names of the two operand wires, e.g. ("a0", "r")
            vals[name] = vals[a] ^ vals[b]  # `^` on bools is XOR: True ^ True = False
        elif op == "and":
            a, b = payload
            vals[name] = vals[a] & vals[b]  # `&` on bools is AND: True & False = False
        else:
            raise ValueError(op)
    return vals


def check_first_order(circ, secret_groups, free_vars):
    """THE SECURITY CHECKER: return `{wire_name: bool_safe}` for every wire.

    A wire is safe iff the distribution of its value (over the uniform random
    bits) is the same for every value of the secrets. For a Boolean wire the
    distribution is fixed by how many 1s it takes over the whole sample space, so
    the test is "the number of 1s is equal for every secret assignment".

    Args:
        circ: the circuit to check.
        secret_groups: `{secret_name: [share_input_names]}` with shares[0] the free
            (uniform) share; remaining shares are reconstructed as
            shares[0] ^ secret.
        free_vars: all inputs that are uniform and free (one share per secret
            plus every fresh randomness).

    Algorithm, step by step:
      1. For every assignment of the SECRET values (a=0/1, b=0/1, ...):
      2.   For every assignment of the FREE bits (the uniform random bits):
      3.     Set the remaining shares so that the shares XOR to the secret
             (share k = share 0 ^ secret).
      4.     Evaluate the whole circuit once and append each wire's value to that
             wire's list for this secret assignment.
      5. For each wire, count the 1s in its list for the first secret assignment
         (the baseline) and in every other secret assignment.
      6. The wire is SAFE iff all counts are equal, i.e. the wire's distribution
         does not depend on the secret. One unequal count marks it as leaking.

    Exact, but 2**len(free_vars) evaluations per secret assignment, hence
    exponential. A worked example: for a wire `a0 & a1` with one secret `a`, the
    count of 1s is 1 for a=0 but 0 for a=1, so the wire is flagged as leaking.
    """
    secrets = list(secret_groups.keys())  # names of the secrets, e.g. ["a", "b"]
    wire_names = [w[0] for w in circ.wires]  # every wire's name, in creation order
    # One entry per secret assignment; each maps wire name -> list of its values
    # over all free assignments, e.g. [{"a0": [0, 1], ...}, {"a0": [0, 1], ...}]
    per_secret = []
    # `1 << n` is 2**n (shift the bit 1 left n places), so this counts through all
    # 2**len(secrets) combinations of secret values, as a bit pattern `sbits`.
    for sbits in range(1 << len(secrets)):
        # Unpack the bits of `sbits`: `(sbits >> i) & 1` shifts bit i down to the
        # lowest place and masks it, e.g. sbits=0b10 -> {"a": 0, "b": 1}.
        svals = {s: (sbits >> i) & 1 for i, s in enumerate(secrets)}
        seq = {w: [] for w in wire_names}  # wire -> its values, e.g. {"a0": []}
        # Enumerate every assignment of the free (uniform random) variables, again
        # as a bit pattern: 2**len(free_vars) combinations.
        for fa in range(1 << len(free_vars)):
            # Same unpacking trick: bit j of `fa` is free variable j,
            # e.g. fa=0b101 -> {"a0": 1, "b0": 0, "r": 1}.
            ass = {v: (fa >> j) & 1 for j, v in enumerate(free_vars)}
            # Fix the remaining shares so that the shares XOR to the secret.
            for s, shares in secret_groups.items():
                for k in range(1, len(shares)):
                    # share k = share 0 XOR secret, so share0 ^ share_k = secret
                    ass[shares[k]] = ass[shares[0]] ^ svals[s]
            vals = evaluate(circ, ass)  # every wire's value for this assignment
            for w in wire_names:
                seq[w].append(vals[w])
        per_secret.append(seq)
    safe = {}  # wire name -> True if safe, e.g. {"a0": True, "xor(b1,b0)": False}
    for w in wire_names:
        # Compare DISTRIBUTIONS, not ordered sequences: the same uniform wire
        # can appear as a different permutation of values across secret
        # assignments.  For Boolean wires the distribution is determined by
        # the number of 1s over the (fixed-size) free-variable sample space.
        # `sum` of a list of True/False counts the Trues, i.e. the number of 1s.
        base = sum(per_secret[0][w])  # count of 1s when the secrets are all 0
        # safe only if every other secret assignment gives exactly the same count
        safe[w] = all(sum(ps[w]) == base for ps in per_secret[1:])
    return safe


def unsafe_wires(safe_map):
    """Given the dict from `check_first_order`, return the names of leaking wires."""
    return [w for w, ok in safe_map.items() if not ok]


# ---- fixtures --------------------------------------------------------
# Hand-written circuits with a known verdict. They exist to validate the checker:
# if it ever disagrees with the expected verdict, the checker is wrong.


def build_isw_and():
    """2-share ISW masked AND. Known first-order secure.

    Computes shares (c0, c1) of a AND b from shares (a0, a1) and (b0, b1) using one
    fresh random bit `r`: 8 gates (4 AND + 4 XOR) and 1 random. This is the
    baseline against which every optimisation in the project is compared.
    """
    c = Circuit()
    a0 = c.add_input("a0")  # share 0 of secret a (a uniform random bit)
    a1 = c.add_input("a1")  # share 1 of secret a, so a = a0 ^ a1
    b0 = c.add_input("b0")  # share 0 of secret b
    b1 = c.add_input("b1")  # share 1 of secret b
    r = c.add_input("r")  # the one fresh random bit of the gadget
    p1 = c.add_gate("and", a0, b0)  # partial product a0*b0
    c0 = c.add_gate("xor", p1, r)  # OUTPUT SHARE 0 = a0*b0 ^ r
    p2 = c.add_gate("and", a0, b1)  # cross product a0*b1
    p3 = c.add_gate("and", a1, b0)  # cross product a1*b0
    p4 = c.add_gate("and", a1, b1)  # partial product a1*b1
    # ISW is secure only with r folded in early: every c1-chain intermediate
    # must contain the fresh random, otherwise a0*b1 ^ a1*b0 leaks.
    w1 = c.add_gate("xor", r, p2)  # r ^ a0*b1: masked by r, so uniform
    w2 = c.add_gate("xor", w1, p3)  # still masked by r
    c1 = c.add_gate("xor", w2, p4)  # OUTPUT SHARE 1; c0 ^ c1 = a AND b
    c.outputs = [c0, c1]
    return c


def build_masked_buffer():
    """Two shares of a: (a0 ^ r, a1 ^ r). Known secure.

    The simplest masked circuit: re-randomises a sharing (this is what a
    "refresh" does). The secret a0 ^ a1 is unchanged because r cancels.
    """
    c = Circuit()
    a0 = c.add_input("a0")  # share 0 of secret a
    a1 = c.add_input("a1")  # share 1 of secret a
    r = c.add_input("r")  # the fresh random bit XORed into both shares
    # new shares (a0^r, a1^r): the XOR of the two is still a0^a1 = a, because r
    # appears twice and cancels
    c.outputs = [c.add_gate("xor", a0, r), c.add_gate("xor", a1, r)]
    return c


def build_isw_and_wrong_order():
    """Same ISW function with r folded in too late (known insecure).

    The intermediate a0&b1 ^ a1&b0 = a0*b ^ a*b0 leaks; real ISW folds the
    fresh random into every c1-chain intermediate. Shows that security depends
    on the ORDER of the XORs, not only on the function computed.
    """
    c = Circuit()
    a0 = c.add_input("a0")  # shares of secret a
    a1 = c.add_input("a1")
    b0 = c.add_input("b0")  # shares of secret b
    b1 = c.add_input("b1")
    r = c.add_input("r")  # fresh random bit
    p1 = c.add_gate("and", a0, b0)  # a0*b0
    c0 = c.add_gate("xor", p1, r)  # output share 0
    p2 = c.add_gate("and", a0, b1)  # cross products and the last partial product
    p3 = c.add_gate("and", a1, b0)
    p4 = c.add_gate("and", a1, b1)
    # r is added LAST here, so the partial sums t1 and t2 are not masked by r.
    t1 = c.add_gate("xor", p2, p3)  # a0*b1 ^ a1*b0 = a0*b ^ a*b0: LEAKS
    t2 = c.add_gate("xor", t1, p4)  # still unmasked
    c1 = c.add_gate("xor", t2, r)  # r arrives too late to protect t1 and t2
    c.outputs = [c0, c1]
    return c


def build_dom_and():
    """2-share DOM masked AND, glitch-free model (registers elided).

    DOM (domain-oriented masking) is a second masked AND gadget with the same job
    as ISW. In hardware its cross terms are registered; here the registers are
    left out because this checker models the glitch-free case.

    Structure transcribed from VerifMSI's own generate_dom_and.py:
        c0 = a0&b0 ^ (a0&b1 ^ r)
        c1 = a1&b1 ^ (a1&b0 ^ r)
    Known first-order secure (glitch-free).
    """
    c = Circuit()
    a0 = c.add_input("a0")  # shares of secret a
    a1 = c.add_input("a1")
    b0 = c.add_input("b0")  # shares of secret b
    b1 = c.add_input("b1")
    r = c.add_input("r")  # fresh random bit, used once in each domain
    x = c.add_gate("and", a0, b0)  # inner-domain product, share-0 domain
    y = c.add_gate("and", a0, b1)  # cross-domain product
    u = c.add_gate("and", a1, b0)  # cross-domain product
    v = c.add_gate("and", a1, b1)  # inner-domain product, share-1 domain
    y2 = c.add_gate("xor", y, r)  # cross term masked by r (a register in hardware)
    u2 = c.add_gate("xor", u, r)  # cross term masked by the same r
    c.outputs = [c.add_gate("xor", x, y2), c.add_gate("xor", v, u2)]
    return c


def build_naive_unmasked_intermediate():
    """A masking built through an unmasked intermediate t = (a0^a1)&(b0^b1).

    Outputs (t ^ r, r) are individually uniform, but the intermediate t is the
    secret product and is a first-order violation. The mistake this fixture
    shows is recombining shares into the clear inside the circuit.
    """
    c = Circuit()
    a0 = c.add_input("a0")  # shares of secret a
    a1 = c.add_input("a1")
    b0 = c.add_input("b0")  # shares of secret b
    b1 = c.add_input("b1")
    r = c.add_input("r")  # random bit used to mask the final product
    x = c.add_gate("xor", a0, a1)  # = secret a
    y = c.add_gate("xor", b0, b1)  # = secret b
    t = c.add_gate("and", x, y)  # = a & b  (unmasked!)
    c.outputs = [c.add_gate("xor", t, r), r]
    return c


# Configuration for the fixtures above. A "secret group" names which inputs are the
# shares of which secret; the FIRST share of each secret and every fresh random
# are the "free" uniform bits that the checker enumerates.
SECRET_GROUPS_AND = {"a": ["a0", "a1"], "b": ["b0", "b1"]}  # for the AND fixtures
FREE_AND = ["a0", "b0", "r"]  # free bits there: first share of a, of b, and r
SECRET_GROUPS_BUF = {"a": ["a0", "a1"]}  # for the single-secret buffer fixture
FREE_BUF = ["a0", "r"]  # free bits there: first share of a, and r
