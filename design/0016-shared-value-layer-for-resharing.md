# 0016 — A shared-value layer for re-sharing equivalences

- **Status:** accepted
- **Date:** 2026-10-11
- **Deciders:** Shreyash Panigrahy (team decision: option A, cost 1 random = 1 gate, include HPC)

## Context

`design/0010` and `design/0011` made the re-sharing gap the research question:
refresh insertion/removal (R3) and gadget substitution (R2) relate circuits
that reconstruct the same value through *different shares*, so they are not
equalities of the wire-term algebra and the existing e-graph cannot hold them.
ISW and DOM, for example, compute the same shared product but different first
shares (`a0&b0 ^ r` vs `a0&b0 ^ a0&b1 ^ r`). Tasks "re-sharing rules" and
"gadget equivalences with ablations" are therefore one representation problem.

## Decision

Add a second e-graph layer whose sort `S` stands for a *sharing* and whose
e-classes are equal iff they reconstruct the same unmasked value. Operators are
shared inputs, share-wise XOR, `refresh`, and the AND gadgets `isw`, `dom`,
`hpc1`. R1 (Boolean identities on values), R2 (`isw = dom = hpc1`) and R3
(`refresh(x) = x`, seeded at gadget inputs) are ordinary egglog rules there.
Shares exist only after extraction, when a term is *lowered* to a wire circuit
with a fresh random per gadget instance. Safety is checked on the lowered
circuit with the bitsliced labeller (`design/0015`), and extraction is
occurrence-aware and term-based, with leaking subterms cut. Cost is gates +
randoms, one each.

## Consequences

- R2 and R3 become expressible, and value-level distributivity — the rule that
  leaks at the wire level — becomes safe to apply (`experiments/resharing`).
- Safety is no longer a per-class label: every `S` class carries a secret. It is
  a property of a lowered term, so constrained extraction enumerates terms
  (k-best per class, exact lowered cost, monotone leak cut). This is the new
  scalability limit: ~150 s at chain depth 5.
- Class-based (one node per class) extraction cannot express a needed refresh,
  because `x` and `refresh(x)` share a class; occurrence-aware extraction is
  required, not an optimisation.
- Relies on egglog's private `EGraph._serialize` to read classes back; pinned by
  `uv.lock` (egglog 14.0.0) and guarded by a format test. No new dependency.
- Glitch-free model only. HPC1's purpose (glitch robustness) is invisible here,
  so an R2 swap away from HPC1 is "free" in this model and not in hardware.
  Results involving HPC must carry that caveat. HPC2 is not modelled: its share
  equations were not fetched (UNVERIFIED).
- **Cost of being wrong:** a lowering bug would make the layer optimise a
  circuit other than the one reported. Mitigated by a reconstruction test over
  every assignment, mutation-checked tests, and a VerifMSI cross-check of every
  reported lowered circuit.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Option B: stay at wire level with an opaque `Refresh` node and a side relation of re-sharings | Ad hoc; reimplements a value-level union-find outside the e-graph |
| Randoms as named term arguments | Insertion needs fresh names inside rewriting; reuse already measured to leak on the chain |
| One node per class (standard DAG extraction) at the value layer | Cannot express `isw(x, refresh(x))` when both operands are one class |
| Extend the in-house harness | `AGENTS.md`: the minimal e-graph is a test harness, not the product |

## Evidence

- `experiments/resharing/RESULTS.md` — ablation, stability, cross-check, scale.
- `experiments/resharing/test_resharing.py` — headline results asserted.
- HPC1 description: P. Knichel, A. Moradi, *Low-Latency Hardware Private
  Circuits*, CCS 2022, §4.1 and Table 1 (fetched 2026-10-11): "a DOM-AND gadget
  and additionally refreshing one of the inputs", 2 random bits at first order.
