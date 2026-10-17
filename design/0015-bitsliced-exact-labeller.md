# 0015 — Bitsliced exact labeller for safety labelling

- **Status:** accepted
- **Date:** 2026-10-07
- **Deciders:** Shreyash Panigrahy

## Context

`docs/adversarial-search-3.md` §D2 measured safety labelling as the scalability
bottleneck: the reference checker costs `2^(free vars)` per call (6.7 s at 16
randoms), and `class_safety` materialised a circuit and called it once per
e-class. `design/0011` made a symbolic or lazy labeller the top implementation
task, listing four routes: VerifMSI as an external labelling oracle, an
ANF/BDD-based exact check, conservative structural pre-filters, and labelling
only the extraction frontier on demand.

Much of the measured cost was not inherent to the exhaustive method but to its
implementation — one Python `evaluate()` per assignment, repeated per class.

## Decision

Replace the labelling implementation with a **bitsliced exact labeller**
(`experiments/labeller/`): each wire or e-class holds its Boolean function as
one truth table packed into a Python int, AND/XOR are bitwise operations, and
safety is a per-secret-block `bit_count()` comparison. `constrained.class_safety`
delegates to it; the original is kept as `class_safety_reference`.

The security model and the verdicts are **unchanged**. The labeller is added to
the trust boundary (`design/0005`) as RULE 1b of the VerifMSI cross-check rather
than trusted by transitivity. The four symbolic/lazy routes are **deferred**
until a benchmark exceeds the bitsliced labeller's range.

## Consequences

- Labelling a depth-5 chain e-graph (17 bits, 4,315 classes) takes ~0.4 s
  against an estimated ~50 min for the reference; in-house saturation now
  dominates (`experiments/labeller/RESULTS.md`).
- Stays stdlib-only, so no runtime dependency and no new ADR for one.
- Free soundness check: a merge whose nodes compute different functions raises
  `InconsistentClassError`.
- **Still exponential.** Spaces above `2**26` are refused; a masked S-box with
  dozens of randoms is out of range. The symbolic route remains a planned task,
  now gated on a benchmark that needs it.
- Callers must pass randoms (not all free variables) to `class_safety`;
  duplicates are rejected instead of silently costing time.
- **Cost of being wrong:** a labeller bug would mislabel classes and let
  constrained extraction emit a leaking circuit. Mitigated by identical verdicts
  against the reference checker, the reference labeller and VerifMSI's exact
  function (1,265 circuits / 22,463 wires, 0 violations), and by mutation-checked
  tests.

## Alternatives considered

| Alternative | Why rejected (for now) |
|---|---|
| VerifMSI as an external labelling oracle | One subprocess per class; GPL boundary; exact mode is itself exhaustive. Kept as the cross-check, not the labeller |
| ANF/BDD-based exact check | Needs a dependency or substantial new code; not needed at current benchmark sizes |
| Conservative structural pre-filters | Sound but incomplete — mislabels safe classes as unsafe; useful later as a fast path |
| Label only the extraction frontier on demand | Changes the extraction algorithm; unnecessary once labelling every class is sub-second |
| Keep the reference labeller | ~50 min at depth 5; blocks every circuit beyond small gadgets |

## Evidence

- `experiments/labeller/RESULTS.md` — agreement tables, timings, raw output.
- `experiments/labeller/test_labeller.py` — agreement and error-path tests.
- `experiments/oracle_crosscheck/crosscheck.py` — RULE 1b, rerun on the full set.
- `docs/adversarial-search-3.md` §D2 — the bottleneck measurement.
