# Findings — what this project found, and how to check each one

Every finding below is reproducible from this repository. `verify.py` re-runs
the experiment behind each one, checks its output for the reported result, and
records the run in `outputs/MANIFEST.json` (commit, tool versions, VerifMSI
commit, pass/fail and a SHA-256 per output).

```bash
uv sync
bash experiments/oracle_crosscheck/setup_oracles.sh   # VerifMSI, outside the repo (GPL)
uv run python findings/verify.py                      # fast steps, ~1 min
uv run python findings/verify.py --full               # + slow timing sweeps, ~5 min
```

A step that needs VerifMSI is **skipped** without it, and a skip is not a
pass. Scope of every finding: first order, 2 shares, straight-line circuits;
glitch-free unless the glitch-extended model is named (`design/0018`).

## Index

| ID | Finding | Key numbers | Evidence | Verify step | Independent check |
|---|---|---|---|---|---|
| **F1** | Equality saturation with cost-minimal extraction is **unsound** for masked circuits | Secure 8-gate ISW AND → 7-gate circuit leaking `b0 ⊕ b1`; same leak on two engines | `experiments/premise_test/RESULTS.md`, `experiments/egglog_port/RESULTS.md` | `F1`, `F1b` | Leaking wires confirmed by VerifMSI (F2 set) |
| **F2** | The in-house checkers are **trustworthy** | Exact checker: 1,216 circuits / 21,760 wires; bitsliced labeller: 1,265 / 22,463; **0 disagreements** with VerifMSI | `experiments/oracle_crosscheck/RESULTS.md`, `design/0005` | `F2` (sample of 49 circuits) | VerifMSI (GPL, external process) |
| **F3** | Security-constrained extraction **repairs** it | Recovers the 8-gate secure ISW; price of security 1 gate | `design/0006`, `run_constrained.py` | `F3` | Checker from F2 |
| **F4** | **No payoff** from plain Boolean rewriting at chain scale | Hand-written chain 16 gates secure; unconstrained 14, insecure; 240 sampled cheaper pairs, none secure | `docs/feasibility-report.md` §4 | `F4` | Checker from F2 |
| **F5** | Labelling and search **scale** at chain scale | egglog saturates depth-5 chain < 0.01 s; bitsliced labeller labels it in ~0.4 s (reference ~50 min, extrapolated) | `experiments/labeller/RESULTS.md`, `design/0009`, `0015` | `F5` (`--full`) | Labels identical to the reference labeller |
| **F6** | In a **shared-value layer**, refresh and gadget substitution are ordinary rewrites; the constraint still matters there | Over-refreshed chain 30 → 18; `a&b ^ a&d` 20 → 11 secure; dropping a needed refresh is cheaper (11) and leaks, constrained keeps it (14) | `experiments/resharing/RESULTS.md`, `design/0016` | `F6` | VerifMSI: 27 circuits / 914 wires, 0 violations |
| **F7** | **Tight starts gain nothing** | Hand-written chain 18, Keccak chi (3- and 5-bit rows) 36 and 60 — unchanged under every rule class | `experiments/resharing/RESULTS.md` | `F6` (same run) | As F6 |
| **F8** | The story **carries over to the glitch-extended model** | Glitch checker vs VerifMSI's own leakage sets: 167 probes, 0 disagreements; transparent registers: registered DOM 10 → 5, chain 20 → 10, leaking; occurrence-aware extraction restores security by placing registers | `experiments/glitch_probe/RESULTS.md`, `design/0017` | `F8` | VerifMSI exact + `checkSecurity` (glitches) |
| **F9** | **Theory**: one result for value-preserving, leakage-changing operators (refresh, register), claims C1–C8 | 12 executable witnesses | `docs/theory.md`, `experiments/claims/test_claims.py` | `F9` | Witnesses, not proofs — proofs to be checked by the author |
| **F10** | **Prior-art status** | Claims survive narrowly at medium confidence; glitch phenomenon and register placement not claimable | `docs/adversarial-search-3.md`, `docs/adversarial-search-4.md` | — | Query logs in the passes |

Slow-step timings in `outputs/` vary by machine; the checked strings do not.

## What these findings do not show

- **Any gain over a tight, published construction.** Every gain (F6) comes
  from a start circuit with deliberate slack (F7).
- **Novelty of the optimizations** (refresh removal, factoring, gadget choice,
  register placement), or that optimizers breaking masking is new
  (`docs/adversarial-search-4.md` §5).
- **Higher orders, more shares, PINI/SNI composition, transitions, register
  timing**, or behaviour of real synthesis tools.
- **Optimality**: extraction is exact only on its k-best frontier.

## Provenance

The work was done as a team until 2026-10-17 and solo since; per-file
authorship is in `git log`. Parts of the code and documents were written with
an AI assistant (Claude); the experiments, numbers and cross-checks above are
reproducible regardless of who wrote them, which is the point of this folder.

## Files

| Path | What |
|---|---|
| `verify.py` | Runs every step; writes `outputs/` |
| `outputs/MANIFEST.json` | Last run: commit, versions, per-step status and output hashes |
| `outputs/<id>.txt` | Raw output of each step |
