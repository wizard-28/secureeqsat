"""Re-run every reported finding and record what happened.

    uv run python findings/verify.py            # all fast steps (~1-2 min)
    uv run python findings/verify.py --full     # adds the slow timing sweeps
    uv run python findings/verify.py --only F6 F8   # merges into MANIFEST.json

Each step runs one experiment, saves its raw output to findings/outputs/<id>.txt
and checks it for the result the finding reports. findings/outputs/MANIFEST.json
records the commit, tool versions, the oracle's commit, and per step: pass /
fail / skipped, time, and a SHA-256 of the output. Exit status is non-zero if
any step fails. A skipped step is NOT a pass.
"""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "findings" / "outputs"
ORACLE_DIR = Path(os.environ.get("SECUREEQSAT_ORACLE_DIR", Path.home() / "oracles"))
HAVE_ORACLE = (ORACLE_DIR / "venv" / "bin" / "python").exists()
PY = sys.executable

# id, finding, command, substrings that must appear, slow?, needs oracle?
STEPS = [
    ("G1", "gate", [PY, "-m", "ruff", "check", "."], ["All checks passed!"], 0, 0),
    ("G2", "gate", [PY, "-m", "ruff", "format", "--check", "."], ["formatted"], 0, 0),
    ("G3", "gate", [PY, "-m", "pytest", "-q"], [" passed"], 0, 0),
    (
        "F1",
        "unsoundness (in-house)",
        [PY, "experiments/premise_test/run.py"],
        ["PREMISE HOLDS"],
        0,
        0,
    ),
    (
        "F1b",
        "unsoundness (egglog)",
        [PY, "experiments/egglog_port/port.py", "--circuit", "isw"],
        ["7 gates", "INSECURE"],
        0,
        0,
    ),
    (
        "F2",
        "trust boundary",
        [PY, "experiments/oracle_crosscheck/crosscheck.py", "--random", "20"],
        ["RESULT: no violations."],
        0,
        1,
    ),
    (
        "F3",
        "repair (constrained extraction)",
        [PY, "experiments/constrained_extraction/run_constrained.py"],
        ["constrained optimum   : 8 gates, secure"],
        0,
        0,
    ),
    (
        "F4",
        "no payoff at chain scale",
        [PY, "experiments/egglog_port/kbest.py", "--rules", "full", "--k", "40"],
        ["cheapest extraction overall : 14 gates, INSECURE", "none found"],
        0,
        0,
    ),
    (
        "F5",
        "labelling cost",
        [PY, "experiments/labeller/measure.py"],
        ["labels identical"],
        1,
        0,
    ),
    (
        "F6",
        "shared-value layer + tight starts",
        [PY, "experiments/resharing/run.py", "--crosscheck"],
        ["0 violations"],
        0,
        1,
    ),
    (
        "F6s",
        "shared-value layer scale sweep",
        [PY, "experiments/resharing/run.py", "--scale"],
        ["depth 5"],
        1,
        0,
    ),
    (
        "F8",
        "glitch model probe",
        [PY, "experiments/glitch_probe/probe.py"],
        ["0 disagreements"],
        0,
        1,
    ),
    (
        "F9",
        "theory witnesses C1-C8",
        [PY, "-m", "pytest", "-q", "experiments/claims"],
        [" passed"],
        0,
        0,
    ),
]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def oracle_commit():
    try:
        return subprocess.run(
            ["git", "-C", str(ORACLE_DIR / "verif_msi"), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="include slow steps")
    ap.add_argument("--only", nargs="*", help="run only these step ids")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONHASHSEED="0")
    results = []
    for sid, finding, cmd, expect, slow, needs_oracle in STEPS:
        if args.only and sid not in args.only:
            continue
        if slow and not args.full and not args.only:
            results.append({"id": sid, "finding": finding, "status": "skipped (slow)"})
            print(f"[skip] {sid:<4} {finding} (slow; use --full)")
            continue
        if needs_oracle and not HAVE_ORACLE:
            status = "skipped (no oracle)"
            results.append({"id": sid, "finding": finding, "status": status})
            print(f"[SKIP] {sid:<4} {finding}: VerifMSI not installed -- not a pass")
            continue
        t0 = time.time()
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
        dt = time.time() - t0
        text = p.stdout + p.stderr
        out_file = OUT / f"{sid}.txt"
        out_file.write_text(text)
        ok = p.returncode == 0 and all(e in text for e in expect)
        if sid in ("G3", "F9") and " failed" in text:
            ok = False
        results.append(
            {
                "id": sid,
                "finding": finding,
                "status": "pass" if ok else "FAIL",
                "seconds": round(dt, 1),
                "command": " ".join(str(c) for c in cmd[1:]),
                "expected": expect,
                "output": str(out_file.relative_to(ROOT)),
                "output_sha256": sha256(text.encode()),
            }
        )
        print(f"[{'pass' if ok else 'FAIL'}] {sid:<4} {finding} ({dt:.1f}s)")

    if args.only and (OUT / "MANIFEST.json").exists():
        # merge into the previous run's record instead of discarding it
        previous = json.loads((OUT / "MANIFEST.json").read_text())["steps"]
        fresh = {r["id"] for r in results}
        results = [r for r in previous if r["id"] not in fresh] + results
        order = [s[0] for s in STEPS]
        results.sort(key=lambda r: order.index(r["id"]))

    lock = ROOT / "uv.lock"
    manifest = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": git("rev-parse", "HEAD"),
        # dirty = uncommitted changes outside findings/outputs (this run's own
        # output is expected to be new)
        "git_dirty": bool(
            git("status", "--porcelain", "--", ".", ":!findings/outputs")
        ),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "egglog": version("egglog"),
        "uv_lock_sha256": sha256(lock.read_bytes()) if lock.exists() else None,
        "verifmsi_commit": oracle_commit() if HAVE_ORACLE else None,
        "steps": results,
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    failed = [r["id"] for r in results if r["status"] == "FAIL"]
    skipped = [r["id"] for r in results if r["status"].startswith("skipped")]
    print(
        f"\n{len(results) - len(failed) - len(skipped)} passed, {len(failed)} failed,"
    )
    print(f"{len(skipped)} skipped {skipped if skipped else ''}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
