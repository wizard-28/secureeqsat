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
  RULE 1b (two-sided) the bitsliced labeller's verdict (experiments/labeller,
                      design/0015) == VerifMSI exact "independent"
                      -> failure on mismatch
  RULE 2 (internal)   tps=True must imply exact independent=True
                      -> failure on contradiction
  RULE 3 (one-sided)  tps=True must imply our verdict == safe
                      -> failure on contradiction
  INFO                tps=False while exact says independent
                      -> counted, not a failure (VerifMSI conservatism)

VerifMSI is GPLv3 and lives outside this repo; it is invoked as an external
process (setup_oracles.sh, AGENTS.md §6.4).

Purpose
-------
This is the REFEREE. The project's own checkers (`masked.check_first_order` and
the bitsliced labeller) were written in-house, so a bug in them could silently
make an insecure circuit look secure. VerifMSI is an independent tool written by
other people. This script sends many circuits to both and compares their verdicts
wire by wire. Any disagreement is a stop-and-fix condition (AGENTS.md).

The circuits tested come from three families: the hand-written fixtures, all 24
re-orderings of the XORs in the ISW second output (some secure, some leaking: the
interesting boundary), and random circuits.

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
sys.path.insert(0, str(ROOT / "experiments" / "labeller"))

from labeller import check_first_order_bitsliced  # noqa: E402
from masked import (  # noqa: E402
    Circuit,
    build_dom_and,
    build_isw_and,
    build_isw_and_wrong_order,
    build_masked_buffer,
    build_naive_unmasked_intermediate,
    check_first_order,
)

# Where VerifMSI is installed (outside the repo; it is GPL). Override the location
# with the SECUREEQSAT_ORACLE_DIR environment variable. It runs in its own Python
# virtual environment, started as a separate process by `oracle_verdict`.
ORACLE_DIR = Path(os.environ.get("SECUREEQSAT_ORACLE_DIR", Path.home() / "oracles"))
ORACLE_PY = ORACLE_DIR / "venv" / "bin" / "python"
DRIVER = Path(__file__).resolve().parent / "verifmsi_driver.py"  # runs inside the venv

# Secret groups used by the fixtures: which inputs are the shares of which secret.
SECRETS_AB = {"a": ["a0", "a1"], "b": ["b0", "b1"]}
SECRETS_A = {"a": ["a0", "a1"]}


def oracle_available():
    """True if VerifMSI's Python and source directory exist where we expect them."""
    return ORACLE_PY.exists() and (ORACLE_DIR / "verif_msi").is_dir()


def free_vars(secrets, randoms):
    """The free (uniform) bits: first share of each secret plus the randoms."""
    return [shares[0] for shares in secrets.values()] + list(randoms)


def circuit_to_payload(circ, secrets, randoms):
    """Convert a `Circuit` into the JSON-able dict that the VerifMSI driver reads.

    The payload lists the secret groups, the random inputs, and every wire as
    `{name, op, args}` in creation order. Raises `ValueError` for any wire kind the
    driver does not support (only inputs, constants, AND and XOR are).
    """
    wires = []  # JSON-ready wire records, e.g. {"name": "xor(a0,r)", "op": "xor", ...}
    for name, op, payload in circ.wires:
        if op == "input":
            wires.append({"name": name, "op": "input", "args": payload})
        elif op == "const":
            # JSON has no Python bool here: send the constant as 1 or 0
            wires.append({"name": name, "op": "const", "args": 1 if payload else 0})
        elif op in ("xor", "and"):
            # a tuple of operand names becomes a JSON list, e.g. ["a0", "r"]
            wires.append({"name": name, "op": op, "args": [payload[0], payload[1]]})
        else:
            raise ValueError(f"unsupported op: {op!r}")
    return {
        # secret name -> list of its share names, e.g. {"a": ["a0", "a1"]}
        "shares": {s: list(sh) for s, sh in secrets.items()},
        "randoms": list(randoms),  # fresh random input names, e.g. ["r"]
        "wires": wires,
    }


def oracle_verdict(circ, secrets, randoms):
    """Ask VerifMSI about every wire of `circ`; return its per-wire answers.

    Algorithm, step by step:
      1. Serialise the circuit to JSON with `circuit_to_payload`.
      2. Start VerifMSI's driver as a SEPARATE process, using VerifMSI's own
         Python, and send the JSON on its standard input (separate process, so the
         GPL code is never linked into ours). Time out after 30 minutes.
      3. If the process fails, raise an error showing the tail of its stderr.
      4. Scan its output for the line starting `RESULT_JSON:` and parse it.
    The result is `{wire_name: {"independent": bool, "tps": bool, ...}}`, where
    `independent` is VerifMSI's EXACT check and `tps` is its sound-but-incomplete
    symbolic certificate.
    """
    # a copy of our environment, plus PYTHONPATH so the driver can import VerifMSI
    env = dict(os.environ, PYTHONPATH=str(ORACLE_DIR))
    proc = subprocess.run(  # start VerifMSI's own Python as a separate process
        [str(ORACLE_PY), str(DRIVER)],
        input=json.dumps(circuit_to_payload(circ, secrets, randoms)),  # sent on stdin
        capture_output=True,  # collect stdout and stderr instead of printing them
        text=True,  # treat them as text, not bytes
        env=env,
        timeout=1800,  # seconds (30 minutes) before giving up
    )
    if proc.returncode != 0:  # non-zero exit status means the driver crashed
        raise RuntimeError(
            f"oracle failed (rc={proc.returncode}): {proc.stderr[-2000:]}"
        )
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT_JSON:"):
            # `[len(...):]` slices off the tag, leaving just the JSON text
            return json.loads(line[len("RESULT_JSON:") :])
    raise RuntimeError(f"no RESULT_JSON in oracle output: {proc.stdout[-2000:]!r}")


def compare(circ, secrets, randoms):
    """Return dict with ours, oracle, violations, conservative, safe_wires.

    Algorithm, step by step:
      1. Compute the verdict for every wire with three independent methods: our
         exact checker (`ours`), the bitsliced labeller (`bitsliced`), and VerifMSI
         (`oracle`).
      2. For each wire, apply the protocol from the module docstring:
           RULE 1   our exact verdict must equal VerifMSI's exact "independent".
           RULE 1b  the bitsliced verdict must equal it too.
           RULE 2   if VerifMSI's certificate says safe, its own exact check must
                    agree (a contradiction here would be a bug in VerifMSI).
           RULE 3   if the certificate says safe, we must also say safe.
           INFO     the certificate saying "not proven" while the exact check
                    says safe is expected conservatism: counted, not an error.
      3. Return the verdicts, a list of violations (empty means full agreement),
         the conservative count, how many wires we consider safe, and the number
         of wires.
    """
    free = free_vars(secrets, randoms)  # the free bits, e.g. ["a0", "b0", "r"]
    ours = check_first_order(circ, secrets, free)  # our exact verdicts {wire: safe?}
    bitsliced = check_first_order_bitsliced(circ, secrets, free)  # the fast labeller
    oracle = oracle_verdict(circ, secrets, randoms)  # VerifMSI: {wire: {...}}
    violations = []  # disagreements found, e.g. [("xor(a0,r)", "exact-mismatch", ...)]
    conservative = 0  # wires where VerifMSI's certificate was cautious but we agree
    safe_wires = 0  # wires our checker considers safe
    for name, _, _ in circ.wires:
        if ours[name]:
            safe_wires += 1
        o = oracle.get(name)  # VerifMSI's record for this wire, or None
        if o is None or "error" in o:
            violations.append((name, "oracle-error", o))
            continue
        exact = bool(o["independent"])  # VerifMSI's EXACT verdict: True = safe
        tps = bool(o["tps"])  # VerifMSI's certificate: True means proven safe
        if bool(ours[name]) != exact:  # RULE 1
            violations.append((name, "exact-mismatch", (bool(ours[name]), exact)))
        if bitsliced[name] != exact:  # RULE 1b
            violations.append((name, "bitsliced-mismatch", (bitsliced[name], exact)))
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
    """(label, circuit, secrets, randoms, expected_all_wires_secure).

    The five hand-written circuits with a known answer: three secure
    (masked buffer, ISW, DOM) and two insecure (ISW with r added last, and the
    naive circuit that builds an unmasked intermediate).
    """
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

    Algorithm: for each of the 24 permutations of the four terms (a0&b1, a1&b0,
    a1&b1 and r), build an ISW gadget whose second output XORs the terms together
    left to right in that order. Returns a list of `(label, circuit)`.
    """
    out = []  # list of (label, circuit), 24 entries
    # every ordering of the four terms, e.g. ("r", "p2", "p3", "p4"); 4! = 24
    for perm in itertools.permutations(["p2", "p3", "p4", "r"]):
        c = Circuit()
        a0 = c.add_input("a0")  # shares of a
        a1 = c.add_input("a1")
        b0 = c.add_input("b0")  # shares of b
        b1 = c.add_input("b1")
        r = c.add_input("r")
        created = {  # term name -> its wire, so a permutation can be looked up
            "p2": c.add_gate("and", a0, b1),  # cross product a0*b1
            "p3": c.add_gate("and", a1, b0),  # cross product a1*b0
            "p4": c.add_gate("and", a1, b1),  # product a1*b1
            "r": r,
        }
        terms = [created[t] for t in perm]  # the wires in this permutation's order
        acc = terms[0]  # the running XOR; starts with the first term
        for t in terms[1:]:
            acc = c.add_gate("xor", acc, t)  # fold in the next term, left to right
        p1 = c.add_gate("and", a0, b0)  # a0*b0, used by output share 0
        c.outputs = [c.add_gate("xor", p1, r), acc]
        out.append((f"isw_perm_{'_'.join(perm)}", c))
    return out


def random_circuit(rng, n_randoms, n_gates):
    """Build a random AND/XOR circuit over the shares of a and b and some randoms.

    Algorithm: start with a pool of the four share inputs and `n_randoms` random
    inputs, shuffled. Repeat `n_gates` times: pick two wires from the pool at
    random, add a random AND or XOR of them, and put the new wire back in the
    pool. The last wire is the output. Returns `(circuit, random_input_names)`.
    These have no expected verdict: they test that the two checkers agree.
    """
    c = Circuit()
    a0 = c.add_input("a0")  # shares of a
    a1 = c.add_input("a1")
    b0 = c.add_input("b0")  # shares of b
    b1 = c.add_input("b1")
    randoms = [c.add_input(f"r{i}") for i in range(n_randoms)]  # ["r0", "r1", ...]
    # `*randoms` unpacks the list into the new list: [a0, a1, b0, b1, r0, r1, ...]
    pool = [a0, a1, b0, b1, *randoms]  # wires that new gates may use as operands
    rng.shuffle(pool)  # random order (rng is seeded, so runs are reproducible)
    for _ in range(n_gates):
        x = rng.choice(pool)  # a random operand wire
        y = rng.choice(pool)  # another random operand wire (may equal x)
        pool.append(c.add_gate(rng.choice(["xor", "and"]), x, y))  # new wire joins pool
    c.outputs = [pool[-1]]  # the last wire created is the output
    return c, randoms


# ---- driver -----------------------------------------------------------


def main():
    """Run the whole cross-check and print a summary.

    Algorithm, step by step:
      1. If VerifMSI is not installed, say how to install it and exit with code 2.
      2. Run `compare` on the five fixtures, also checking each fixture's expected
         secure/insecure answer.
      3. Run `compare` on all 24 ISW re-ordering variants.
      4. Run `compare` on `--random` randomly generated circuits (seeded, so the
         run is reproducible).
      5. Accumulate totals (cases, wires, safe wires, conservative alarms) and any
         violations as it goes.
      6. Print the totals. Exit 0 if there were no violations, 1 if there were.
    """
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

    t0 = time.time()  # start time, for reporting how long the whole run took
    totals = {  # running counters across every circuit tested
        "cases": 0,  # circuits compared so far, e.g. 149
        "wires": 0,  # wires compared so far
        "safe_wires": 0,  # wires our checker called safe
        "conservative": 0,  # VerifMSI certificate cautious, exact check agreed safe
        "violations": [],  # (label, [violation, ...]) for any disagreement
        "expect_failures": [],  # fixtures whose overall verdict was not as expected
    }

    def run_case(label, circ, secrets, randoms, expected_secure=None):
        """Compare one circuit across checkers, update totals, print one line.

        If `expected_secure` is given (the fixtures), also record a failure when
        the circuit's overall verdict differs from the expected one.
        """
        r = compare(circ, secrets, randoms)  # r: the dict returned by `compare`
        totals["cases"] += 1
        totals["wires"] += r["n_wires"]
        totals["safe_wires"] += r["safe_wires"]
        totals["conservative"] += r["conservative"]
        if r["violations"]:
            totals["violations"].append((label, r["violations"][:4]))  # first 4 only
        # A circuit is "all secure" when every wire is safe. `!=` is True when that
        # differs from what the fixture is supposed to be.
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
    print("  - bitsliced labeller == VerifMSI exact independence on every wire")
    print("  - no tps certificate contradicted us (one-sided)")
    print("  - conservative tps alarms counted and explained, not failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
