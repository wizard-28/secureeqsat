"""Composition analysis experiments (design/0019).

    uv run python experiments/composition/run_composition.py            # all sections
    uv run python experiments/composition/run_composition.py --no-oracle

1. which gadgets are 1-PINI (exact checker, cross-checked with VerifMSI);
2. composable extraction vs the exact term extractor on every fixture;
3. soundness on random PINI-only terms (exact checker must agree);
4. scale: circuits beyond the exact checkers' 2**26 range, certified by
   composition and independently by VerifMSI's symbolic (sound) check.

Purpose
-------
This script produces the results table of finding F11 (see `RESULTS.md`). Section 1
shows which gadgets are PINI, section 2 compares the cheap composable extraction with
the exact (slow) one, section 3 stress-tests the theorem on random circuits, and
section 4 demonstrates circuits too big for exact checking (Keccak chi up to 32 bits,
ISW chains up to depth 15), certified by composition and by VerifMSI's symbolic check.
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for sub in ("composition", "resharing", "labeller", "premise_test"):
    sys.path.insert(0, str(ROOT / "experiments" / sub))

from analysis import (  # noqa: E402
    composable_classes,
    extract_composable,
    pini_operators,
)
from extract import Evaluator, kbest  # noqa: E402
from fixtures import FIXTURES, TIGHT, chi  # noqa: E402
from gadgets import (  # noqa: E402
    GADGETS,
    cost_of,
    lower,
    secret_groups,
    secrets_of,
)
from labeller import DEFAULT_MAX_BITS  # noqa: E402
from layer import export, saturate  # noqa: E402
from pini import gadget_is_pini, gadget_term  # noqa: E402

# Where VerifMSI lives (outside the repo; GPL) and the Python it runs in.
ORACLE_DIR = Path(os.environ.get("SECUREEQSAT_ORACLE_DIR", Path.home() / "oracles"))
ORACLE_PY = ORACLE_DIR / "venv" / "bin" / "python"


def oracle(driver, payload):
    """Run a VerifMSI driver script as a separate process; return its JSON answer.

    Args:
        driver: file name of the driver in this directory (`pini_driver.py` or
            `tps_driver.py`).
        payload: the dict to send as JSON on the driver's standard input.

    Algorithm: start VerifMSI's own Python with the driver (30 minute timeout), send the
    JSON, fail with the process's error text if it crashed, otherwise parse the line
    that starts with `RESULT_JSON:`.
    """
    # a copy of the environment plus PYTHONPATH so the driver can import VerifMSI
    env = dict(os.environ, PYTHONPATH=str(ORACLE_DIR))
    p = subprocess.run(
        [str(ORACLE_PY), str(HERE / driver)],
        input=json.dumps(payload),  # sent on stdin
        capture_output=True,  # collect stdout and stderr
        text=True,  # as text, not bytes
        env=env,
        timeout=1800,  # seconds
    )
    if p.returncode != 0:  # the driver crashed
        raise RuntimeError(p.stderr[-2000:])  # last 2000 characters of its stderr
    for line in p.stdout.splitlines():
        if line.startswith("RESULT_JSON:"):
            # slice off the tag so only the JSON text remains
            return json.loads(line[len("RESULT_JSON:") :])
    raise RuntimeError(p.stdout[-2000:])


def verifmsi_pini(op):
    """Does VerifMSI's PINI check pass for gadget `op`? (True = no leak found).

    Lowers the gadget, builds the JSON payload (the input sharings, the randoms, every
    wire, and the output share pair), runs `pini_driver.py`, and returns whether it
    reported zero leaks.
    """
    low = lower([gadget_term(op)])
    sharings = {"x": ["x0", "x1"]}  # input sharing names -> their two share names
    if op not in ("refresh", "not"):
        sharings["y"] = ["y0", "y1"]  # binary gadgets also have a second operand
    payload = {
        "sharings": sharings,
        "randoms": low.randoms,
        "wires": [{"name": n, "op": o, "args": a} for n, o, a in low.circ.wires],
        "outputs": [low.circ.outputs],  # one output sharing: [share0, share1]
    }
    return oracle("pini_driver.py", payload)["nb_leak"] == 0


def verifmsi_certify(term):
    """Ask VerifMSI's symbolic check how many wires of `term` it certifies safe.

    Returns `(certified, not_certified)` counts. Uses `tps_driver.py`, which needs no
    enumeration, so it works on circuits far beyond the exact checkers' range.
    """
    low = lower([term])
    payload = {
        "shares": secret_groups(secrets_of(term)),
        "randoms": low.randoms,
        "wires": [{"name": n, "op": o, "args": a} for n, o, a in low.circ.wires],
    }
    res = oracle("tps_driver.py", payload)
    return res["certified"], len(res["not_certified"])


def bits_of(term):
    """Width of the term's assignment space, and its lowering: `(bits, lowered)`.

    `bits` = 2 per secret (a secret's two shares) + number of randoms, an upper bound
    on the exponent of the exhaustive checkers' cost (the space has 2**bits points).
    """
    low = lower([term])
    return 2 * len(secrets_of(term)) + len(low.randoms), low


def section_gadgets(use_oracle):
    """Section 1: print whether each gadget is 1-PINI, by our checker and VerifMSI's."""
    print("== 1. which gadgets are 1-PINI")
    rows = []  # (operator, our verdict, VerifMSI's verdict or None)
    for op in ("xor", "not", "refresh", *GADGETS):
        ours = gadget_is_pini(op)[0]  # exhaustive in-house check
        theirs = verifmsi_pini(op) if use_oracle else None
        agree = "" if theirs is None else ("agree" if ours == theirs else "DISAGREE")
        verdict = "-" if theirs is None else ("PINI" if theirs else "not PINI")
        print(
            f"  {op:<8} ours: {'PINI' if ours else 'not PINI':<9} VerifMSI: "
            f"{verdict:<9} {agree}"
        )
        rows.append((op, ours, theirs))
    print(f"  operators used by the analysis: {sorted(pini_operators())}")
    return rows


def section_fixtures():
    """Section 2: composable extraction versus the exact extractor, on every fixture.

    Algorithm, step by step, for each fixture and each of two rule sets (R2 alone, and
    all three):
      1. Saturate and export the e-graph.
      2. Time the composable extraction (cheap, no enumeration).
      3. Time the exact k-best extraction (slow, enumerates).
      4. Print both costs, whether the composable result is secure, the fraction of
         classes that are composable, and the two timings. "composable: no" means the
         root cannot be built from PINI gadgets alone.
    """
    print("\n== 2. composable vs exact term extraction (cost = gates + randoms)")
    for name, term in {**FIXTURES, **TIGHT}.items():
        for rules in (("R2",), ("R1", "R2", "R3")):
            eg, _ = saturate(term, rules, 6)
            classes, root = export(eg)
            t0 = time.time()
            comp = extract_composable(classes, root)  # composable-only extraction
            t_comp = time.time() - t0
            t0 = time.time()
            exact, _ = kbest(classes, root, k=8, secure=True)  # the exact extractor
            t_exact = time.time() - t0
            label = "+".join(rules)  # e.g. "R1+R2+R3"
            if comp is None:
                print(
                    f"  {name:<14} {label:<9} composable: no          "
                    f"exact: {exact[0] if exact else '-'}"
                )
                continue
            c, leaks = Evaluator()(comp)  # cost and leaking wires of the result
            # share of classes marked composable, formatted below as a percentage
            frac = len(composable_classes(classes)) / len(classes)
            print(
                f"  {name:<14} {label:<9} composable: {c:>3} "
                f"{'LEAKS' if leaks else 'secure'} ({t_comp * 1000:.1f} ms)  "
                f"exact: {exact[0] if exact else '-':>3} ({t_exact:.2f} s)  "
                f"composable classes {frac:.0%}"
            )


def random_pini_term(rng, depth, leaves):
    """A random term built only from PINI operators (xor, not, refresh, hpc1).

    Algorithm: recurse. With depth 0 (or probability 0.2) return a random leaf.
    Otherwise pick a random operator; unary ones (not, refresh) wrap one subterm, binary
    ones (xor, hpc1) combine two. `depth` bounds the tree height; `leaves` are the
    input terms.
    """
    if depth == 0 or rng.random() < 0.2:  # stop at depth 0, or early with chance 20%
        return rng.choice(leaves)
    op = rng.choice(("xor", "not", "refresh", "hpc1"))
    if op in ("not", "refresh"):
        return (op, random_pini_term(rng, depth - 1, leaves))
    return (
        op,
        random_pini_term(rng, depth - 1, leaves),
        random_pini_term(rng, depth - 1, leaves),
    )


def section_soundness(n=300):
    """Section 3: random PINI-only terms must never leak (checked exactly).

    Generates `n` random PINI-only terms, skips trivial ones and any too large for the
    exact checker, runs the exact checker on the rest, and prints how many were checked
    and how many leaked (the theorem says: zero).
    """
    print("\n== 3. soundness: random PINI-only terms, exact checker verdict")
    rng = random.Random(19)  # fixed seed: the same terms every run
    leaves = [("in", s) for s in "abd"]  # the three secret inputs a, b, d
    checked = leaked = 0
    for _ in range(n):
        t = random_pini_term(rng, 3, leaves)
        # skip a bare input, and terms whose space exceeds the exact checker's cap
        if t[0] == "in" or bits_of(t)[0] > DEFAULT_MAX_BITS:
            continue
        checked += 1
        if Evaluator()(t)[1]:  # a non-empty list of leaking wires is truthy
            leaked += 1
    print(f"  {checked} terms checked exactly, {leaked} leaking (must be 0)")
    return checked, leaked


def chain(depth):
    """A chain of `depth` ISW gadgets: ((x0 AND x1) AND x2) ... as a term."""
    term = ("in", "x0")
    for i in range(1, depth + 1):
        term = ("isw", term, ("in", f"x{i}"))  # wrap in another ISW with the next input
    return term


def section_scale(use_oracle):
    """Section 4: circuits beyond the exact checkers' range.

    Algorithm, step by step, for each case (Keccak chi rows of 3 to 32 bits, ISW chains
    of depth 2 to 15):
      1. Saturate with R2 (so ISW can be swapped for HPC1, which is PINI) and extract
         the composable circuit, timing both.
      2. Compute the size of its assignment space (2**bits). If within 2**26 run the
         exact checker too, otherwise report "refused".
      3. If VerifMSI is available, ask its symbolic check how many wires it certifies.
      4. Print cost, space size, exact verdict, composition verdict and time.
    """
    print("\n== 4. scale: composable extraction where the exact checkers refuse")
    print("  start (ISW gadgets), rewritten with R2; exact range is 2**26 points")
    cases = [(f"Keccak chi, {n}-bit row", chi(n)) for n in (3, 5, 6, 8, 12, 16, 24, 32)]
    # Depth stops at 15: the harness Circuit names wires by their full
    # expression, and those names grow too fast past ~15 (a harness limit,
    # not one of the analysis).
    cases += [(f"ISW chain, depth {d}", chain(d)) for d in (2, 5, 10, 15)]
    for label, start in cases:
        t0 = time.time()
        eg, _ = saturate(start, ("R2",), 2)
        classes, root = export(eg)
        term = extract_composable(classes, root)
        t_total = time.time() - t0  # seconds for saturation + extraction
        bits, low = bits_of(term)
        # the exact checker can only run if the space fits within its 2**26 cap
        exact = "checked" if bits <= DEFAULT_MAX_BITS else "refused"
        if exact == "checked":
            exact = "secure" if not Evaluator()(term)[1] else "LEAKS"
        cert = ""  # text for the VerifMSI column, empty if not used
        if use_oracle:
            ok, missing = verifmsi_certify(term)
            cert = f"VerifMSI certifies {ok}/{ok + missing} wires"
        print(
            f"  {label:<24} cost {cost_of(low):>5}  space 2**{bits:<4} "
            f"exact: {exact:<8} composition: secure ({t_total:.2f} s)  {cert}"
        )


def main():
    """Run the four sections; `--no-oracle` skips every VerifMSI call."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-oracle", action="store_true")
    args = ap.parse_args()
    # use VerifMSI only if the user did not disable it AND it is installed
    use_oracle = not args.no_oracle and ORACLE_PY.exists()
    if not use_oracle:
        print("VerifMSI not available: oracle columns SKIPPED (not passed)\n")
    section_gadgets(use_oracle)
    section_fixtures()
    section_soundness()
    section_scale(use_oracle)


if __name__ == "__main__":
    main()
