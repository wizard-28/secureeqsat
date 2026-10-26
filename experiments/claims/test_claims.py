"""Executable witnesses for the claims in docs/theory.md (design/0018).

Each test is named after the claim it witnesses (C1..C8). A witness is a
concrete instance or a randomised property check -- evidence that the claim
is stated correctly, not a proof. The proofs are in docs/theory.md.
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

A, B, D = ("in", "a"), ("in", "b"), ("in", "d")
Z = ("xor", A, B)
SEC = {"a": ["a0", "a1"], "b": ["b0", "b1"]}


def leaks(term):
    return bool(Evaluator()(term)[1])


def random_wire_circuit(rng, n_gates, n_regs=0):
    c = GCircuit()
    pool = [c.add_input(n) for n in ("a0", "a1", "b0", "b1", "r1", "r2")]
    for _ in range(n_gates):
        if n_regs and rng.random() < 0.3:
            pool.append(c.add_reg(rng.choice(pool)))
            n_regs -= 1
        else:
            op = rng.choice(("and", "xor"))
            pool.append(c.add_gate(op, rng.choice(pool), rng.choice(pool)))
    c.outputs = [pool[-1]]
    return c


def random_value_term(rng, depth, leaves=(A, B, D)):
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
    rng = random.Random(1)
    space = TruthSpace(SEC, ["a0", "b0", "r1", "r2"])
    verdict_of = {}
    for _ in range(400):
        c = random_wire_circuit(rng, rng.randint(1, 7))
        for name, table in circuit_tables(c, space).items():
            safe = space.is_safe(table)
            assert verdict_of.setdefault(table, safe) == safe, name


# ---- C2: unconstrained, cost-minimal extraction is unsound --------------------


def test_c2_cost_minimal_extraction_breaks_isw():
    spec = importlib.util.spec_from_file_location(
        "premise_run", ROOT / "experiments" / "premise_test" / "run.py"
    )
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
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
    space = TruthSpace(SEC, ["a0", "b0", "r1"])
    shares = {}
    for g in ("isw", "dom"):
        low = lower([(g, A, B)])
        t = circuit_tables(low.circ, space)
        shares[g] = [t[w] for w in low.circ.outputs]
    assert shares["isw"][0] != shares["dom"][0]
    assert shares["isw"][0] ^ shares["isw"][1] == shares["dom"][0] ^ shares["dom"][1]


def test_c3_refresh_changes_each_share():
    space = TruthSpace({"a": ["a0", "a1"]}, ["a0", "r1"])
    plain = circuit_tables(lower([A]).circ, space)
    low = lower([("refresh", A)])
    t = circuit_tables(low.circ, space)
    s0, s1 = (t[w] for w in low.circ.outputs)
    assert s0 != plain["a0"] and s0 ^ s1 == plain["a0"] ^ plain["a1"]


# ---- C4: value equality is a congruence; lowering is correct ------------------


def _envs(names):
    for bits in itertools.product((0, 1), repeat=len(names)):
        yield dict(zip(names, bits, strict=True))


def test_c4_value_equality_is_a_congruence_for_every_operator():
    rng = random.Random(4)
    for _ in range(300):
        x = random_value_term(rng, 3)
        y = random_value_term(rng, 3)
        x2 = ("refresh", x)  # V(x2) = V(x), x2 != x
        for op in ("xor", *GADGETS):
            for env in _envs(["a", "b", "d"]):
                assert value((op, x, y), env) == value((op, x2, y), env)


def test_c4_lowering_reconstructs_the_value():
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
        recon = tab[s0] ^ tab[s1]
        want = 0
        for env in _envs(names):
            if value(t, env):
                want |= ((1 << space.block) - 1) << (
                    _block_index(env, names) * space.block
                )
        assert recon == want, t


def _block_index(env, names):
    return sum(env[s] << i for i, s in enumerate(names))


# ---- C5: at the value layer safety is not class-local; DAG extraction is incomplete


def test_c5_same_class_different_safety():
    assert leaks(("isw", Z, Z)) and not leaks(("isw", Z, ("refresh", Z)))


def _build_dag(classes, pick, c, stack=frozenset()):
    if c in stack:
        return None  # cyclic choice
    node = classes[c][pick[c]]
    if node[0] == "in":
        return node
    kids = [_build_dag(classes, pick, k, stack | {c}) for k in node[1]]
    if any(k is None for k in kids):
        return None
    return (node[0], *kids)


def _dag_extractions(classes, root):
    """Every acyclic one-node-per-class choice reachable from root, as a term."""
    order = list(classes)
    for choice in itertools.product(*(range(len(classes[c])) for c in order)):
        t = _build_dag(classes, dict(zip(order, choice, strict=True)), root)
        if t is not None:
            yield t


def test_c5_no_secure_dag_extraction_of_square_but_a_term_extraction_exists():
    eg, _ = saturate(FIXTURES["square"], ("R3",), 6)
    classes, root = export(eg)
    dags = set(_dag_extractions(classes, root))
    assert dags and all(leaks(t) for t in dags)  # here: exactly one, isw(z, z)
    best, _ = kbest(classes, root, secure=True)
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
    fx = glitch_fixtures()
    reg_roots, secrets, _ = fx["dom (registered)"]
    raw_roots, _, randoms = fx["dom (no registers)"]
    reg_c, raw_c = to_circuit(reg_roots), to_circuit(raw_roots)
    free = free_of(secrets, randoms)
    space = TruthSpace(secrets, free)
    for i in range(2):
        same_function = (
            tables(reg_c, space)[reg_c.outputs[i]]
            == tables(raw_c, space)[raw_c.outputs[i]]
        )
        assert same_function
    g_reg = check_glitch(reg_c, secrets, free)
    g_raw = check_glitch(raw_c, secrets, free)
    assert all(g_reg[o] for o in reg_c.outputs)
    assert not all(g_raw[o] for o in raw_c.outputs)


# ---- C7: a leaking subterm leaks in every context (the extraction cut) ---------


def test_c7_value_layer_leak_is_monotone_in_context():
    rng = random.Random(7)
    inner = ("isw", Z, Z)
    for _ in range(80):
        t = inner
        for _ in range(rng.randint(1, 3)):
            other = random_value_term(rng, 1, leaves=(A, B, D))
            op = rng.choice(("xor", "refresh", *GADGETS))
            if op == "refresh":
                t = ("refresh", t)
            elif rng.random() < 0.5:
                t = (op, t, other)
            else:
                t = (op, other, t)
        assert leaks(t), t


def test_c7_glitch_leak_is_monotone_in_context():
    rng = random.Random(77)
    free = free_of(SEC, ["r1", "r2"])
    found = 0
    for _ in range(300):
        c = random_wire_circuit(rng, rng.randint(2, 6), 2)
        g = check_glitch(c, SEC, free)
        bad = [w for w, ok in g.items() if not ok]
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
        g2 = check_glitch(c, SEC, free)
        assert all(not g2[w] for w in bad)
    assert found > 20


# ---- C8: at first order, outputs can be extracted separately -------------------


def _cone(c, root):
    keep, stack = set(), [root]
    by_name = {n: (op, a) for n, op, a in c.wires}
    while stack:
        w = stack.pop()
        if w in keep:
            continue
        keep.add(w)
        op, a = by_name[w]
        if op in ("and", "xor", "reg"):
            stack.extend(a)
    sub = GCircuit()
    for n, op, a in c.wires:
        if n in keep:
            sub._add(n, op, a)
    sub.outputs = [root]
    return sub


def test_c8_circuit_secure_iff_every_root_cone_secure():
    rng = random.Random(8)
    free = free_of(SEC, ["r1", "r2"])
    for _ in range(200):
        c = random_wire_circuit(rng, rng.randint(3, 9), rng.randint(0, 2))
        roots = rng.sample([w for w, op, _ in c.wires if op != "input"], 2)
        for check in (check_glitch, check_glitch_free):
            in_cones = set()
            for r in roots:
                in_cones |= {n for n, _, _ in _cone(c, r).wires}
            verdict = check(c, SEC, free)
            whole = all(verdict[w] for w in in_cones)
            parts = all(all(check(_cone(c, r), SEC, free).values()) for r in roots)
            assert whole == parts


# ---- C9: for PINI-built terms, safety is class-local again ---------------------


def test_c9_pini_restricted_dag_extraction_is_secure():
    from analysis import composable_classes, extract_composable

    eg, _ = saturate(FIXTURES["square"], ("R2", "R3"), 6)
    classes, root = export(eg)
    assert root in composable_classes(classes)
    term = extract_composable(classes, root)  # one node per class, PINI nodes
    assert term[0] == "hpc1" and term[1] == term[2]  # same sharing, both operands
    assert not leaks(term)


def test_c9_random_pini_terms_with_fan_out_are_secure():
    rng = random.Random(9)
    pini_ops = ("xor", "not", "refresh", "hpc1")
    for _ in range(80):
        shared = random_value_term(rng, 1, leaves=(A, B))
        t = shared
        for _ in range(rng.randint(1, 3)):
            op = rng.choice(pini_ops)
            if op in ("not", "refresh"):
                t = (op, t)
            else:
                t = (op, t, rng.choice((shared, D, t)))  # fan-out of `shared`
        if any(g in repr(t) for g in ("isw", "dom")):
            continue
        assert not leaks(t), t
