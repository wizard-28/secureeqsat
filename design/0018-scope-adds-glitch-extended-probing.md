# 0018 — Scope: add the glitch-extended probing model; target a workshop paper

- **Status:** accepted
- **Date:** 2026-10-18
- **Deciders:** Shreyash Panigrahy
- **Supersedes:** the glitch-free-only restriction of `0002`

## Context

The project is now solo and its deliverable is a short theory-plus-negative-
results paper for an e-graphs venue (EGRAPHS workshop class), not an
optimizer. `0002` limited the core to the glitch-free model, which reviewers
of hardware masking treat as a toy. The probe in `0017` showed that the
glitch-extended model fits the existing machinery with only the checker
swapped: a register keeps a value and changes what a probe sees, exactly like
a refresh, and the occurrence-aware extraction of `0016` handles both.

## Decision

The core scope becomes: **first order, 2 shares, straight-line circuits, in
two leakage models — glitch-free and glitch-extended (robust probing with
glitches; registers as glitch barriers, no timing semantics).** The paper's
central result is stated once for both models, for any *value-preserving,
leakage-changing* operator (refresh, register): `docs/theory.md`, with every
claim tied to an executable witness in `experiments/claims/`.

## Consequences

- Glitch-model claims are allowed, but only with the VerifMSI glitch
  cross-check (`experiments/glitch_probe/glitch_driver.py`), as `0005`
  requires for the glitch-free model.
- In the glitch model, safety is **not** a function of a wire's Boolean
  function, so the per-class wire-level repair of `0006` holds for the
  glitch-free model only. The glitch model needs term-based extraction even at
  the wire level.
- Still out of scope: higher orders, more than 2 shares, PINI/SNI composition,
  transitions and coupling, timing/latency of registers, random probing.
- Payoff work (randomness reuse, generator post-pass) stays future work.
- **Cost of being wrong:** a mis-stated lemma would sink the paper's core;
  mitigated by tying each claim to a test witness and keeping the proofs in a
  form the author must check line by line.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Keep glitch-free only (`0002`) | Weakest model; first question any reviewer asks |
| Go to higher order / PINI as well | Set-valued probing and composition; not feasible solo in the time available |
| Pursue gains (randomness, generator outputs) first | No evidence yet of gains; the theory is supported now |

## Evidence

- `design/0017`, `experiments/glitch_probe/RESULTS.md` (167 probes, 0
  disagreements with VerifMSI; opaque vs transparent registers; repair by
  register placement).
- `design/0016`, `experiments/resharing/RESULTS.md` (refresh as a self-loop;
  occurrence-aware extraction).
