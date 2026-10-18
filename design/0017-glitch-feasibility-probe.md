# 0017 — Feasibility probe: glitch-extended probing

- **Status:** accepted (probe only; does not change the core scope of `0002`)
- **Date:** 2026-10-18
- **Deciders:** Shreyash Panigrahy

## Context

`design/0002` fixes the core scope as first order, 2 shares, glitch-free. That
is the model reviewers treat as a toy: real masked hardware is evaluated with
glitches, where a probe on a combinational wire reveals every *stable* signal
(primary input or register output) feeding it. The project is now solo and
aiming at a workshop paper; extending to glitches would make the paper
stronger, and a register is structurally like a refresh — it keeps the value
and changes what a probe sees — so the shared-value representation
(`design/0016`) may carry over. Before committing to that, a one-step go/no-go:
does the soundness/repair story survive the glitch model at all?

## Decision

Run a bounded feasibility probe in `experiments/glitch_probe/`, without
changing the core scope:

- an in-house glitch-extended first-order checker (joint distribution of each
  wire's stable-input set, bitsliced);
- an independent VerifMSI glitch driver: circuits built with VerifMSI's own
  `Gate`/`Register` elements, so the leakage sets come from its implementation,
  checked exactly with `getDistribWithExev` and also with its `checkSecurity`;
- egglog rewriting of register-annotated gadgets with registers either opaque
  or transparent (`reg(x) = x`), then unconstrained extraction and a k-best
  search for the cheapest glitch-secure variant.

**Go** if the checker agrees with VerifMSI and the premise reproduces under
glitches (some cost-preferred rewrite breaks glitch security and a constrained
search recovers a secure circuit). Otherwise stay with the glitch-free paper.

## Consequences

- No glitch-model claim may be made until the cross-check passes; results are
  marked as a probe.
- Glitch-extended safety depends on the stable-input set of a wire's cone, not
  only on its function, so it is **not** a per-class property even at the wire
  level. That is expected and part of what the probe tests.
- If go, a follow-up ADR changes the scope of `0002`.
- **Cost of being wrong:** a wrong glitch semantics would misclassify circuits;
  mitigated by deriving the oracle's leakage sets from VerifMSI's own
  implementation rather than from ours.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Change the scope now | Unknown whether the story survives; a probe is cheaper than a rewrite of the scope |
| Use only VerifMSI's `checkSecurity` | Its TPS check is sound but incomplete (conservative alarms), and it reports counts, not per-probe verdicts |
| Skip the probe, write the glitch-free paper | Leaves the reviewers' first question unanswered |

## Evidence

- VerifMSI `hw.py` (local clone, read 2026-10-18): `Register` resets
  `leakageOut` to its input's expression; gates take the union of their inputs'
  `leakageOut`; `checkSecurity(order, withGlitches, prop, ...)`.
- VerifMSI `benchmarks/dom_and/generate_dom_and.py`: register-annotated DOM.
- `experiments/glitch_probe/RESULTS.md` (this probe).
