"""Executable witnesses for the claims in docs/theory.md (design/0018).

Each test is named after the claim it witnesses (C1..C8). A witness is a
concrete instance or a randomised property check -- evidence that the claim
is stated correctly, not a proof. The proofs are in docs/theory.md.

Purpose
-------
`docs/theory.md` states nine claims about masked circuits and e-graphs (for example
"glitch-free safety is a property of a wire's function", "re-sharing is not an equality
of wire terms", "a leaking subterm leaks in every context"). A proof on paper can hide a
mistake in the statement itself, so each claim gets a test that exhibits a concrete
instance or checks it on thousands of random cases. These tests are WITNESSES, not
proofs: passing means the claim is plausibly stated correctly, nothing more. Run with:
    uv run pytest experiments/claims -q
"""

import importlib.util
import itertools
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for sub in ("labeller", "resharing", "glitch_probe", "premise_test", "composition"):
    sys.path.insert(0, str(ROOT / "experiments" / sub))

from extract import Evaluator, kbest  # noqa: E402
from fixtures import FIXTURES  # noqa: E402
from gadgets import GADGETS, lower, secrets_of, value  # noqa: E402
from glitch import GCircuit, check_glitch, check_glitch_free, tables  # noqa: E402
from labeller import TruthSpace, circuit_tables  # noqa: E402
from layer import export, saturate  # noqa: E402
from masked import Circuit, check_first_order  # noqa: E402
from probe import fixtures as glitch_fixtures  # noqa: E402
from probe import free_of, to_circuit  # noqa: E402

A, B, D = ("in", "a"), ("in", "b"), ("in", "d")  # secret input terms
Z = ("xor", A, B)  # a share-wise XOR of a and b
SEC = {"a": ["a0", "a1"], "b": ["b0", "b1"]}  # secret groups for the wire circuits


def leaks(term):
    """True iff the term's lowered circuit has at least one leaking wire."""
    return bool(Evaluator()(term)[1])


def random_wire_circuit(rng, n_gates, n_regs=0):
    """Random circuit (inputs a0..b1, r1, r2) with `n_gates` gates and some registers.

    Each step adds, with probability 0.3 while registers remain, a register on a
    random wire; otherwise a random AND or XOR of two random wires. The last wire is
    the output.
    """
    c = GCircuit()
    pool = [c.add_input(n) for n in ("a0", "a1", "b0", "b1", "r1", "r2")]
    for _ in range(n_gates):
        if n_regs and rng.random() < 0.3:  # 30% chance while registers remain
            pool.append(c.add_reg(rng.choice(pool)))
            n_regs -= 1
        else:
            op = rng.choice(("and", "xor"))
            pool.append(c.add_gate(op, rng.choice(pool), rng.choice(pool)))
    c.outputs = [pool[-1]]
    return c


def random_value_term(rng, depth, leaves=(A, B, D)):
    """Random value-layer term of height at most `depth` (xor, refresh, any gadget).

    With depth 0 (or probability 0.25) return a random leaf; otherwise pick an operator.
    `refresh` wraps one subterm; `xor` and the AND gadgets combine two.
    """
    if depth == 0 or rng.random() < 0.25:
        return rng.choice(leaves)
    op = rng.choice(("xor", "refresh", *GADGETS))
    if op == "refresh":
        return ("refresh", random_value_term(rng, depth - 1, leaves))
    return (
        op,
        random_value_term(rng, depth - 1, leaves),
        random_value_term(rng, depth - 1, leaves),
    )


# ---- C1: glitch-free safety is a property of a wire's function ----------------


def test_c1_glitch_free_safety_depends_only_on_the_function():
    """Two wires with the same truth table always get the same verdict.

    Algorithm: over 400 random circuits, record the safety verdict of every wire keyed
    by its truth table (the function it computes). `setdefault` stores the first verdict
    seen for a table; if a later wire with the same table had a different verdict the
    assertion fails. This is why one safe/unsafe label per wire-level e-class works.
    """
    rng = random.Random(1)  # fixed seed: reproducible circuits
    space = TruthSpace(SEC, ["a0", "b0", "r1", "r2"])
    verdict_of = {}  # truth table -> the verdict first seen for it
    for _ in range(400):
        c = random_wire_circuit(rng, rng.randint(1, 7))
        for name, table in circuit_tables(c, space).items():
            safe = space.is_safe(table)
            assert verdict_of.setdefault(table, safe) == safe, name


# ---- C2: unconstrained, cost-minimal extraction is unsound --------------------


def test_c2_cost_minimal_extraction_breaks_isw():
    """Cost-only extraction of the ISW e-graph gives a 7-gate circuit that leaks.

    `run.py` is loaded by file path (importlib) so the test does not depend on how the
    module path is configured; the e-graph is saturated with the full rules and the
    cheapest circuit is checked.
    """
    spec = importlib.util.spec_from_file_location(
        "premise_run", ROOT / "experiments" / "premise_test" / "run.py"
    )
    run = importlib.util.module_from_spec(spec)  # an empty module object
    spec.loader.exec_module(run)  # run the file's code inside it
    from egraph import RULES_FULL, extract, materialize
    from egraph import saturate as sat

    eg, c0, c1 = run.build_isw_egraph()
    sat(eg, RULES_FULL)
    best, _ = extract(eg)
    circ = Circuit()
    materialize(eg, best, [c0, c1], circ)
    verdict = check_first_order(circ, SEC, ["a0", "b0", "r"])
    assert circ.gate_count() == 7 and not all(verdict.values())


# ---- C3: re-sharing is not an equality of wire terms ---------------------------


def test_c3_isw_and_dom_differ_per_share_agree_on_value():
    """ISW and DOM give different output SHARES but the same reconstructed VALUE.

    So `isw = dom` is true as secret values but false as wire terms: it cannot be an
    e-graph equality at the wire level.
    """
    space = TruthSpace(SEC, ["a0", "b0", "r1"])
    shares = {}  # gadget name -> [truth table of share 0, of share 1]
    for g in ("isw", "dom"):
        low = lower([(g, A, B)])
        t = circuit_tables(low.circ, space)
        shares[g] = [t[w] for w in low.circ.outputs]
    assert shares["isw"][0] != shares["dom"][0]  # share 0 differs between gadgets
    # share0 ^ share1 (the reconstructed value) is the same for both gadgets
    assert shares["isw"][0] ^ shares["isw"][1] == shares["dom"][0] ^ shares["dom"][1]


def test_c3_refresh_changes_each_share():
    """A refresh changes share 0 but leaves the reconstructed secret unchanged."""
    space = TruthSpace({"a": ["a0", "a1"]}, ["a0", "r1"])
    plain = circuit_tables(lower([A]).circ, space)  # tables of the unrefreshed sharing
    low = lower([("refresh", A)])
    t = circuit_tables(low.circ, space)
    s0, s1 = (t[w] for w in low.circ.outputs)  # the refreshed share tables
    assert s0 != plain["a0"] and s0 ^ s1 == plain["a0"] ^ plain["a1"]


# ---- C4: value equality is a congruence; lowering is correct ------------------


def _envs(names):
    """Yield every assignment of 0/1 to the secrets `names` as a dict."""
    for bits in itertools.product((0, 1), repeat=len(names)):
        yield dict(zip(names, bits, strict=True))


def test_c4_value_equality_is_a_congruence_for_every_operator():
    """If two terms have the same value, swapping one for the other in any operator
    leaves the result's value unchanged (value equality IS a congruence).

    `x2 = refresh(x)` has the same value as `x` but is a different term.
    """
    rng = random.Random(4)
    for _ in range(300):
        x = random_value_term(rng, 3)
        y = random_value_term(rng, 3)
        x2 = ("refresh", x)  # V(x2) = V(x), x2 != x
        for op in ("xor", *GADGETS):
            for env in _envs(["a", "b", "d"]):
                assert value((op, x, y), env) == value((op, x2, y), env)


def test_c4_lowering_reconstructs_the_value():
    """The lowered circuit's two output shares XOR to the term's value, as a table.

    Algorithm: for 60 random terms, lower the term, compute the truth table of
    share0 ^ share1, and build the EXPECTED table by setting, for every secret value
    where `value(term)` is 1, the whole block of that secret assignment to ones. The two
    integers must be equal.
    """
    rng = random.Random(44)
    for _ in range(60):
        t = random_value_term(rng, 2)
        low = lower([t])
        names = secrets_of(t)
        space = TruthSpace(
            {s: [f"{s}0", f"{s}1"] for s in names},
            [f"{s}0" for s in names] + low.randoms,
        )
        tab = circuit_tables(low.circ, space)
        s0, s1 = low.circ.outputs
        recon = tab[s0] ^ tab[s1]  # reconstructed value, as a truth table
        want = 0  # the expected table, built block by block
        for env in _envs(names):
            if value(t, env):
                # set this secret assignment's whole block to ones: a block is
                # `space.block` bits wide and starts at index block_index * block
                want |= ((1 << space.block) - 1) << (
                    _block_index(env, names) * space.block
                )
        assert recon == want, t


def _block_index(env, names):
    """Index of the block belonging to the secret assignment `env`.

    Reads the secrets' values as the bits of a number: the first secret is the lowest
    bit. Example: names ["a", "b"] and env {"a": 1, "b": 0} give index 1.
    """
    return sum(env[s] << i for i, s in enumerate(names))


# ---- C5: at the value layer safety is not class-local; DAG extraction is incomplete


def test_c5_same_class_different_safety():
    """One class, two safety verdicts: `isw(z, z)` leaks, with a refresh it does not."""
    assert leaks(("isw", Z, Z)) and not leaks(("isw", Z, ("refresh", Z)))


def _build_dag(classes, pick, c, stack=frozenset()):
    """Build the term for class `c` when every class uses exactly the node `pick[c]`.

    Returns None if the choice is cyclic (a class reached again on the current path,
    tracked in `stack`). This models ONE-NODE-PER-CLASS extraction.
    """
    if c in stack:
        return None  # cyclic choice
    node = classes[c][pick[c]]  # the single node chosen for this class
    if node[0] == "in":
        return node
    kids = [_build_dag(classes, pick, k, stack | {c}) for k in node[1]]  # children
    if any(k is None for k in kids):
        return None
    return (node[0], *kids)


def _dag_extractions(classes, root):
    """Every acyclic one-node-per-class choice reachable from root, as a term.

    Algorithm: try every combination of one node per class (the Cartesian product of the
    index ranges), build the term, and yield it if it is acyclic.
    """
    order = list(classes)  # a fixed order of the classes
    # `product` over the ranges gives every combination of node indices
    for choice in itertools.product(*(range(len(classes[c])) for c in order)):
        t = _build_dag(classes, dict(zip(order, choice, strict=True)), root)
        if t is not None:
            yield t


def test_c5_no_secure_dag_extraction_of_square_but_a_term_extraction_exists():
    """For the square, every one-node-per-class extraction leaks; terms work."""
    eg, _ = saturate(FIXTURES["square"], ("R3",), 6)
    classes, root = export(eg)
    dags = set(_dag_extractions(classes, root))
    assert dags and all(leaks(t) for t in dags)  # here: exactly one, isw(z, z)
    best, _ = kbest(classes, root, secure=True)  # per-occurrence term extraction
    assert best is not None and not leaks(best[1])


def _pick_for(classes, c, term, pick):
    """Extend `pick` so class `c` extracts to `term`, one node per class; or None."""
    for i, node in enumerate(classes[c]):
        if c in pick and pick[c] != i:
            continue
        if node[0] == "in":
            if term == node:
                return {**pick, c: i}
            continue
        if term[0] != node[0] or len(term) - 1 != len(node[1]):
            continue
        trial = {**pick, c: i}
        for kid, sub in zip(node[1], term[1:], strict=True):
            trial = _pick_for(classes, kid, sub, trial)
            if trial is None:
                break
        if trial is not None:
            return trial
    return None


SQUARE_DAG_SECURE = ("xor", ("isw", A, Z), ("isw", B, Z))


def test_c5b_is_specific_to_r3_alone():
    """C5(b) does not generalise: with R1 + R3 (no self-refreshing gadget) a
    secure one-node-per-class extraction of `square` exists.

    a&(a^b) ^ b&(a^b) = a ^ (a&b) ^ (a&b) ^ b = a ^ b, the square of z = a ^ b,
    reached by distributivity; each gadget's operands are independent sharings.
    VerifMSI agreement: test_c5b_counterexample_agrees_with_verifmsi.
    """
    eg, _ = saturate(FIXTURES["square"], ("R1", "R3"), 6)
    classes, root = export(eg)
    pick = _pick_for(classes, root, SQUARE_DAG_SECURE, {})
    assert pick is not None  # expressible with one node per class
    full = {c: pick.get(c, 0) for c in classes}
    assert _build_dag(classes, full, root) == SQUARE_DAG_SECURE  # and acyclic
    assert not leaks(SQUARE_DAG_SECURE)


def test_c5b_counterexample_agrees_with_verifmsi():
    crosscheck = pytest.importorskip("crosscheck")
    if not crosscheck.oracle_available():
        pytest.skip("VerifMSI oracle not installed")
    from gadgets import secret_groups

    low = lower([SQUARE_DAG_SECURE])
    out = crosscheck.compare(
        low.circ, secret_groups(secrets_of(SQUARE_DAG_SECURE)), low.randoms
    )
    assert out["violations"] == []
    assert all(v["independent"] for v in out["oracle"].values())


# ---- C6: glitch-extended safety is not a function of the wire -----------------


def test_c6_glitch_safety_is_not_function_determined():
    """Registered and unregistered DOM compute the SAME functions with DIFFERENT safety.

    Algorithm: build both circuits, check that each output computes the same truth table
    in both, then check the registered one is glitch-secure and the unregistered is not.
    So glitch-extended safety cannot be a label on the function (unlike C1).
    """
    fx = glitch_fixtures()
    reg_roots, secrets, _ = fx["dom (registered)"]
    raw_roots, _, randoms = fx["dom (no registers)"]
    reg_c, raw_c = to_circuit(reg_roots), to_circuit(raw_roots)
    free = free_of(secrets, randoms)
    space = TruthSpace(secrets, free)
    for i in range(2):  # both output shares
        same_function = (
            tables(reg_c, space)[reg_c.outputs[i]]
            == tables(raw_c, space)[raw_c.outputs[i]]
        )
        assert same_function
    g_reg = check_glitch(reg_c, secrets, free)
    g_raw = check_glitch(raw_c, secrets, free)
    assert all(g_reg[o] for o in reg_c.outputs)  # registered: glitch-secure
    assert not all(g_raw[o] for o in raw_c.outputs)  # unregistered: leaks


# ---- C7: a leaking subterm leaks in every context (the extraction cut) ---------


def test_c7_value_layer_leak_is_monotone_in_context():
    """Wrapping a leaking subterm in more logic never removes the leak.

    This justifies cutting leaking terms during extraction: any term containing a
    leaking subterm leaks, so it never needs to be considered.
    """
    rng = random.Random(7)
    inner = ("isw", Z, Z)  # a known leaking subterm
    for _ in range(80):
        t = inner
        for _ in range(rng.randint(1, 3)):  # wrap it in 1 to 3 random contexts
            other = random_value_term(rng, 1, leaves=(A, B, D))
            op = rng.choice(("xor", "refresh", *GADGETS))
            if op == "refresh":
                t = ("refresh", t)
            elif rng.random() < 0.5:
                t = (op, t, other)  # the leaking term as the first operand
            else:
                t = (op, other, t)  # ... or as the second
        assert leaks(t), t


def test_c7_glitch_leak_is_monotone_in_context():
    """The same property with glitches: adding gates never hides a leaking probe."""
    rng = random.Random(77)
    free = free_of(SEC, ["r1", "r2"])
    found = 0  # how many circuits actually had a leaking probe to track
    for _ in range(300):
        c = random_wire_circuit(rng, rng.randint(2, 6), 2)
        g = check_glitch(c, SEC, free)
        bad = [w for w, ok in g.items() if not ok]  # the leaking probes
        if not bad:
            continue
        found += 1
        pool = [w for w, _, _ in c.wires]
        for _ in range(rng.randint(1, 4)):  # grow a context
            op = rng.choice(("and", "xor", "reg"))
            if op == "reg":
                pool.append(c.add_reg(rng.choice(pool)))
            else:
                pool.append(c.add_gate(op, rng.choice(pool), rng.choice(pool)))
        g2 = check_glitch(c, SEC, free)  # re-check after adding the context
        assert all(not g2[w] for w in bad)  # every earlier leaking probe still leaks
    assert found > 20  # the test must not be vacuous


# ---- C8: at first order, outputs can be extracted separately -------------------


def _cone(c, root):
    """The sub-circuit made of `root` and everything it depends on.

    Algorithm: walk back from `root` through the operands of every and/xor/reg wire,
    collecting the names reached (the "cone"); then copy those wires, in their original
    order, into a new circuit whose only output is `root`.
    """
    keep, stack = set(), [root]  # keep: wires in the cone; stack: wires still to visit
    by_name = {n: (op, a) for n, op, a in c.wires}  # wire name -> (op, args)
    while stack:
        w = stack.pop()
        if w in keep:
            continue  # already visited
        keep.add(w)
        op, a = by_name[w]
        if op in ("and", "xor", "reg"):
            stack.extend(a)  # visit its operands too
    sub = GCircuit()
    for n, op, a in c.wires:
        if n in keep:
            sub._add(n, op, a)  # copy the wire, preserving the order
    sub.outputs = [root]
    return sub


def test_c8_circuit_secure_iff_every_root_cone_secure():
    """A circuit is secure iff each output's own cone is secure, in both models.

    So at first order each output can be optimised on its own. Checked on 200 random
    circuits with two random roots, for the glitch-extended and glitch-free checkers.
    """
    rng = random.Random(8)
    free = free_of(SEC, ["r1", "r2"])
    for _ in range(200):
        c = random_wire_circuit(rng, rng.randint(3, 9), rng.randint(0, 2))
        # two random non-input wires to play the role of the outputs
        roots = rng.sample([w for w, op, _ in c.wires if op != "input"], 2)
        for check in (check_glitch, check_glitch_free):
            in_cones = set()  # all wires lying in some root's cone
            for r in roots:
                in_cones |= {n for n, _, _ in _cone(c, r).wires}
            verdict = check(c, SEC, free)  # verdicts on the whole circuit
            whole = all(verdict[w] for w in in_cones)  # safe on the union of cones?
            # safe when each cone is checked as its own small circuit?
            parts = all(all(check(_cone(c, r), SEC, free).values()) for r in roots)
            assert whole == parts


# ---- C9: for PINI-built terms, safety is class-local again ---------------------


def test_c9_pini_restricted_dag_extraction_is_secure():
    """One-node-per-class extraction over PINI gadgets is secure on the square."""
    from analysis import composable_classes, extract_composable

    eg, _ = saturate(FIXTURES["square"], ("R2", "R3"), 6)
    classes, root = export(eg)
    assert root in composable_classes(classes)
    term = extract_composable(classes, root)  # one node per class, PINI nodes
    assert term[0] == "hpc1" and term[1] == term[2]  # same sharing, both operands
    assert not leaks(term)


def test_c9_random_pini_terms_with_fan_out_are_secure():
    """Random PINI-only terms, with one subterm reused several times, never leak.

    The `shared` subterm is deliberately used in several places (fan-out); PINI
    composition says that is fine. Terms containing ISW or DOM are skipped (not PINI).
    """
    rng = random.Random(9)
    pini_ops = ("xor", "not", "refresh", "hpc1")
    for _ in range(80):
        shared = random_value_term(rng, 1, leaves=(A, B))  # the reused subterm
        t = shared
        for _ in range(rng.randint(1, 3)):
            op = rng.choice(pini_ops)
            if op in ("not", "refresh"):
                t = (op, t)
            else:
                t = (op, t, rng.choice((shared, D, t)))  # fan-out of `shared`
        # skip terms where random_value_term happened to produce a non-PINI gadget
        if any(g in repr(t) for g in ("isw", "dom")):
            continue
        assert not leaks(t), t
