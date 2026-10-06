# 0005 — Security checker and the external-oracle trust boundary

- **Status:** accepted — **gate closed** (0 violations)
- **Date:** 2026-10-06
- **Deciders:** project team

## Context

The project needs a security decision procedure inside the search loop. If that procedure
is wrong in a direction that flatters the optimizer, every result is void — this is the
single largest scientific risk in the project.

The in-house checker (`experiments/premise_test/masked.py`) implements first-order,
2-share, straight-line, glitch-free probing security: for each secret assignment it
enumerates all free-uniform assignments and compares each wire's value **distribution**
(number of 1s over the sample space) across secrets.

It has been validated against internal fixtures with the expected verdicts:

| Fixture | Expected | Verdict |
|---|---|---|
| Masked buffer `(a0^r, a1^r)` | secure | SECURE |
| ISW masked AND (correct construction) | secure | SECURE |
| Naive unmasked intermediate | insecure | INSECURE, names the unmasked secrets |

It also earned some trust by catching a genuine bug in a hand-written fixture: the first
"ISW" circuit folded `r` in too late, leaving `a0&b1 ^ a1&b0` as a leaking intermediate.
That is evidence the checker discriminates, not proof that it is correct.

**Self-validation is not independent validation.** A checker can be wrong in exactly the
way that makes an insecure optimizer look successful.

## Decision

1. The in-house checker drives the search loop (speed, auditability, no GPL linkage).
2. **Mandatory gate: cross-validate against at least one independent oracle before any
   security claim is made.** Order: **VerifMSI** (pure Python, closest to our stack), then
   **tightPROVE** (straight-line format, trivially generated). **Zero disagreements on
   fixtures is required.** The gate is **OPEN** as of this ADR.
3. VerifMSI and tightPROVE are **GPLv3**: invoke them as external processes only. Never
   link, vendor, or copy their code into our tree.
4. Regression tests must permanently cover the three ways this checker has been or could be
   wrong:
   - distribution vs. value sequence (a permuted uniform wire must be judged safe),
   - XOR-ordering sensitivity of ISW (the same function is secure or not depending on
     where `r` is folded in),
   - unmasked-intermediate detection.
5. Checker scope is first order, glitch-free, 2 shares. **No robust-probing, glitch, PINI,
   or higher-order claims may be made from this code** (see `design/0002`).

## Consequences

- Until the gate closes, every document must describe the checker as *internally validated
  only*, and no security claim may be stated. This applies to the proposal and the team
  briefing as written.
- If the oracle disagrees on any fixture, the correct response is to **stop and fix**, not
  to note the discrepancy and continue (`AGENTS.md` §11).
- If the oracle cannot express one of our fixtures, that limitation must be documented
  rather than silently skipped — a checker we cannot cross-validate is a checker we do not
  trust.
- The checker stays conservative: when in doubt, it should report a wire as unsafe, because
  a false "safe" is the dangerous direction.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Use an external oracle directly in the search loop | Interface impedance and uncertain performance; we want an auditable in-repo core that we own. May be revisited if the in-house checker proves too slow at scale. |
| Trust the in-house checker on internal fixtures | Self-validation cannot detect systematic error; this is the project's stated trust boundary |
| Skip a checker and rely only on published constructions | There is nothing to optimize if we cannot evaluate candidates |

## Evidence

- `experiments/premise_test/masked.py` — checker implementation.
- `experiments/premise_test/test_premise.py` — the five checker tests.
- `experiments/premise_test/RESULTS.md` §4.4 — limitations, including this open gate.
- `AGENTS.md` §6.3 (trust boundary), §11 (stopping conditions).
- Oracles: VerifMSI (`github.com/quentin-meunier/VerifMSI`), tightPROVE
  (`github.com/CryptoExperts/tightPROVE`, ASIACRYPT 2018).

## Status updates

- **2026-10-06** — **Gate closed.** The cross-check ran against VerifMSI over
  1,216 circuits / 21,760 wires with **0 disagreements**, so the stopping
  condition in `AGENTS.md` §6.3 and §11 is satisfied for the tested scope
  (first order, 2 shares, glitch-free). Gate reopens if the scope changes or a
  disagreement appears. `experiments/oracle_crosscheck/RESULTS.md`,
  `docs/feasibility-report.md`.
