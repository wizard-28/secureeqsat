# 0019 — PINI composition as an e-class analysis

- **Status:** accepted
- **Date:** 2026-10-22
- **Deciders:** Shreyash Panigrahy

## Context

Exact checking enumerates every input, so it refuses circuits past `2**26`
points, and the shared-value layer's term extraction slows sharply with size.
Theory claim C5 showed why extraction must work on terms: with refresh in a
class, safety is not class-local. The masking literature has a composition
notion, PINI, under which any composition of PINI gadgets is secure. The
project has no time for the end-to-end Verilog pass, so this phase works on the
existing layer and fixtures only.

## Decision

Add `experiments/composition/`: an exhaustive 1-PINI checker for each gadget's
lowering (cross-checked with VerifMSI's PINI mode); an e-class analysis —
a class is *composable* if it holds a PINI node over composable children —
computed on the exported, saturated e-graph; and one-node-per-class extraction
restricted to PINI nodes. Security of its output rests on Cassiers &
Standaert's Properties 11 and 12 (`docs/adversarial-search-5.md`), recorded as
theory claim C9. Exact term extraction stays as the cheaper path where it fits.

## Consequences

- Circuits far beyond the exact range are handled in milliseconds (Keccak χ on
  a 32-bit row: a 2^128-point space), with VerifMSI's symbolic certificate as
  an independent check.
- Price: PINI gadgets cost more (HPC1 12 vs ISW 9), so composable circuits are
  costlier than the exact optimum (ISW chain 24 vs 18).
- The analysis runs after saturation in Python, not inside egglog.
- Glitch-free only; glitch-robust PINI needs registered gadgets (not modelled).
- **Cost of being wrong:** a gadget wrongly accepted as PINI would make every
  circuit using it falsely "secure". Mitigated by the exhaustive checker,
  VerifMSI agreement on every gadget, a soundness test on random PINI-only
  terms, and mutation-checked tests.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| SNI typing with refresh insertion (maskComp-style) | Needs refresh placement rules; PINI composes with no side conditions |
| Symbolic exact checker (BDD/ANF) | Still per-circuit; does not restore class-level extraction |
| Implement the analysis in egglog itself | Possible later; Python on the export is enough to test the idea |
| Phase A (Verilog front end) first | No time; Phase B works on existing material |

## Evidence

- `experiments/composition/RESULTS.md`, `test_composition.py`.
- `docs/adversarial-search-5.md` (Properties 11, 12 verified from the paper).
- `docs/theory.md` C9; `experiments/claims/test_claims.py::test_c9_*`.
