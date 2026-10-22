"""Composition analysis experiments (design/0019).

    uv run python experiments/composition/run_composition.py            # all sections
    uv run python experiments/composition/run_composition.py --no-oracle

1. which gadgets are 1-PINI (exact checker, cross-checked with VerifMSI);
2. composable extraction vs the exact term extractor on every fixture;
3. soundness on random PINI-only terms (exact checker must agree);
4. scale: circuits beyond the exact checkers' 2**26 range, certified by
   composition and independently by VerifMSI's symbolic (sound) check.
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

ORACLE_DIR = Path(os.environ.get("SECUREEQSAT_ORACLE_DIR", Path.home() / "oracles"))
ORACLE_PY = ORACLE_DIR / "venv" / "bin" / "python"


def oracle(driver, payload):
    env = dict(os.environ, PYTHONPATH=str(ORACLE_DIR))
    p = subprocess.run(
        [str(ORACLE_PY), str(HERE / driver)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=1800,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-2000:])
    for line in p.stdout.splitlines():
        if line.startswith("RESULT_JSON:"):
            return json.loads(line[len("RESULT_JSON:") :])
    raise RuntimeError(p.stdout[-2000:])


def verifmsi_pini(op):
    low = lower([gadget_term(op)])
    sharings = {"x": ["x0", "x1"]}
    if op not in ("refresh", "not"):
        sharings["y"] = ["y0", "y1"]
    payload = {
        "sharings": sharings,
        "randoms": low.randoms,
        "wires": [{"name": n, "op": o, "args": a} for n, o, a in low.circ.wires],
        "outputs": [low.circ.outputs],
    }
    return oracle("pini_driver.py", payload)["nb_leak"] == 0


def verifmsi_certify(term):
    low = lower([term])
    payload = {
        "shares": secret_groups(secrets_of(term)),
        "randoms": low.randoms,
        "wires": [{"name": n, "op": o, "args": a} for n, o, a in low.circ.wires],
    }
    res = oracle("tps_driver.py", payload)
    return res["certified"], len(res["not_certified"])


def bits_of(term):
    low = lower([term])
    return 2 * len(secrets_of(term)) + len(low.randoms), low


def section_gadgets(use_oracle):
    print("== 1. which gadgets are 1-PINI")
    rows = []
    for op in ("xor", "not", "refresh", *GADGETS):
        ours = gadget_is_pini(op)[0]
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
    print("\n== 2. composable vs exact term extraction (cost = gates + randoms)")
    for name, term in {**FIXTURES, **TIGHT}.items():
        for rules in (("R2",), ("R1", "R2", "R3")):
            eg, _ = saturate(term, rules, 6)
            classes, root = export(eg)
            t0 = time.time()
            comp = extract_composable(classes, root)
            t_comp = time.time() - t0
            t0 = time.time()
            exact, _ = kbest(classes, root, k=8, secure=True)
            t_exact = time.time() - t0
            label = "+".join(rules)
            if comp is None:
                print(
                    f"  {name:<14} {label:<9} composable: no          "
                    f"exact: {exact[0] if exact else '-'}"
                )
                continue
            c, leaks = Evaluator()(comp)
            frac = len(composable_classes(classes)) / len(classes)
            print(
                f"  {name:<14} {label:<9} composable: {c:>3} "
                f"{'LEAKS' if leaks else 'secure'} ({t_comp * 1000:.1f} ms)  "
                f"exact: {exact[0] if exact else '-':>3} ({t_exact:.2f} s)  "
                f"composable classes {frac:.0%}"
            )


def random_pini_term(rng, depth, leaves):
    if depth == 0 or rng.random() < 0.2:
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
    print("\n== 3. soundness: random PINI-only terms, exact checker verdict")
    rng = random.Random(19)
    leaves = [("in", s) for s in "abd"]
    checked = leaked = 0
    for _ in range(n):
        t = random_pini_term(rng, 3, leaves)
        if t[0] == "in" or bits_of(t)[0] > DEFAULT_MAX_BITS:
            continue
        checked += 1
        if Evaluator()(t)[1]:
            leaked += 1
    print(f"  {checked} terms checked exactly, {leaked} leaking (must be 0)")
    return checked, leaked


def chain(depth):
    term = ("in", "x0")
    for i in range(1, depth + 1):
        term = ("isw", term, ("in", f"x{i}"))
    return term


def section_scale(use_oracle):
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
        t_total = time.time() - t0
        bits, low = bits_of(term)
        exact = "checked" if bits <= DEFAULT_MAX_BITS else "refused"
        if exact == "checked":
            exact = "secure" if not Evaluator()(term)[1] else "LEAKS"
        cert = ""
        if use_oracle:
            ok, missing = verifmsi_certify(term)
            cert = f"VerifMSI certifies {ok}/{ok + missing} wires"
        print(
            f"  {label:<24} cost {cost_of(low):>5}  space 2**{bits:<4} "
            f"exact: {exact:<8} composition: secure ({t_total:.2f} s)  {cert}"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-oracle", action="store_true")
    args = ap.parse_args()
    use_oracle = not args.no_oracle and ORACLE_PY.exists()
    if not use_oracle:
        print("VerifMSI not available: oracle columns SKIPPED (not passed)\n")
    section_gadgets(use_oracle)
    section_fixtures()
    section_soundness()
    section_scale(use_oracle)


if __name__ == "__main__":
    main()
