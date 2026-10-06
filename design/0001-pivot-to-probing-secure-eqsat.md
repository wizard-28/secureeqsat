# 0001 — Pivot to probing-secure equality saturation

- **Status:** accepted
- **Date:** 2026-10-06
- **Deciders:** project team (pending confirmation; briefing circulated)

## Context

The original project was *LLM/agent-guided equality saturation and superoptimization*
(`docs/original/`): replace human-written guides in Guided Equality Saturation with
LLM/ML guidance, ultimately on real compiler IR. Two adversarial passes established that
this is dead:

1. The core framing is occupied — ML-Guided Equality Saturation (EGRAPHS 2025) states the
   goal of replacing expert guides with a learned model; LGuess (arXiv 2511.00403)
   implements the LLM-checkpoint pattern exactly; EggMind (arXiv 2604.17364) occupies
   strategy synthesis.
2. The two fallback survivors from the first adversarial search are occupied — a learned
   stop/continue controller is Omelette (Cambridge MPhil, 2022, explicit `end` action);
   guide-usefulness prediction is EggMind's tractability guidance.
3. The security/constant-time niche (§5.7) was rated highest by the first search and fails
   on both axes: Cryptonite (arXiv 2505.14657) already runs egg-based EqSat on the same
   Fiat crypto kernels, and the abstraction level is wrong — constant-time is a property of
   control flow and memory addresses, which straight-line e-graph terms do not have, making
   a term-level constraint vacuous.
4. The plan's own phases sum to ≥11 weeks before contingency.

What survives is a different use of the same machinery: masked cryptographic circuits are
straight-line Boolean circuits (the native EqSat domain), and the security property there
is a genuine, checkable constraint on intermediates rather than a vacuous one.

## Decision

Adopt **probing-secure equality saturation (SecureEqSat)**: use equality saturation to
optimize masked circuits under a first-order probing-security constraint, and treat
**security-constrained extraction** as the core research problem.

We explicitly claim only the *optimization* problem. superVer (EGRAPHS 2024) already uses
e-graphs to *verify* probing security; masked-circuit optimizers (Rosita, Eldib & Wang,
AGEMA, COMPRESS, Feldtkeller et al., TETRIS, Tornado) exist without e-graphs. The
intersection — search/extraction under the constraint — is the gap.

## Consequences

- The project now depends on a **security checker we must own and validate**, which creates
  a trust boundary (see ADR 0005). This is the main new risk.
- Novelty is assessed at ~6/10, with superVer's group as the main monitoring risk.
- A null result is possible: the constraint may leave little optimization freedom. The
  evaluation plan must surface this early rather than at write-up.
- The team's existing EqSat reading and side-channel background remain relevant; the pivot
  is a repositioning, not a restart.
- The original direction is closed. Rebuilding an EqSat prototype for general compiler IR
  is explicitly discouraged (`AGENTS.md` §9).

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Continue the original LLM-guided EqSat plan | Occupied on every sub-direction; ~4/10 novelty, infeasible schedule |
| Constant-time-constrained EqSat on LLVM/MLIR | Abstractions mismatch (vacuous constraint) + Cryptonite collision + crowded field |
| Budget-aware differential-privacy compiler | Feasible (~9) but novelty ~5; contested by DPella/APEx/DPack |
| Sparse tensor layout-conflict scheduling | Closed Sept 2026 by SparseConflicts (same group that owns the area) |
| Compiler-only intermittent checkpointing | Closed Oct 2026 by Bao (arXiv 2610.02426) |
| Linear-layout extension | Owned by the Triton/OpenAI group; remaining gap staked as their future work |

## Evidence

- `docs/adversarial-search-2.md` — second adversarial pass, revises CT/EqSat to 4/10
  novelty, 3/10 feasibility.
- `docs/team-briefing-plan-a.md` — full argument with verified citations.
- `docs/probing-secure-eqsat-proposal.md` — Plan A proposal, prior-art matrix.
- Premise validation: `experiments/premise_test/RESULTS.md`.
