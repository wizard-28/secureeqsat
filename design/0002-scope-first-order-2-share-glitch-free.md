# 0002 — Scope: first order, 2 shares, straight-line, glitch-free

- **Status:** superseded by 0018 (glitch-free-only restriction)
- **Date:** 2026-10-06
- **Deciders:** project team

## Context

Masking has a large design space: number of shares (order), composability notions
(NI / SNI / PINI), and leakage models (glitch-free probing, robust probing with glitches,
random probing). The literature's state of the art targets higher-order, glitch-robust,
composable constructions. The project needs a scope that is (a) tractable for a
gadget-scale prototype and (b) still a real fragment of the problem, so that results
transfer rather than trivialize.

The key structural fact that makes first order attractive: **first-order safety is a
per-e-class property**. Since all terms in an e-class compute the same Boolean function,
and first-order safety is a property of that function under the masking distribution, a
class can be labelled safe or unsafe directly. At `t ≥ 2`, joint independence is a property
of *sets* of wires — a hyperproperty — and is not per-class. That is a genuinely harder
algorithmic problem and is deferred.

## Decision

The core of the project is: **first-order (`t = 1`) probing security, 2 shares, straight-line
Boolean circuits, glitch-free leakage model.** Higher orders and robust/PINI composability
are explicitly stretch scope, and the system's rule taxonomy must not preclude them.

## Consequences

- The checker is small and exhaustively implementable (validated — see ADR 0005).
- **No claim about robust probing, glitches, PINI, or higher orders may be made from this
  code.** The evaluation section must say so.
- Higher-order extraction is designed for but not implemented (ADR 0006's lazy separation
  oracle is the planned path).
- A reviewer will ask "what about glitches?" — the answer is a scope statement, not a claim.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Start at higher order (`t ≥ 2`) | Checker and extraction both harder; premise already demonstrable at `t = 1`; risks the timeline |
| Robust/glitch-extended probing from the start | Different probe units (gate input cones); distracts from the extraction problem |
| Random probing / RPC | Different security notion; the composition story is heavier |

## Evidence

- `experiments/premise_test/masked.py` — the first-order checker.
- `experiments/premise_test/RESULTS.md` — checker validated on secure and insecure fixtures.
- `docs/probing-secure-eqsat-proposal.md` §10.3 — the per-class vs hyperproperty framing.
