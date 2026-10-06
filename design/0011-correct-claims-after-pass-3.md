# 0011 — Correct the novelty claims after adversarial pass 3

- **Status:** accepted
- **Date:** 2026-10-06
- **Deciders:** Sourajyoti Basak

## Context

The third adversarial pass (`docs/adversarial-search-3.md`) attacked the v2
proposal's three novelty claims with two independent falsification passes (30+
query formulations each, every hit fetched) plus two new measurements. All three
claims needed surgery:

1. **Soundness claim survives, but the phenomenon is known next door.**
   **MaskedHLS** (TCAD 2024, arXiv 2407.11806) shows conventional HLS/LLVM
   reassociation causes "incorrect recombination of shares", "result[ing] in an
   unmasked circuit". A FRAIG-rewriting CAD paper (ePrint 2025/1190) shows
   functionally equivalent candidates that "violate the conditions required for
   secure composition", filtered with VERICA. **SecCG** does security-constrained
   codegen. What remains uniquely ours is the **EqSat instantiation plus the
   systematicity argument** — that the insecure representative wins *on cost*.
2. **The repair claim is partially anticipated.** **eVer** (ePrint 2026/208), the
   superVer group's successor, now optimizes away superfluous refresh sequences
   and optimizes refresh gadgets, re-verifying with its proof system. Our "watch
   item" is **realised**. Additionally, constrained extraction already exists
   (acyclic constraints, EGRAPHS 2023; SkeleShare, CGO 2026), so the claim must
   narrow to being constrained by a **semantic hyperproperty**.
3. **The re-sharing claim was too strong and partly a rediscovery.**
   "EqSat cannot express them" is **false**: `egg` has conditional/dynamic
   appliers and `egglog` rules carry `:when` guards. And "equivalence up to
   re-sharing" is **standard masking semantics** (ISW re-randomisation; SNI
   refresh; tightPROVE's `Flatten`; RNI-f; COMAR), not a new observation. The
   defensible core is a **congruence obstruction**: an e-graph's semantics is a
   partial congruence (Suciu, Wang, Zhang, ICDT 2025), and re-sharing is not a
   congruence of the wire-term algebra, so no guard repairs it. A precision
   correction also landed: the three optimizations are **not one relation**, and
   "same decoded value" is too coarse — it would identify secure `(x0, x1)` with
   insecure `(x, 0)`.

**New measurement (feasibility).** `egglog` saturation scales near-linearly
(chain depth 5: 759 AND / 3,341 XOR nodes, < 0.01 s), but the **safety labelling
is the bottleneck**: the exhaustive checker costs `2^(free vars)` and is called
once per e-class — 0.000 s at 2 randoms, **6.717 s at 16**.

## Decision

1. Adopt the corrected claims in the proposal (**v3**) and record the
   disclaimers: MaskedHLS, FRAIG-CAD, SecCG, eVer, prior constrained extraction,
   and the standard masking lineage for re-sharing.
2. State the re-sharing contribution as the **congruence obstruction and its
   consequence for e-graph search**, not as the discovery of the equivalence.
3. Add the **labelling bottleneck** as a first-class risk and make a
   symbolic/lazy labeller the top implementation task.
4. Reposition against eVer: claim the e-graph + congruence angle, never
   "optimize refreshes".

## Consequences

- The novelty claim is narrower but defensible; every surviving part is either
  verified experimentally or anchored in a published theorem.
- The payoff route (R3) is now known to overlap eVer's refresh optimisation;
  the distinctive part is doing it as an **e-graph search relation**, which
  requires solving the representation problem first.
- The next sprint has a concrete, measurable goal (labeller scaling) before any
  larger circuit work.
- Two claims move from "medium" to "high" confidence (congruence obstruction),
  and one from "medium" to "low" (labelling scalability).

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Keep the v2 claims | A reviewer would find MaskedHLS and eVer; the claims would not survive the room |
| Drop the re-sharing route entirely | The congruence framing is still novel and is the only identified payoff route; dropping it leaves only negative results |
| Keep "cannot express" and argue about guards | Factually wrong — the APIs were verified |
| Claim "first to optimize refresh sequences" | eVer already does, and by a sound method |

## Evidence

- `docs/adversarial-search-3.md` — the pass, its queries, and the measurements.
- `docs/probing-secure-eqsat-proposal.md` — v3 (claims, disclaimers, risks,
  Appendix B).
- `experiments/egglog_port/RESULTS.md` — search-side scaling.
