# 0010 — Reframe around soundness and the re-sharing gap

- **Status:** accepted
- **Date:** 2026-10-06
- **Deciders:** Sourajyoti Basak

## Context

The feasibility push (`docs/feasibility-report.md`) closed the trust boundary,
confirmed the premise on two independent engines, and implemented
security-constrained extraction. It also produced **negative results on the
original payoff hypothesis**:

- gadget scale: the constrained optimum is 8 gates — exactly the known ISW
  construction; the constraint costs a gate and buys nothing;
- chain scale: the unconstrained optimum is 14 gates and insecure, the
  hand-written composition is 16 gates and secure, and the **entire sampled
  k-best frontier was insecure**;
- the gate savings come from the same share-refolding mechanism as the
  security violation.

§6 of the report explains why: the optimizations the masking literature
actually exploits — refresh insertion/removal, randomness reuse, gadget
substitution (Tornado, AGEMA, COMPRESS, Feldtkeller et al.) — are **equivalences
up to re-sharing**, not Boolean equalities. Plain functional equality
saturation cannot express them, and actively prefers the one refactoring it can
express, which is the insecure one.

## Decision

Reframe the project's primary claim. Instead of "we use EqSat to find cheaper
secure masked circuits", lead with the three things the evidence supports:

1. **Soundness finding.** Unconstrained equality saturation is *unsound* for
   masked-circuit optimization, with a concrete mechanism (share refolding via
   distributivity), reproduced on two engines with identical leaking wires.
2. **Repair.** An exact first-order checker, independently cross-validated on
   21,760 wires with zero violations; per-class safety labelling; and
   security-constrained extraction that recovers a secure circuit from the
   insecure optimum.
3. **The re-sharing gap.** The optimizations worth having are not function
   equalities. Characterising the equivalence relation an e-graph would need in
   order to express them — and whether it can carry it — becomes the research
   question and the next work item.

The optimization payoff is demoted from *claim* to *open research question with
a named route*.

## Consequences

- The Review 1 novelty claim changes. `docs/probing-secure-eqsat-proposal.md`
  carries a revision note; its §10 mechanism, §11 novelty boundaries and the
  trust-boundary material remain valid.
- Deliverables already in hand are unaffected and verified: checker, cross-check,
  constrained extraction, two-engine reproduction, scalability answer.
- New work item with the highest leverage: model **re-sharing equivalence** —
  refresh as a first-class rewrite with randomness side conditions — since that
  is the only identified route to genuine optimization gains.
- Risk register updated: payoff risk moves from "unknown" to "high, explained,
  with a proposed route".
- A reviewer can now be told a coherent story: we found the unsoundness, we can
  repair it, and we can say precisely why the payoff is hard and where it must
  come from.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Keep pitching the optimization payoff | The evidence contradicts it; a reviewer running the same experiments would find the same thing |
| Abandon the direction | The mechanics all work and the soundness finding is novel; abandoning verified results would be wasteful |
| Pivot to another problem | The alternative search was exhaustive (`docs/adversarial-search-2.md`); nothing else combined novelty with feasible prototyping |
| Withhold the negative results | Dishonest, and they are the most interesting thing we have |

## Evidence

- `docs/feasibility-report.md` — consolidated checks and confidence levels.
- `experiments/premise_test/RESULTS.md`, `experiments/oracle_crosscheck/RESULTS.md`,
  `experiments/egglog_port/RESULTS.md`.
- `design/0005` (trust boundary), `design/0006` (constrained extraction),
  `design/0009` (engine check).
