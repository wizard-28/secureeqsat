"""Cross-check the in-house first-order checker against VerifMSI.

Closes the trust boundary required by design/0005: no security claim may rest
on the in-house checker alone.

What we learned about the oracle (probed empirically, see RESULTS.md):
  * `getDistribWithExev(e)` returns (uniform, independent) and is EXACT — it is
    the same property our checker implements. Used two-sided.
  * `checkTpsVal(e)` returns a 3-tuple and is a SOUND but INCOMPLETE symbolic
    certificate: over 400 random expressions, tps=True never contradicted
    exhaustive independence, but tps=False sometimes did (false alarms).
    Used one-sided.

Protocol per wire:
  RULE 1 (two-sided)  our verdict == VerifMSI exact "independent"
                      -> failure on mismatch
  RULE 2 (internal)   tps=True must imply exact independent=True
                      -> failure on contradiction
  RULE 3 (one-sided)  tps=True must imply our verdict == safe
                      -> failure on contradiction
  INFO                tps=False while exact says independent
                      -> counted, not a failure (VerifMSI conservatism)

VerifMSI is GPLv3 and lives outside this repo; it is invoked as an external
process (setup_oracles.sh, AGENTS.md §6.4).

Usage:
    uv run python experiments/oracle_crosscheck/crosscheck.py [--random N]
Exit codes: 0 = no violations, 1 = violation(s), 2 = oracle unavailable.
"""

import argparse
import itertools
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "premise_test"))

from masked import (  # noqa: E402
    Circuit,
    build_dom_and,
    build_isw_and,
    build_isw_and_wrong_order,
    build_masked_buffer,
    build_naive_unmasked_intermediate,
    check_first_order,
)

ORACLE_DIR = Path(os.environ.get("SECUREEQSAT_ORACLE_DIR", Path.home() / "oracles"))
ORACLE_PY = ORACLE_DIR / "venv" / "bin" / "python"
DRIVER = Path(__file__).resolve().parent / "verifmsi_driver.py"

SECRETS_AB = {"a": ["a0", "a1"], "b": ["b0", "b1"]}
SECRETS_A = {"a": ["a0", "a1"]}


def oracle_available():
    return ORACLE_PY.exists() and (ORACLE_DIR / "verif_msi").is_dir()


def free_vars(secrets, randoms):
    return [shares[0] for shares in secrets.values()] + list(randoms)


def circuit_to_payload(circ, secrets, randoms):
    wires = []
    for name, op, payload in circ.wires:
        if op == "input":
            wires.append({"name": name, "op": "input", "args": payload})
        elif op == "const":
            wires.append({"name": name, "op": "const", "args": 1 if payload else 0})
        elif op in ("xor", "and"):
            wires.append({"name": name, "op": op, "args": [payload[0], payload[1]]})
        else:
            raise ValueError(f"unsupported op: {op!r}")
    return {
        "shares": {s: list(sh) for s, sh in secrets.items()},
        "randoms": list(randoms),
        "wires": wires,
    }


def oracle_verdict(circ, secrets, randoms):
    env = dict(os.environ, PYTHONPATH=str(ORACLE_DIR))
    proc = subprocess.run(
        [str(ORACLE_PY), str(DRIVER)],
        input=json.dumps(circuit_to_payload(circ, secrets, randoms)),
        capture_output=True,
        text=True,
        env=env,
        timeout=1800,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"oracle failed (rc={proc.returncode}): {proc.stderr[-2000:]}"
        )
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT_JSON:"):
            return json.loads(line[len("RESULT_JSON:") :])
    raise RuntimeError(f"no RESULT_JSON in oracle output: {proc.stdout[-2000:]!r}")


def compare(circ, secrets, randoms):
    """Return dict with ours, oracle, violations, conservative, safe_wires."""
    ours = check_first_order(circ, secrets, free_vars(secrets, randoms))
    oracle = oracle_verdict(circ, secrets, randoms)
    violations = []
    conservative = 0
    safe_wires = 0
    for name, _, _ in circ.wires:
        if ours[name]:
            safe_wires += 1
        o = oracle.get(name)
        if o is None or "error" in o:
            violations.append((name, "oracle-error", o))
            continue
        exact = bool(o["independent"])
        tps = bool(o["tps"])
        if bool(ours[name]) != exact:  # RULE 1
            violations.append((name, "exact-mismatch", (bool(ours[name]), exact)))
        if tps and not exact:  # RULE 2
            violations.append((name, "oracle-internal-contradiction", None))
        if tps and not ours[name]:  # RULE 3
            violations.append((name, "certificate-contradiction", None))
        if not tps and exact:  # INFO
            conservative += 1
    return {
        "ours": ours,
        "oracle": oracle,
        "violations": violations,
        "conservative": conservative,
        "safe_wires": safe_wires,
        "n_wires": len(circ.wires),
    }


# ---- circuit families -------------------------------------------------


def fixture_cases():
    """(label, circuit, secrets, randoms, expected_all_wires_secure)."""
    return [
        ("masked_buffer", build_masked_buffer(), SECRETS_A, ["r"], True),
        ("isw_and", build_isw_and(), SECRETS_AB, ["r"], True),
        ("dom_and", build_dom_and(), SECRETS_AB, ["r"], True),
        ("isw_wrong_order", build_isw_and_wrong_order(), SECRETS_AB, ["r"], False),
        (
            "naive_unmasked_intermediate",
            build_naive_unmasked_intermediate(),
            SECRETS_AB,
            ["r"],
            False,
        ),
    ]


def isw_reassociation_variants():
    """c1 = left fold over every permutation of {p2, p3, p4, r}.

    All 24 circuits compute the same function; some fold r in early enough to
    be secure, others leak. Puts the cross-check on the secure/insecure
    boundary.
    """
    out = []
    for perm in itertools.permutations(["p2", "p3", "p4", "r"]):
        c = Circuit()
        a0 = c.add_input("a0")
        a1 = c.add_input("a1")
        b0 = c.add_input("b0")
        b1 = c.add_input("b1")
        r = c.add_input("r")
        created = {
            "p2": c.add_gate("and", a0, b1),
            "p3": c.add_gate("and", a1, b0),
            "p4": c.add_gate("and", a1, b1),
            "r": r,
        }
        terms = [created[t] for t in perm]
        acc = terms[0]
        for t in terms[1:]:
            acc = c.add_gate("xor", acc, t)
        p1 = c.add_gate("and", a0, b0)
        c.outputs = [c.add_gate("xor", p1, r), acc]
        out.append((f"isw_perm_{'_'.join(perm)}", c))
    return out


def random_circuit(rng, n_randoms, n_gates):
    c = Circuit()
    a0 = c.add_input("a0")
    a1 = c.add_input("a1")
    b0 = c.add_input("b0")
    b1 = c.add_input("b1")
    randoms = [c.add_input(f"r{i}") for i in range(n_randoms)]
    pool = [a0, a1, b0, b1, *randoms]
    rng.shuffle(pool)
    for _ in range(n_gates):
        x = rng.choice(pool)
        y = rng.choice(pool)
        pool.append(c.add_gate(rng.choice(["xor", "and"]), x, y))
    c.outputs = [pool[-1]]
    return c, randoms


# ---- driver -----------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--random", type=int, default=120)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--random-randoms", type=int, default=3)
    ap.add_argument("--random-gates", type=int, default=10)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not oracle_available():
        print("Oracle unavailable. Run:")
        print("  bash experiments/oracle_crosscheck/setup_oracles.sh")
        print(f"Looked for {ORACLE_PY} and {ORACLE_DIR / 'verif_msi'}")
        return 2

    t0 = time.time()
    totals = {
        "cases": 0,
        "wires": 0,
        "safe_wires": 0,
        "conservative": 0,
        "violations": [],
        "expect_failures": [],
    }

    def run_case(label, circ, secrets, randoms, expected_secure=None):
        r = compare(circ, secrets, randoms)
        totals["cases"] += 1
        totals["wires"] += r["n_wires"]
        totals["safe_wires"] += r["safe_wires"]
        totals["conservative"] += r["conservative"]
        if r["violations"]:
            totals["violations"].append((label, r["violations"][:4]))
        if (
            expected_secure is not None
            and (r["safe_wires"] == r["n_wires"]) != expected_secure
        ):
            totals["expect_failures"].append(label)
        if not args.quiet:
            state = (
                "all safe"
                if r["safe_wires"] == r["n_wires"]
                else f"{r['n_wires'] - r['safe_wires']} unsafe"
            )
            extra = (
                f" (+{r['conservative']} conservative tps)" if r["conservative"] else ""
            )
            flag = "VIOLATION" if r["violations"] else "ok"
            print(f"  {flag:9s} {label}: {state}{extra}")

    print("== hand fixtures ==")
    for label, circ, secrets, randoms, expected in fixture_cases():
        run_case(label, circ, secrets, randoms, expected)

    print("== ISW reassociation variants ==")
    for label, circ in isw_reassociation_variants():
        run_case(label, circ, SECRETS_AB, ["r"])

    if args.random:
        print(f"== random circuits (n={args.random}, seed={args.seed}) ==")
        rng = random.Random(args.seed)
        for i in range(args.random):
            circ, randoms = random_circuit(rng, args.random_randoms, args.random_gates)
            run_case(f"random_{i:03d}", circ, SECRETS_AB, randoms)

    dt = time.time() - t0
    print()
    print(
        f"cases={totals['cases']}  wires={totals['wires']}  "
        f"safe_wires={totals['safe_wires']}  "
        f"conservative_tps_alarms={totals['conservative']}  "
        f"({dt:.1f}s)"
    )
    if totals["expect_failures"]:
        print("FIXTURE EXPECTATION FAILURES:", totals["expect_failures"])
    if totals["violations"]:
        print("VIOLATIONS:")
        for label, v in totals["violations"]:
            print(f"  {label}: {v}")
        return 1
    print("RESULT: no violations.")
    print("  - our verdict == VerifMSI exact independence on every wire (two-sided)")
    print("  - no tps certificate contradicted us (one-sided)")
    print("  - conservative tps alarms counted and explained, not failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
