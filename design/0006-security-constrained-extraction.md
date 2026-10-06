# 0006 — Security-constrained extraction design

- **Status:** accepted — **prototype implemented**
- **Date:** 2026-10-06
- **Deciders:** project team

## Context

The premise test established that cost-only extraction selects *cheaper* insecure circuits:
unrestricted rewriting with distributivity/factoring refolds shares, and the resulting
circuit materializes the unmasked secret (7 gates versus 8 for secure ISW AND). The failure
is systematic because the insecure circuit wins on cost.

The technical shape of the constraint:

- **First order (`t = 1`):** all terms in an e-class compute the same Boolean function, so
  safety — independence of the secrets under the masking distribution — is a property of the
  *class*, not of a particular term. A class can therefore be labelled safe or unsafe, and
  the constraint is: **do not materialize an unsafe class as an internal wire.**
- **Higher order (`t ≥ 2`):** joint independence is a property of *sets* of wires, i.e. a
  hyperproperty. It is not per-class and cannot be captured by a class label.
- Standard extraction (greedy DP, ILP) has no notion of security, and safety is neither a
  local nor a monotone cost, so it cannot be folded into a normal cost function.

## Decision

1. **First order — per-class admissibility.** Attach the safety label to each e-class and
   make extraction treat unsafe classes as inadmissible for internal materialization.
   Intended outputs (roots) are exempt; every other materialized class must be safe.
2. **`t ≥ 2` — lazy verify-and-refine (CEGIS-style separation oracle).** Extract the cheapest
   candidate satisfying all constraints discovered so far; run the exact checker; if it
   reports a violation, generate a blocking constraint (e.g. "these classes may not be
   materialized together") and re-extract; iterate to a bound. First-order extraction is the
   first iteration of this loop, so the two paths share an implementation.
3. **Cost model.** Weighted gate count (AND = 2, XOR = 1) plus fresh-randomness count; depth
   reported as a secondary metric. Weights are a parameter, recorded with every result.
4. **Acceptance.** A candidate is accepted only if it passes functional equivalence *and*
   the security oracle (which must itself be cross-validated per `design/0005`).

## Consequences

- This is the project's central algorithmic contribution and its main implementation work.
- Extraction is no longer a pure fixed-point DP once higher orders are in scope; it needs
  constraint generation, a bound, and reporting when no secure candidate is found.
- DAG-aware extraction remains NP-hard; limits and runtime reporting are required, not
  optional.
- If the lazy loop cannot find a secure candidate that beats the fixed-gadget baseline, that
  is a reportable null result and must be surfaced early (see `project_context.md` §6.3).
- Rule-level restriction (admitting only security-preserving rewrites) is deliberately *not*
  the primary mechanism, because it would discard the rewrites that create the optimization
  opportunities. It remains a fallback hybrid if the extraction loop proves too weak.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Encode safety in an e-class analysis | An `egg`-style analysis must be a per-class join-semilattice with cheap local merge. Safety is not locally composable, and for `t ≥ 2` it is not even per-class. |
| Extract, check, discard (post-hoc filter only) | No search guidance and no attribution of *which* term choices caused the violation. The lazy loop subsumes it — its first iteration is exactly extract-and-check. |
| Restrict the rule set to security-preserving rules only | Overly conservative as the sole mechanism; discards the refactoring opportunities that make the search worthwhile. Kept as a possible hybrid. |
| ILP extraction with security encoded as constraints | Joint independence has no compact linear encoding; would require the oracle as a separation cut anyway, which is the chosen lazy loop. |

## Evidence

- `experiments/premise_test/RESULTS.md` — the failure this design must prevent.
- `docs/probing-secure-eqsat-proposal.md` §10.3–10.5 — safety semantics and the algorithm.
- `design/0002` (scope), `design/0005` (trust boundary).

## Status updates

- **2026-10-06** — **Prototype implemented.** Per-class admissibility and
  security-constrained extraction work and recover a secure circuit from the
  insecure optimum (ISW AND: 7 gates insecure → 8 gates secure, price of
  security = 1 gate). The lazy separation oracle for `t ≥ 2` remains
  **unimplemented**. Separately, safety labelling is now the measured scalability
  bottleneck (`docs/adversarial-search-3.md` §D2, `project_context.md` §6.5).
  `experiments/constrained_extraction/`.
