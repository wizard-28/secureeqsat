# Adversarial search #3 — attacking the *reframed* proposal

**Date:** 2026-10-06
**Target:** `docs/probing-secure-eqsat-proposal.md` revision 2 (the reframe in
`design/0010`), specifically its three novelty claims.
**Method:** two independent falsification passes (30+ query formulations each,
every hit fetched and verified) plus two new feasibility measurements. Query
lists are reproduced in each pass; the passes were run by separate agents and
their findings were spot-checked.

**Headline:** claim 1 (soundness) survives but must be sharpened and
disclaimed; claim 2 (repair) is partially anticipated by a 2026 paper and must
be reframed; **claim 3 (the re-sharing gap) is too strong as written and must be
rewritten** — the equivalence it describes is standard masking semantics, and
"cannot express" is false. A new scalability bottleneck was also measured.

---

## A. Claim 1 — "EqSat optimization of masked circuits is unsound"

**Verdict: survives in its EqSat-specific form; the surrounding phenomenon is
already known and must be disclaimed.**

No prior work applies cost-minimizing e-graph/equality-saturation optimization to
masked circuits, and none states the sharp point: that cost-minimal extraction
**systematically prefers** the insecure representative because it is cheaper.

But three adjacent works anticipate the *phenomenon*:

| Work | What it shows | Relation |
|---|---|---|
| **MaskedHLS** (Sarma, Thakur, Karfa, IEEE TCAD 2024, arXiv 2407.11806) | Conventional HLS/LLVM: **LLVM reassociation causes "incorrect recombination of shares"**, "result[ing] in an unmasked circuit"; expression balancing "hamper[s] the security of the masked circuit" | Closest same-mechanism hit — a *rewrite-style* optimizer producing a functionally correct but probing-insecure masked circuit. Conventional tools, not EqSat |
| **AI-driven optimization of masked gadgets** (Koblah et al., ePrint 2025/1190) | Conventional CAD (technology mapping, **FRAIG-based rewriting**, retiming) can produce functionally equivalent candidates that "**violate the conditions required for secure composition**"; they filter with VERICA | Shows rewriting breaks masking and needs an oracle; no e-graph, no systematicity claim |
| **SecCG** (Tsoupidi et al., arXiv 2207.02614) | Security-constrained codegen for masked code; quantified overhead "up to 7%" | Security-constrained cost optimization for masked code predates us |

**Required change.** Claim 1 becomes: *first to show the EqSat instantiation and
to quantify the systematicity* (the insecure representative wins on cost, on two
engines). Disclaim MaskedHLS, the FRAIG-CAD paper and SecCG explicitly. Without
this, a reviewer who knows the compiler-induced-leakage literature will judge the
finding obvious.

---

## B. Claim 2 — "security-constrained extraction is new"

**Verdict: partially anticipated; reframe as *semantic/hyperproperty* constraint,
and disclaim eVer.**

1. **eVer** (Gourjon, Orlt, Pauls, Treff, ePrint 2026/208 — the superVer
   group's successor) has crossed from verification into
   **security-preserving optimization**: it "optimize[s] out a superfluous
   sequence of refresh applications to improve performance and randomness
   consumption and **re-verif[ies]** security and correctness", and optimizes
   "the costly refresh gadgets". Mechanism: sound proof rules plus
   re-verification — **not** e-graph search or cost-driven extraction.

   Consequences: our "watch item" (superVer/eVer adds optimization) is now
   **triggered**; and our proposed R3 "refresh removal" route overlaps their
   headline optimization. The e-graph angle survives; "first to optimize refresh
   sequences" does not.

2. **Constrained extraction already exists** in forms other than cost:
   - acyclic constraints (He, Dong, Malik, Gupta, EGRAPHS 2023);
   - resource/sharing constraints (SkeleShare, CGO 2026).
   So the claim is **not** "first constrained extraction". It is: first to
   constrain extraction by a **semantic/hyperproperty** (probing security), and
   first to define the constraint's class/hyperproperty structure.

---

## C. Claim 3 — "the re-sharing gap" — **too strong, rewrite it**

Two independent attacks both land.

### C1. "Plain equality saturation cannot express them" is false as stated

Verified API facts: **egg** has `ConditionalApplier` and custom `Applier`s that
can inspect analysis data and insert new e-nodes; **egglog** rules carry
arbitrary Datalog premises, with `:when` guards; egglog-python exposes
`rewrite(...).to(..., *when)`. Guarded rewriting is available.

**The defensible core** is a congruence argument, not an expressiveness one:

> Re-sharing is **not a congruence of the wire-level Boolean term algebra**.
> `x0` and `x0 ⊕ r` are different functions, and that difference survives
> ordinary contexts. Since the semantics of an e-graph is a partial congruence
> relation, re-sharing cannot be the e-graph's *equality* relation, and no side
> condition repairs that. Guards control *when* an equality fires; they cannot
> make a non-equality into an equality.

This is now citable at theorem level: Suciu, Wang, Zhang, *Semantic foundations
of equality saturation*, ICDT 2025 (arXiv 2501.02413) establishes that an
e-graph's semantics is a partial congruence.

Required rewrite: from "EqSat cannot express re-sharing" to **"re-sharing is not
a congruence, so it cannot be the equality relation of a plain e-graph over the
wire-term algebra; guarded and dynamic rules do not repair that; expressing it
requires changing the representation or the theory."**

### C2. "Equivalence up to re-sharing" is standard masking semantics, not a discovery

The notion is basic, load-bearing vocabulary in masking, formalised years ago:

- **ISW** (CRYPTO 2003) already relies on re-randomised gadget outputs being
  *m*-wise independent even given the full input encoding.
- **Barthe et al., CCS 2016 (SNI)**: "inserting refreshing gadgets does not
  change the functional behavior"; probing security is itself defined as a
  **distributional equivalence**.
- **tightPROVE** (ASIACRYPT 2018) uses it as a reduction: its Game 2 `Flatten`
  replaces every multiplication/refresh gadget output with a fresh input sharing
  of the same value.
- Randomness reuse is an entire research line (COMAR / Feldtkeller et al.,
  TCHES 2022; **RNI-f**, Wang et al., TCHES 2022; graph-colouring randomness
  optimisation, ePrint 2025/2102).
- eVer's own keywords include "**probabilistic equivalence**".

Required rewrite: cite this lineage and state plainly that the equivalence is
**standard masking semantics**; what is new is only the *use* of re-sharing as
the e-graph **search relation for optimization** with security-constrained
extraction.

### C3. Precision problem found by the attack — the three optimizations are not one relation

- refresh insertion/removal = "same shared value, different shares";
- randomness reuse = a property of the **dependency/independence structure**;
- gadget substitution = implementation equivalence **under a composability
  discipline**.

Worse, "same decoded value" alone is **too coarse**: it would identify a secure
`(x0, x1)` with the insecure `(x, 0)` — exactly the unsoundness the project
found. Any usable relation must be **finer than the decode kernel and
security-aware** (e.g. tracking freshness and independence, as RNI-f does).

Required rewrite: stop calling the three optimizations one equivalence; state
the constraint on the relation (finer than the decode kernel, security-aware).

### C4. Prior art on richer-than-functional equivalence in e-graphs

Colored e-graphs (arXiv 2305.19203), constraint-aware/ASSUME e-graphs
(arXiv 2303.01839), and **e-graphs modulo theories** (Zucker, arXiv 2504.14340)
are precedent for equivalence beyond the syntactic. Also relevant: superVer
already puts **randomness and probabilistic independence** into an e-graph (for
verification). No work was found that makes re-sharing the search relation for
*optimization* — that specific combination appears open (medium confidence,
negative result).

*(Correction: an earlier internal note attributed "EqSat modulo theories" to
Koppel/Bhattacharyya. No such paper exists; the correct citation is Zucker,
arXiv 2504.14340.)*

---

## D. New feasibility measurements

**The search scales; the checker does not.** Both were run on this machine and
are reproducible from `experiments/egglog_port/`.

### D1. `egglog` saturation of chained gadgets (full rules, `run(4)`)

| Chain depth | AND nodes | XOR nodes | Time |
|---:|---:|---:|---:|
| 2 | 90 | 666 | < 0.01 s |
| 3 | 305 | 1,551 | < 0.01 s |
| 4 | 532 | 2,446 | < 0.01 s |
| 5 | 759 | 3,341 | < 0.01 s |

Node growth is ~linear in chain depth; saturation is instant through depth 5.
**The search-side scalability question is closed.**

### D2. In-house exhaustive checker cost (12 gates, 2 secrets, k randoms)

| Randoms | Time per check |
|---:|---:|
| 2 | 0.000 s |
| 6 | 0.004 s |
| 10 | 0.085 s |
| 12 | 0.376 s |
| 14 | 1.595 s |
| 16 | 6.717 s |

Cost doubles per additional random (the enumeration is `2^(free vars)`), and
**safety labelling calls the checker once per e-class**. A chain of depth 5 has
hundreds of classes and ~5 randoms plus 6 secrets, so labelling — not
saturation, not extraction — becomes the bottleneck first.

**Required change.** The proposal must name this: the next implementation task
is a **symbolic or lazy labeller** — VerifMSI as an external labelling oracle, an
ANF/BDD-based exact check, conservative structural pre-filters
(non-completeness/uniformity), and/or labelling only the extraction frontier on
demand. Without it the safety labelling does not scale past small gadgets.

---

## E. Resulting claim revisions (applied to the proposal)

| v2 claim | v3 claim |
|---|---|
| First to show EqSat optimization of masked circuits is unsound | First to show the **EqSat instantiation** and that the insecure representative is **systematically cheaper**; disclaim MaskedHLS, FRAIG-CAD, SecCG |
| First security-constrained extraction | First extraction constrained by a **semantic/hyperproperty**; disclaim eVer's refresh optimization and prior constrained-extraction work |
| EqSat cannot express re-sharing; the re-sharing gap is new | Re-sharing is **not a congruence**, so it cannot be an e-graph's equality relation; guards do not repair it. The equivalence itself is **standard masking semantics** (ISW/SNI/tightPROVE-Flatten/RNI-f); new is only its use as the **search relation** for optimization. The relation must be **finer than the decode kernel** |
| (unstated) | **New risk/next task:** safety labelling is the scalability bottleneck |

---

## F. Residual uncertainty

- Both passes are web-index-limited; paywalled 2026 venue papers could hide a
  collision. eVer was read via a mirror (ePrint's PDF is bot-blocked); its
  identity was verified from the ePrint abstract page.
- superVer remains unpublished (WIP talk); its characterisation rests on the
  official EGRAPHS listing.
- The "re-sharing-aware e-graph optimization is unclaimed" conclusion is a
  negative result at **medium** confidence.
- The scaling measurements are for 2-share, first-order, glitch-free circuits
  and one chain topology; they bound this configuration, not the field.
