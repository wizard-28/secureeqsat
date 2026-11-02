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

## Read in full (PDF supplied by the team, 21 pages, `2025-1190.pdf`)

- Title on the PDF: *Lightweight Masked Hardware Gadgets through Verification-aware Optimization*, the
  team's title; it is the 2026 revision of ePrint 2025/1190 (the abstract page I fetched earlier still
  showed the first title). **Resolved.**
- Method: NSGA-II genetic algorithm (DEAP) over a digraph of NanGate45 gates; sensitivity-guided
  single-point crossover; four mutation types; library-derived surrogate fitness (power, area, delay)
  correlated 0.87 / 0.81 with Design Compiler.
- Security: **PINI**, verified with **VERICA**, on the final candidates outside the search loop
  ("Candidates that fail verification are discarded"); during the search, functional equivalence
  (SAT/miter) and the surrogate are used. So PINI is checked on every *reported* result, not on every
  individual in every generation. The team's wording "checks every candidate" is therefore imprecise.
- Results: Table 6 (random mutation + tournament): power up to -15.2% (HPC3 AND), area up to -10.2%
  (HPC3 MUX), several entries positive (worse); conventional CAD (ABC fraig/retime) up to -43% (HPC2)
  and -60% (HPC3), only the PINI-secure ones reported. 32-bit AES: -12% power, -7.2% area after one
  gadget replacement (MSKregEn, 3 cells instead of 4); Skinny S-box area -5%.
- Scope: first order (two shares), COMAR/HPC1/HPC2/HPC3 gadgets from AGEMA, power and area only (latency
  and randomness are not objectives), gadget level, ASIC (NanGate45) only.

## Effect on our novelty boundary (confidence: medium)

Earlier text said no masking tool explores equivalent masked circuits by rewriting, and that this work is
the only approach that explores rewrites and checks every result. Both are too strong. Narrowed to: we
saturate an e-graph (all equivalent forms, not a sampled search), work at whole-program level, add a
value-level layer for re-sharing, and characterise unsafe extraction. Residual risk after reading the full text: low for the claims above; it works on library cells of single
gadgets, not on Boolean programs, and says so ("not to redesign the gadget logic at the Boolean or
architectural level").
