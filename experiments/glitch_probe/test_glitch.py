"""Tests for the glitch feasibility probe (design/0017)."""

import itertools
import random
import sys
from collections import Counter
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from gextract import export, kbest, term_circuit  # noqa: E402
from glitch import GCircuit, check_glitch, check_glitch_free, stable_sets  # noqa: E402
from probe import (  # noqa: E402
    ORACLE_PY,
    crosscheck,
    fixtures,
    free_of,
    parse,
    saturate,
    to_circuit,
    verdict,
)

FIX = fixtures()


def brute_force_glitch(circ, secrets, randoms):
    """Independent reference: enumerate assignments, compare joint distributions."""
    free = free_of(secrets, randoms)
    sets = stable_sets(circ)
    per_secret = []
    for svals in itertools.product((0, 1), repeat=len(secrets)):
        env_s = dict(zip(secrets, svals, strict=True))
        dists = {w: Counter() for w, _, _ in circ.wires}
        for fvals in itertools.product((0, 1), repeat=len(free)):
            val = dict(zip(free, fvals, strict=True))
            for s, (sh0, sh1) in secrets.items():
                val[sh1] = val[sh0] ^ env_s[s]
            for name, op, args in circ.wires:
                if op == "input":
                    continue
                if op == "const":
                    val[name] = args
                elif op == "reg":
                    val[name] = val[args[0]]
                elif op == "xor":
                    val[name] = val[args[0]] ^ val[args[1]]
                else:
                    val[name] = val[args[0]] & val[args[1]]
            for w in dists:
                dists[w][tuple(val[x] for x in sorted(sets[w]))] += 1
        per_secret.append(dists)
    return {w: all(d[w] == per_secret[0][w] for d in per_secret) for w in per_secret[0]}


def random_circuit(rng, n_gates, n_regs):
    c = GCircuit()
    pool = [c.add_input(n) for n in ("a0", "a1", "b0", "b1", "r1", "r2")]
    for _ in range(n_gates):
        if n_regs and rng.random() < 0.25:
            pool.append(c.add_reg(rng.choice(pool)))
            n_regs -= 1
        else:
            op = rng.choice(("and", "xor"))
            pool.append(c.add_gate(op, rng.choice(pool), rng.choice(pool)))
    return c


SEC = {"a": ["a0", "a1"], "b": ["b0", "b1"]}


def test_checker_matches_brute_force_on_random_circuits():
    rng = random.Random(7)
    for _ in range(150):
        c = random_circuit(rng, rng.randint(3, 10), rng.randint(0, 3))
        ours = check_glitch(c, SEC, free_of(SEC, ["r1", "r2"]))
        assert ours == brute_force_glitch(c, SEC, ["r1", "r2"])


@pytest.mark.parametrize("name", sorted(FIX))
def test_checker_matches_brute_force_on_fixtures(name):
    roots, secrets, randoms = FIX[name]
    c = to_circuit(roots)
    assert check_glitch(c, secrets, free_of(secrets, randoms)) == brute_force_glitch(
        c, secrets, randoms
    )


def test_known_verdicts():
    def leaks(name):
        roots, secrets, randoms = FIX[name]
        return verdict(to_circuit(roots), secrets, randoms)  # (glitch, glitch-free)

    assert leaks("isw (no registers)") == (True, False)
    assert leaks("dom (no registers)") == (True, False)
    assert leaks("dom (registered)") == (False, False)
    assert leaks("dom chain (registered)") == (False, False)


def test_glitch_implies_glitch_free():
    rng = random.Random(11)
    free = free_of(SEC, ["r1", "r2"])
    for _ in range(100):
        c = random_circuit(rng, 8, 2)
        g, f = check_glitch(c, SEC, free), check_glitch_free(c, SEC, free)
        assert all(f[w] for w in g if g[w])


def _extract(name, mode):
    roots, secrets, randoms = FIX[name]
    eg, hs = saturate(roots, mode)
    classes, rts = export(eg, [f"o{i}" for i in range(len(hs))])
    free = free_of(secrets, randoms)
    picks = [kbest(classes, rts[f"o{i}"], secrets, free)[0] for i in range(len(hs))]
    return picks, secrets, randoms


def test_opaque_registers_block_rewriting():
    roots, secrets, randoms = FIX["dom (registered)"]
    eg, hs = saturate(roots, "opaque")
    best = to_circuit([parse(str(eg.extract(h))) for h in hs])
    assert best.count("reg") == 2 and verdict(best, secrets, randoms) == (False, False)


def test_transparent_registers_make_extraction_drop_them():
    roots, secrets, randoms = FIX["dom (registered)"]
    eg, hs = saturate(roots, "transparent")
    best = to_circuit([parse(str(eg.extract(h))) for h in hs])
    assert best.count("reg") == 0 and verdict(best, secrets, randoms)[0]


@pytest.mark.parametrize("name", ["isw (no registers)", "dom (no registers)"])
def test_register_insertion_repairs_unregistered_gadgets(name):
    picks, secrets, randoms = _extract(name, "transparent")
    c = term_circuit([p[1] for p in picks])
    assert c.count("reg") == 2 and c.count("and", "xor") == 8
    assert verdict(c, secrets, randoms) == (False, False)


def test_reported_circuits_agree_with_verifmsi():
    if not ORACLE_PY.exists():
        pytest.skip("VerifMSI oracle not installed")
    circuits = [(to_circuit(r), s, n) for r, s, n in FIX.values()]
    for name in ("isw (no registers)", "dom (no registers)"):
        picks, secrets, randoms = _extract(name, "transparent")
        circuits.append((term_circuit([p[1] for p in picks]), secrets, randoms))
    for c, secrets, randoms in circuits:
        _, bad, nb_leak = crosscheck(c, secrets, randoms)
        assert bad == []
        assert (nb_leak > 0) == verdict(c, secrets, randoms)[0]
