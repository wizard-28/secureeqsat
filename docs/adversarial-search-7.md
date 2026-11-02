# Adversarial search 7: search-based gadget optimisation (Koblah et al.)

Date: 2026-11-02. Trigger: a team member named "Koblah et al. (2026), *Lightweight masked
hardware gadgets through verification-aware optimization*", an evolutionary search over masked
gadget variants that checks each candidate with PINI verification and keeps the smaller secure ones.

## Queries run (web search; US-only index)

1. `Koblah "Lightweight masked hardware gadgets through verification-aware optimization"` : no exact match.
2. `Koblah masked gadgets evolutionary search PINI verification lightweight eprint 2026` : found ePrint 2025/1190.
3. `"verification-aware optimization" masked hardware gadgets lightweight Koblah Forte Ganji` : no exact match.

## What was verified by direct fetch (eprint.iacr.org/2025/1190, abstract page)

- Title: *Towards AI-driven Optimization of Robust Probing Model-compliant Masked Hardware Gadgets
  Using Evolutionary Algorithms*. Authors: D. S. Koblah, D. M. Mehta, N. Poch, M. Hashemi,
  F. Ganji, D. Forte. Received 2025-06-25, latest revision 2026-08-21. Preprint, no venue listed.
- Evolutionary algorithm with circuit-specific mutation and crossover over gate-level realisations;
  objectives power and area; functional equivalence and probing-model compliance checked;
  security-preserving reductions up to 15% in selected cases; conventional CAD (technology mapping,
  FRAIG rewriting, retiming) sometimes gives up to 60% but is "not systematic" under masking constraints.

## Not verified

- The title quoted by the team (*Lightweight masked hardware gadgets ...*) was not found; it may be a
  later title of the same work or a different paper. **UNVERIFIED.**
- That every candidate is checked with **PINI** verification: the abstract names no security notion or
  verifier ("industry-standard ... pre-silicon side-channel verification tools"). The PDF returned HTTP
  403, so the full text was not read. **UNVERIFIED.**
- Whether smaller secure variants are "kept" by a fixed rule; the abstract says only that the search
  produces security-preserving designs.

## Effect on our novelty boundary (confidence: medium)

Earlier text said no masking tool explores equivalent masked circuits by rewriting, and that this work is
the only approach that explores rewrites and checks every result. Both are too strong. Narrowed to: we
saturate an e-graph (all equivalent forms, not a sampled search), work at whole-program level, add a
value-level layer for re-sharing, and characterise unsafe extraction. Residual risk: the full text may
show a closer overlap (for example a verification-guided search at program level). Read it before
submission.
