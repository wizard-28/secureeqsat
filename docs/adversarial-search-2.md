# Adversarial search #2 — attacking the constant-time / equality-saturation survivor

Scope: a second, adversarial pass on the one direction that survived the first search
(`docs/adversarial-search.md` §19–§20, "security/CT-constrained EqSat"). This pass attacks
both **novelty** and **feasibility**, and it attacks the present author's own earlier
recommendation as hard as it attacks the original document.

Method: direct verification of every load-bearing citation by fetching the source, plus
targeted novelty searches through the cryptography, side-channel, information-flow, and
e-graph literatures. Every claim below is tagged with what was actually checked.

Confidence note up front: no literature search establishes novelty with certainty. What
follows uses verified citations and explicitly states residual risk. Where a claim could
not be made airtight, it is flagged rather than smoothed over.

---

## Executive verdict

**Correction to the first pass.** The first adversarial search scored the CT/security
direction at novelty 6–7 / feasibility 3 and listed it as one of two survivors. A second
pass revises this downward:

| | First pass | This pass |
|---|---:|---:|
| Novelty | 6–7 | **4** |
| Feasibility | 3 | **3** |
| 7-week scope | "TOO HARD" | **still too hard; one-night 30% is not possible for the full claim** |

The core gap is real: *no prior work places non-interference inside an equality-saturation
substrate*. But three discoveries materially weaken it, and one of them is a genuine
feasibility kill for the framing proposed in the first pass.

---

## 1. Cryptonite already runs equality saturation on cryptographic primitives

**Cryptonite: Scalable Accelerator Design for Cryptographic Primitives and Algorithms**
(arXiv 2505.14657) builds an "E-graph Loop Synthesizer" that performs egg-based equality
saturation directly on **straight-line cryptographic kernels from Fiat Cryptography** —
the same Curve25519 / secp256k1 family the first pass proposed as the "nobody has touched
this" domain.

The first pass's central argument was:

> Cryptographic arithmetic kernels are straight-line bitvector expressions — no memory, no
> aliasing, no control flow — so EqSat is *natively adequate* there, unlike general compiler
> IR. That is the unoccupied, feasible corner.

Cryptonite is published evidence that this is not an unoccupied observation; it is someone
else's implemented design choice. Worse, Cryptonite explicitly discusses the security
property:

> "The aforementioned hardware implementation explorer ensures that critical properties of
> the original code, particularly those related to **constant-time arithmetic**, manual
> carry propagation, ambiguity in bit widths, and lack of variable loop bounds, are
> preserved… It avoids introducing control-flow variability, operator widening, or replacing
> masking logic with more complex arithmetic. By retaining these properties, the
> transformations applied by the explorer remain potentially side-channel resistant."

The escape hatch is a single sentence — Cryptonite says "side-channel resistance is not the
primary focus of this work." But the domain-alignment insight, which was the strongest part
of the first pass's novelty argument, now belongs to Cryptonite's design rationale.

**Novelty impact: significant.**

## 2. The "CT inside the substrate" mechanism is vacuous as stated

This is the feasibility kill, and it is an abstraction-level problem, not an engineering
problem.

Constant-time is a property of **control flow and memory addresses**. A straight-line
bitvector e-graph term contains **neither**. Consequently:

- A taint / information-flow constraint attached to e-graph terms via an e-class analysis
  has nothing to constrain. Every term passes, because nothing branches and nothing indexes
  at that level.
- The leakage that CT is meant to exclude appears only at **lowering**: integer division
  (`x / y`), variable shifts by secret amounts, carry handling, register spills.
- These are properties of the **lowering function**, not of the term. They cannot be
  observed by inspecting the e-graph term alone.

Therefore the first pass's formulation —

> "candidate rewrites are admitted only if verified leakage-preserving, and the extractor
> minimizes cost subject to that constraint… non-interference becomes part of the
> saturation substrate"

— is not implementable in the form stated. Any implementation must smuggle the lowering
relation into the picture, at which point the constraint is no longer a property *of the
e-graph*.

### The only two architectures

**(A) Per-rule admissibility.** For each candidate rewrite rule ℓ→r, lower both sides to a
target and check that the leakage profiles agree. The rule set is finite, so this is
tractable. CT then holds *compositionally* over admitted rules. This is exactly CryptOpt's
architecture (verify the transformation; do not trust the search), applied to a different
search method.

- Viable, but the mechanism is a **rule filter**, not a substrate property. The novel
  contribution shrinks to "we filtered a rule set with a CT oracle before saturating."

**(B) Put the target inside the e-graph.** Add target instructions to the rewrite language
so the constraint becomes internally expressible — but then EqSat runs over x86-64 with
memory, flags, and aliasing, i.e. precisely the intractable representation problem the
first search identified. And one competes directly with CryptOpt's Coq-verified checker.

- Not viable in the timeframe.

**Only (A) survives. The novelty claim must be restated as a compositional admission
predicate over a rule set, not as non-interference inside the substrate.**

## 3. "Verified" in the title is not supportable with the described tooling

The first pass proposed the title *Non-Interference-Constrained Equality Saturation:
**Verified** Constant-Time Optimization*. That word cannot be defended with the tooling the
project document lists (TIMECOP, Binsec/Rel2, ct-fuzz):

- **TIMECOP** is dynamic, statistical taint analysis. It produces evidence, not a proof.
- **Binsec/Rel2** is static binary analysis — closer, but applying it per-candidate-rule over
  generated code fragments is a research project of its own.
- **ct-fuzz** is a testing tool by construction.

Realistic oracles for per-rule CT checking are **ct-verif** (LLVM-based, models value/control/
memory taint) and **CtChecker** (ECOOP 2024, PDG/constraint-based, sound). Note that
CtChecker already contains the concept of **declassification via a whitelist** — i.e. prior
art for "which derived values are permitted to be public," which overlaps with "which
rewrites are CT-admissible."

Either the title drops "verified" (empirical validation only), or the project commits to a
mechanized artifact. Neither is a tonight problem, but the title must not overclaim for
review 1.

## 4. The generic mechanism was already in egg

egg's **e-class analyses** (Willsey et al., POPL 2021) are a general mechanism for attaching
semilattice-valued facts to e-classes. The egg paper explicitly states that analysis data may
"inform how or if rewrites apply their right-hand sides, or determine the cost of terms
during the extraction process," and even formulates extraction itself as an e-class analysis.

So the *mechanism* needed to attach any constraint to an e-graph has existed since 2021 and
is documented for exactly these two uses. Combined with §2, architecture (A) does not even
use it — the CT check happens outside the e-graph, on rule candidates. This removes the last
piece of "novel mechanism" from the proposal.

## 5. Positioning risk: the constraint may not bind, and the baseline is hand-tuned assembly

Two independent risks that the first pass did not weigh:

1. **The constraint may bind on almost nothing.** Hand-written cryptographic arithmetic is
   already CT-disciplined by construction. If nearly every performance-relevant rewrite is
   already CT-safe, the constraint filters almost nothing, and the contribution reduces to a
   null result. A null result is publishable *if framed as a finding* — but it is not a
   system.
2. **The performance baseline is hand-tuned assembly.** CryptOpt reports that standalone,
   against hand-optimized libsecp256k1 assembly, it achieves only ~1.04×. CryptOpt's large
   speedups (1.74× over GCC) come from the verified pipeline relative to *compilers*, not
   relative to experts. An EqSat-based optimizer in this domain is competing against the
   domain's own best-in-class hand tuning, using a weaker search method, while carrying an
   extra constraint. It may simply lose.

## 6. Revised scorecard

| Proposed direction | Novelty | Depth | Feasibility | One-night 30% | Verdict |
|---|---:|---:|---:|---:|---|
| CT-constrained EqSat, "substrate" framing | 4 | 7 | 3 | No | ❌ abstraction-level kill |
| CT-constrained EqSat, architecture (A) | 4 | 5 | 4 | No | ⚠️ salvageable only as rule-filter study; best of a bad set but not 6/10 |
| CryptOpt/Cryptonite differentiation study | 3 | 4 | 6 | Partial | ❌ not enough |
| §5.9 guide-ablation study | 4–5 | 5 | 8 | Yes | ⚠️ only high-feasibility item; low novelty |

## 7. What survives, stated honestly

The only defensible version of this direction is:

> **Constant-time-preserving equality saturation for cryptographic arithmetic kernels,**
> where CT admissibility is enforced as a **compositional predicate over the admitted rule
> set** (architecture A), validated empirically with existing CT tooling, and evaluated on
> whether the CT constraint changes the extracted program at all relative to unconstrained
> EqSat.

- Do **not** claim non-interference inside the substrate.
- Do **not** claim verified / mechanized guarantees.
- Always cite **CryptOpt** (e-graph in its verified equivalence checker; randomized search;
  functional correctness only) and **Cryptonite** (egg EqSat on straight-line Fiat crypto;
  CT related properties preserved but not optimized for).
- The falsifiable hypothesis is: *how often does the CT constraint bind, and what is the
  cost of the security constraint when it does?*

## 8. Residual uncertainty

- Whether Cryptonite's loop synthesis actually *changes* the CT profile of the kernels in a
  way that would have made a CT constraint bind is **not determined here** — the paper
  claims preservation, not optimization. Reading Cryptonite in full could move the verdict
  in either direction.
- Whether an inexpensive, per-rule CT oracle can be assembled from the project's existing
  tooling was **not** established here; it is the single largest feasibility unknown.
- Absence of prior art for "non-interference as an e-graph constraint" was checked across
  the e-graph, information-flow, and side-channel literatures; it is a negative result and
  therefore has the usual limits of negative search.

## References

- Cryptonite, arXiv 2505.14657 — EqSat loop synthesis over straight-line Fiat crypto kernels.
- CryptOpt, PLDI 2023, arXiv 2211.10665 — verified compilation via randomized search;
  e-graph used inside the Coq-verified equivalence checker (verified by full-text fetch).
- Kuepper et al., PLDI 2023, DOI 10.1145/3591272.
- Willsey et al., *egg: Fast and Extensible Equality Saturation*, POPL 2021 — e-class
  analyses (verified by full-text fetch).
- CtChecker, ECOOP 2024 — sound CT analysis with declassification/whitelisting.
- Abate et al., *An Extended Account of Trace-relating Compiler Correctness and Secure
  Compilation*, TOPLAS 2021, DOI 10.1145/3460860 — resolves to a survey, **not** a CT
  preservation theorem (correction to the first search's citation [17]).
- Barthe et al., *Formal Verification of a Constant-Time Preserving C Compiler*, ITP 2020 —
  the correct citation for the CT-preserving CompCert result.
