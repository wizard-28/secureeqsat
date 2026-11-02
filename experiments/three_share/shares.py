"""Does Finding 1 survive with more than two shares?  (d = 2, 3, 4)

Question
--------
At two shares every gate-saving factoring of the ISW gadget puts a secret back
together (`b0 ^ b1 = b`). With d >= 3 shares, `b0 ^ b1` is no longer the secret, so
some factorings may be both cheaper AND secure. This script measures that.

    uv run python experiments/three_share/shares.py

Method
------
This is NOT an e-graph. The Boolean rewrites of Finding 1 (reassociation,
commutation, factoring) act on a flat XOR of "leaves", so their closure is
enumerable directly:

  * The d-share ISW AND has output share c_i = a_i b_i ^ XOR_{j!=i} z_ij with
    z_ij = r_ij (i<j) and z_ji = (r_ij ^ a_i b_j) ^ a_j b_i. Every c_i is therefore
    a flat XOR of products a_x b_y and fresh bits r_ij.
  * A *plan* for one output partitions its products into blocks. A block is a lone
    product, or a set of >= 2 products with the same a-index (factored as
    a_x (b_y ^ b_w ^ ...)) or the same b-index. This is the factoring rule.
  * A plan's cost is (#blocks) ANDs + XORs inside blocks + (#atoms - 1) XORs
    combining the atoms (blocks and randoms). Every binary XOR tree over the atoms
    has the same cost, so reassociation changes security but not cost.
  * First-order glitch-free security of a wire depends only on the function it
    computes (design/0006), so a wire is checked once from its truth table.
    Secure iff every block-internal XOR, every atom and every tree node is safe.
    Existence of a fully safe tree is a subset DP.

Limits (also in RESULTS.md): in-house checker only, NOT cross-checked against
VerifMSI (not installed here); first order only; per-output costs are summed, so
XORs shareable between outputs are counted once per output (an upper bound on cost);
only ISW structure is explored, not DOM/HPC or refresh insertion.
"""

import itertools
import sys


class Gadget:
    """The d-share ISW AND, with every wire function as a bit-vector over all points."""

    def __init__(self, d):
        self.d = d
        self.pairs = [(i, j) for i in range(d) for j in range(i + 1, d)]
        # free bits: shares 0..d-2 of a and b, and one random per pair
        self.free = (
            [f"a{i}" for i in range(d - 1)]
            + [f"b{i}" for i in range(d - 1)]
            + [f"r{i}{j}" for i, j in self.pairs]
        )
        n = len(self.free)
        self.npts = 4 << n  # (a, b) secrets x free assignments
        # truth-table bit-vectors: bit p of fn[x] = value of x at point p
        var = {}
        a_sec = b_sec = 0
        for p in range(self.npts):
            s = p >> n
            a_sec |= (s & 1) << p
            b_sec |= ((s >> 1) & 1) << p
        cols = {name: 0 for name in self.free}
        for p in range(self.npts):
            f = p & ((1 << n) - 1)
            for k, name in enumerate(self.free):
                cols[name] |= ((f >> k) & 1) << p
        var.update(cols)
        for who, sec in (("a", a_sec), ("b", b_sec)):
            last = sec
            for i in range(d - 1):
                last ^= var[f"{who}{i}"]
            var[f"{who}{d - 1}"] = last
        self.var = var
        self.ab = {
            (x, y): var[f"a{x}"] & var[f"b{y}"] for x in range(d) for y in range(d)
        }
        self.rand = {(i, j): var[f"r{i}{j}"] for i, j in self.pairs}

    def safe(self, fn):
        """True iff the number of 1s of fn is equal for the 4 secret assignments."""
        n = len(self.free)
        block = 1 << n
        counts = [
            bin((fn >> (s * block)) & ((1 << block) - 1)).count("1") for s in range(4)
        ]
        return len(set(counts)) == 1

    def leaves(self, i):
        """Leaves of output share i: ('p', x, y) products and ('r', i, j) randoms."""
        d = self.d
        out = [("p", i, i)]
        for j in range(d):
            if j == i:
                continue
            lo, hi = min(i, j), max(i, j)
            out.append(("r", lo, hi))
            if j < i:  # z_ij with i > j also carries both cross products
                out += [("p", j, i), ("p", i, j)]
        return out

    def fn(self, leaf):
        return self.ab[leaf[1:]] if leaf[0] == "p" else self.rand[leaf[1:]]


def blocks_of(products):
    """All partitions of `products` into singletons / same-a / same-b factor blocks."""
    products = list(products)
    if not products:
        yield []
        return
    first, rest = products[0], products[1:]
    yield from ([[first]] + p for p in blocks_of(rest))
    for size in range(1, len(rest) + 1):
        for comb in itertools.combinations(rest, size):
            grp = [first, *comb]
            if len({p[1] for p in grp}) == 1 or len({p[2] for p in grp}) == 1:
                rem = [p for p in rest if p not in comb]
                yield from ([grp] + p for p in blocks_of(rem))


def analyse_output(g, i):
    """For output share i: min cost over all plans, and min cost over secure plans.

    Returns a dict with the cheapest unconstrained cost, the cheapest cost among
    plans for which SOME XOR tree is fully safe, whether every cheapest-cost plan is
    forced to contain a leaking wire, and the plan counts.
    """
    lv = g.leaves(i)
    prods = [x for x in lv if x[0] == "p"]
    rands = [x for x in lv if x[0] == "r"]
    best_any = None
    best_sec = None
    n_plans = n_secure = 0
    cheapest_plans = []
    for part in blocks_of(prods):
        n_plans += 1
        atoms = []
        atoms_ok = True
        extra_xor = 0
        for blk in part:
            if len(blk) == 1:
                atoms.append(g.fn(blk[0]))
                continue
            same_a = len({p[1] for p in blk}) == 1
            if same_a:
                shared = blk[0][1]
                others = sorted(p[2] for p in blk)
                side = "b"
            else:
                shared = blk[0][2]
                others = sorted(p[1] for p in blk)
                side = "a"
            acc = g.var[f"{side}{others[0]}"]
            for o in others[1:]:
                acc ^= g.var[f"{side}{o}"]
                extra_xor += 1
                atoms_ok = atoms_ok and g.safe(acc)  # each chain prefix is a wire
            lone = g.var[f"{'a' if same_a else 'b'}{shared}"]
            atoms.append(lone & acc)
        atoms += [g.fn(r) for r in rands]
        cost = len(part) + extra_xor + (len(atoms) - 1)
        # NB: AND count = number of blocks; XORs = extra_xor + combining XORs
        ok = atoms_ok and all(g.safe(a) for a in atoms) and tree_exists(g, atoms)
        if ok:
            n_secure += 1
        if best_any is None or cost < best_any:
            best_any, cheapest_plans = cost, []
        if cost == best_any:
            cheapest_plans.append(ok)
        if ok and (best_sec is None or cost < best_sec):
            best_sec = cost
    return {
        "min_any": best_any,
        "min_secure": best_sec,
        "plans": n_plans,
        "secure_plans": n_secure,
        "cheapest_all_leak": not any(cheapest_plans),
    }


def tree_exists(g, atoms):
    """Is there a binary XOR tree over `atoms` with every internal node safe?"""
    n = len(atoms)
    if n > 12:
        raise ValueError("too many atoms")
    fn = [0] * (1 << n)
    for m in range(1, 1 << n):
        low = (m & -m).bit_length() - 1
        fn[m] = fn[m & (m - 1)] ^ atoms[low]
    ok = [False] * (1 << n)
    for m in range(1, 1 << n):
        if m & (m - 1) == 0:
            ok[m] = g.safe(fn[m])
            continue
        if not g.safe(fn[m]):
            continue
        sub = (m - 1) & m
        while sub:
            if ok[sub] and ok[m ^ sub]:
                ok[m] = True
                break
            sub = (sub - 1) & m
    return ok[(1 << n) - 1]


def find_tree(g, atoms):
    """Like `tree_exists`, but return a nested-tuple XOR tree over atom indices."""
    n = len(atoms)
    fn = [0] * (1 << n)
    for m in range(1, 1 << n):
        low = (m & -m).bit_length() - 1
        fn[m] = fn[m & (m - 1)] ^ atoms[low]
    tree = [None] * (1 << n)
    for m in range(1, 1 << n):
        if m & (m - 1) == 0:
            tree[m] = (m.bit_length() - 1,) if g.safe(fn[m]) else None
            continue
        if not g.safe(fn[m]):
            continue
        sub = (m - 1) & m
        while sub:
            if tree[sub] and tree[m ^ sub]:
                tree[m] = (tree[sub], tree[m ^ sub])
                break
            sub = (sub - 1) & m
    return tree[(1 << n) - 1]


def _plan_atoms(g, part, rands):
    """Atom truth tables and the circuit recipe for each atom of a plan."""
    atoms, recipe, atoms_ok = [], [], True
    for blk in part:
        if len(blk) == 1:
            atoms.append(g.fn(blk[0]))
            recipe.append(("and", f"a{blk[0][1]}", f"b{blk[0][2]}"))
            continue
        same_a = len({p[1] for p in blk}) == 1
        if same_a:
            lone, others, side = f"a{blk[0][1]}", sorted(p[2] for p in blk), "b"
        else:
            lone, others, side = f"b{blk[0][2]}", sorted(p[1] for p in blk), "a"
        names = [f"{side}{o}" for o in others]
        acc = g.var[names[0]]
        for nm in names[1:]:
            acc ^= g.var[nm]
            atoms_ok = atoms_ok and g.safe(acc)
        atoms.append(g.var[lone] & acc)
        recipe.append(("fact", lone, names))
    for r in rands:
        atoms.append(g.fn(r))
        recipe.append(("rand", f"r{r[1]}{r[2]}"))
    return atoms, recipe, atoms_ok


def build_circuit(d, kind):
    """A real `Circuit` for the d-share ISW AND, from the cheapest plan of each output.

    kind = "secure": cheapest plan that has a fully safe XOR tree (cost-constrained).
    kind = "any":    cheapest plan overall, preferring one with NO safe tree, i.e. the
                     circuit a cost-only optimiser may return (it cannot tell).
    Returns (circuit, secrets, randoms) ready for the oracle cross-check.
    """
    import masked  # noqa: PLC0415 - path set by the caller (premise_test)

    g = Gadget(d)
    c = masked.Circuit()
    for x in "ab":
        for i in range(d):
            c.add_input(f"{x}{i}")
    randoms = [f"r{i}{j}" for i, j in g.pairs]
    for r in randoms:
        c.add_input(r)
    for i in range(d):
        lv = g.leaves(i)
        prods = [x for x in lv if x[0] == "p"]
        rands = [x for x in lv if x[0] == "r"]
        best = None
        for part in blocks_of(prods):
            atoms, recipe, atoms_ok = _plan_atoms(g, part, rands)
            extra = sum(len(r[2]) - 1 for r in recipe if r[0] == "fact")
            cost = len(part) + extra + len(atoms) - 1
            tree = find_tree(g, atoms) if atoms_ok else None
            if kind == "secure" and tree is None:
                continue
            key = (cost, tree is not None) if kind == "any" else (cost, False)
            if best is None or key < best[0]:
                best = (key, recipe, tree, len(atoms))
        _, recipe, tree, n = best
        wires = []
        for r in recipe:
            if r[0] == "and":
                wires.append(c.add_gate("and", r[1], r[2]))
            elif r[0] == "rand":
                wires.append(r[1])
            else:
                acc = r[2][0]
                for nm in r[2][1:]:
                    acc = c.add_gate("xor", acc, nm)
                wires.append(c.add_gate("and", r[1], acc))

        def emit(t, wires=wires):
            if len(t) == 1:
                return wires[t[0]]
            return c.add_gate("xor", emit(t[0]), emit(t[1]))

        if tree is None:  # cost-only: any association, here a left-to-right chain
            tree = (0,)
            for k in range(1, n):
                tree = (tree, (k,))
        c.outputs.append(emit(tree))
    secrets = {x: [f"{x}{i}" for i in range(d)] for x in "ab"}
    return c, secrets, randoms


def circuit_safety(d, circ):
    """Per-wire verdicts of the in-house truth-table check for a built circuit."""
    g = Gadget(d)
    fn = {}
    for name, op, payload in circ.wires:
        if op == "input":
            fn[name] = g.var[name]
        elif op == "xor":
            fn[name] = fn[payload[0]] ^ fn[payload[1]]
        elif op == "and":
            fn[name] = fn[payload[0]] & fn[payload[1]]
        else:
            raise ValueError(op)
    return {n: g.safe(v) for n, v in fn.items()}


def isw_baseline_cost(d):
    """Gates of the plain d-share ISW: d^2 ANDs + XORs (every leaf chained)."""
    g = Gadget(d)
    total = 0
    for i in range(d):
        lv = g.leaves(i)
        total += sum(1 for x in lv if x[0] == "p") + len(lv) - 1
    return total


def main():
    ds = [int(x) for x in sys.argv[1:]] or [2, 3]
    print("d  baseline  min(any)  min(secure)  outputs: [any/secure, plans, secure]")
    for d in ds:
        g = Gadget(d)
        rows = [analyse_output(g, i) for i in range(d)]
        ba = isw_baseline_cost(d)
        any_ = sum(r["min_any"] for r in rows)
        sec = sum(r["min_secure"] for r in rows)
        detail = "; ".join(
            f"c{i}: {r['min_any']}/{r['min_secure']} ({r['secure_plans']}/{r['plans']})"
            + (" LEAK-forced" if r["cheapest_all_leak"] else "")
            for i, r in enumerate(rows)
        )
        print(f"{d}  {ba:8d}  {any_:8d}  {sec:11d}  {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
