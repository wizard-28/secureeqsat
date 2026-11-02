# Adversarial search 6 — novelty re-check of claims A–F

**Date:** 2026-10-25. **Method:** four independent search agents, each told to try to *defeat* the
claims, with web search and page fetches. Citations below are marked by how much was read.
Nothing in this pass has been reviewed by the human team; under `AGENTS.md` §11 the final
novelty wording is theirs to decide.

**Reading status legend:** `full` = full text read; `abstract` = abstract or listing page only;
`snippet` = search-result snippet only; `UNVERIFIED` = could not be fetched.
Several ePrint PDFs returned a Cloudflare 403 to automated fetches, so they are `abstract` or
`UNVERIFIED` here. They need a manual read in a browser.

## Claims under attack

- **A.** Equality saturation with cost-minimal extraction systematically returns a
  probing-insecure circuit from a secure masked one, *because* the insecure representative is
  cheaper. Reproduced on two engines.
- **B.** Extraction from an e-graph constrained by a semantic hyperproperty (probing security):
  per-class safe/unsafe labels at first order; term-based per-use extraction when re-sharing
  rules are present.
- **C.** Congruence obstruction: re-sharing (refresh, gadget swap, register) preserves the encoded
  value but is not a congruence of the wire-term algebra, so it cannot be an e-graph equality;
  a value-level layer plus lowering and per-use extraction is needed.
- **D.** On the PINI-only fragment, safety is again a class label, one-node-per-class extraction
  is sound at any fan-out, and class-level extraction scales (2^128-point circuit) without
  enumeration.
- **E.** In the glitch-extended model a register acts like a refresh; cost-minimal extraction
  that treats registers as transparent deletes them; constrained extraction restores them.
- **F.** Gains appear only where the start circuit has slack; tight constructions are unchanged.

## Queries run (exact, by search agent)

**Agent 1 — eVer and superVer.**
`superVer e-graph masking verification EGRAPHS 2024 Treff Pauls Orlt Gourjon`;
`eVer verification side-channel masking "equality saturation" OR "e-graph" Gourjon Orlt Pauls Treff`;
`"eVer" Universal and Automated Verification of Side-Channel Security Additive, Inner Product, Polynomial General Code-Based Masking`;
`Alexander Treff Pajam Pauls masking verification probabilistic independence proof system`;
`eVer github Gourjon masking verifier proof rule probabilistic independence tool repository`;
`Gourjon Orlt Treff Pauls masking "e-graph" OR "equality saturation" OR "rewriting" verification probing security`.

**Agent 2 — compiler-induced leakage.**
`equality saturation e-graph masking probing security side-channel`;
`logic synthesis optimization breaks masking probing security glitch ABC Yosys masked circuit`;
`"e-graph" OR "equality saturation" "masked" implementation threshold implementation rewriting side-channel`;
`superVer e-graph verification masked implementations probing security EGRAPHS 2024`;
`security-constrained code generation masking SecCG compiler optimization preserve probing security`;
`Fraunhofer AISEC BSI re-timing masked hardware report 2024`;
`hyperproperty preserving compiler optimization e-graph equality saturation constant-time secure compilation`;
`e-graph rewriting secret leakage "side-channel" OR "constant-time" equality saturation security-aware extraction`;
`E-Syn OR BoolE e-graph logic synthesis masked circuits side-channel security preserve`;
`Rosita++ compiler optimization masked code; Eldib Wang synthesis of masking countermeasures`;
`area-optimal masked circuit synthesis rewriting insecure cheaper "probing security" SAT-based minimal masked gadget`.

**Agent 3 — extraction constraints and non-congruent rewriting.**
`Semantic Foundations of Equality Saturation Suciu Wang Zhang ICDT 2025 congruence`;
`e-graph extraction under security constraint masking probing security equality saturation`;
`e-graph extraction non-local constraint hyperproperty OR "information flow" OR "constant-time" equality saturation`;
`e-graphs with contexts OR "colored e-graphs" Singher Itzhaky conditional equalities non-congruence`;
`SkeleShare CGO 2026 equality saturation resource constraints extraction`;
`equality saturation masked implementation side-channel countermeasure e-graph optimization masking gadgets`;
`e-graph extraction dependent/context-sensitive cost occurrence tree-vs-DAG cost`;
`equality saturation e-graph secure compilation constant-time cryptographic verified rewriting side channel`;
`equality saturation directed/non-symmetric/refinement relations not congruence`;
`E-graph extraction acyclicity EGRAPHS 2023 ILP global constraints`.

**Agent 4 — masking optimisation and PINI.**
`masked circuit optimization e-graph equality saturation probing security`;
`automated masking randomness optimization PINI gadget selection compiler 2025`;
`Fraunhofer AISEC BSI report re-timing synthesis breaks masking glitch registers removed`;
`Cardinal RPC masked circuit compiler ASIACRYPT 2025`; `COMPRESS TCHES 2024 gadget selection randomness area`;
`Prover TCHES 2025 masking verification probing compositional scalable`;
`logic synthesis optimization removes registers masked hardware glitch-extended probing retiming secure synthesis flow`;
`Keccak chi first-order masked minimum randomness lower bound optimal gates DOM ISW glitch-extended 2024 2025`;
`registers act as refresh glitch-extended probing register placement minimal refresh gadgets masked circuit optimization PINI`.
Not searched separately: Tornado, POMMES/CoMEMS, IronMask, tightPROVE, VerifMSI, maskVerif, Usuba.

## Hits and verdicts

| Source | Read | What it precisely shows | A | B | C | D | E | F |
|---|---|---|---|---|---|---|---|---|
| superVer, Treff, Pauls, Orlt, Gourjon, EGRAPHS 2024 | abstract | E-graphs used to *verify* joint independence of probed expressions; solves "phase ordering" of language-based verifiers; "free of false negatives". No extraction, cost or optimisation mentioned | context | partial (subject area) | context | – | – | – |
| eVer, Gourjon, Orlt, Pauls, Treff, ePrint 2026/208 | abstract (PDF blocked) | A sound verifier for additive, inner-product, polynomial and code-based masking via a new proof rule for joint independence. **Abstract does not mention e-graphs, optimisation or refresh gadgets** | context | context | context | – | – | – |
| MaskedHLS, Sarma, Thakur, Karfa, arXiv 2407.11806 | part full | HLS/LLVM reassociation "alter[s] the guarantee" giving insecure RTL; uses retiming with locked registers; notes redundant registers "can be optimized out" safely | context | – | – | – | **partial** (closest) | – |
| Koblah et al., ePrint 2025/1190 | abstract (PDF blocked) | Evolutionary-algorithm optimisation of masked gadgets; compares conventional CAD (technology mapping, FRAIG rewriting, retiming) whose gains are "inconsistent". Abstract has no e-graphs and no VERICA | partial | context | – | – | – | – |
| SecCG, Tsoupidi et al., arXiv 2207.02614 | abstract | Constraint-based cost-driven code generation preserving power side-channel security | context | context | – | – | – | – |
| Fraunhofer AISEC for BSI, blog 7 Nov 2024 | blog only | Re-timing in synthesis leaks in a masked AES S-box | context | – | – | – | **partial** | – |
| Suciu, Wang, Zhang, ICDT 2025, arXiv 2501.02413 | HTML via a summarising fetch | E-graph semantics is a partial congruence relation (a congruent and reachable PER). Says nothing about wire-term algebras or re-sharing | – | – | enabling citation | – | – | – |
| Colored e-graphs, Singher and Itzhaky, arXiv 2305.19203 | abstract | Each colour is its own congruence layer | – | context | context | – | – | – |
| Acyclic extraction, He et al., EGRAPHS 2023; SkeleShare, CGO 2026 | abstract | Extraction under acyclicity / FPGA resource constraints | – | context (closest: global constraint) | – | – | – | – |
| Cassiers and Standaert, PINI, ePrint 2018/438 | abstract; Cassiers' master's thesis read | Thesis has the composition property (Property 2.11), linear gadgets d-PINI (2.12), and soundness needs independent input encodings. **Property 11 and 12 numbering in the paper is UNVERIFIED** | – | – | – | **supports** (soundness is a corollary) | – | – |
| COMPRESS, Cassiers et al., TCHES 2024(3) | part full | PINI-compositional optimisation by gadget selection, scheduling and register placement via CP-SAT, no enumeration, fixed circuit, no rewriting | – | – | – | **partial** | **partial** | context |
| TETRIS, Sarma et al., ePrint 2026/1306 (CHES 2026) | abstract | PINI design-space exploration, heuristics under a millisecond, VERICA-checked | – | – | – | **partial** | UNVERIFIED | UNVERIFIED |
| Kumar et al., ePrint 2025/2102 | abstract | Graph-colouring randomness optimisation, glitch-extended model | – | – | – | context | – | context |

## Findings that correct the existing repo text

1. **eVer.** `docs/adversarial-search-3.md`, `design/0011` and the proposal say eVer "optimises refresh
   sequences and gadgets." This pass could read only its abstract, which describes a verifier. The
   claim is **UNVERIFIED** until the full PDF is read in a browser. If it is only a verifier, the
   overlap with our work is smaller than the repo assumes.
2. **ePrint 2025/1190** is Koblah et al., an evolutionary-algorithm paper. It is not described in the
   abstract as a FRAIG paper filtered with VERICA. The repo's description needs checking.
3. **COMAR attribution.** Agent 4 found COMAR credited to Knichel and Moradi, not Feldtkeller et al. as
   the repo text has it. Check before citing.

## Residual gap and verdict per claim

- **A — survives, medium-high.** No source shows, for e-graph extraction specifically, that cost-minimal
  extraction selects insecure circuits, or frames it as systematic because the insecure member is
  cheaper. The broad phenomenon (optimisers and synthesis break masking) is established (MaskedHLS,
  Fraunhofer/BSI) and must not be claimed. Risk: superVer, eVer and ePrint 2025/1190 are unread.
- **B — survives, medium-high.** No hit extracts under a security, information-flow or hyperproperty
  constraint. SkeleShare (resource) and acyclic extraction are the nearest precedents.
- **C — survives, medium-high, but frame it carefully.** It is an application of a known fact (e-graph
  equality is a congruence). The novelty is the observation for masked circuits plus the value-level
  layer. No hit argues that re-sharing is non-congruent for e-graphs.
- **D — partly pre-empted, medium.** PINI-compositional optimisation without enumeration exists
  (COMPRESS, TETRIS). Soundness at any fan-out follows from the PINI composition property. Do **not**
  claim "PINI makes optimisation scale." What remains is doing it over e-classes under rewriting.
- **E — partly pre-empted, medium.** Register placement under PINI (COMPRESS, MaskedHLS) and re-timing
  breaking masking (Fraunhofer/BSI) are known. What remains is the "register = refresh" unification
  and the demonstration that cost-minimal extraction deletes registers.
- **F — survives, medium-high.** Nothing contradicts it, and no source states Keccak chi is already
  tight. It is our empirical finding and should be presented as one, with its limits.

## What we do not claim

Not first to see optimisers break masking (MaskedHLS, Fraunhofer/BSI, ePrint 2025/1190). Not first to use
e-graphs for probing security (superVer). Not first to place registers or select gadgets by PINI
composition (COMPRESS, MaskedHLS, TETRIS). Not first to constrain extraction (acyclicity, SkeleShare).
Not the notion of equivalence up to re-sharing.

## Could not verify

Full text of eVer, superVer, ePrint 2025/1190, the BSI report, TETRIS, ProverNG, Cardinal RPC; the
numbering of Properties 11 and 12 in ePrint 2018/438; Tornado, POMMES/CoMEMS, IronMask, tightPROVE,
VerifMSI, maskVerif, Usuba and the common-shares paper were not searched. The search tool is US-only
and snippet-based, so a recent workshop paper could be missed. Novelty is a negative claim and cannot
be proven.

## Recommended before any novelty wording is final

Download and read in a browser: eVer (ePrint 2026/208), ePrint 2025/1190, the superVer paper (PLDI 2024
EGRAPHS page), ePrint 2018/438, and TETRIS (ePrint 2026/1306). Search EGRAPHS 2025 and 2026 proceedings.
