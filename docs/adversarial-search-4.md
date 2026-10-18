# Adversarial search #4 — attacking the theory draft

**Date:** 2026-10-18
**Target:** `docs/theory.md` (claims C1–C8) and the scope change in
`design/0018`, specifically the four items its §5 lists for a citation check.
**Method:** one pass, run by Claude (AI assistant) for the author; every hit
listed as *fetched* was opened and its title, authors and venue read from the
primary page. Hits seen only as search-result titles are marked
**UNVERIFIED** and must not be cited from this record. Rules:
`.claude/skills/secureeqsat-citation-check`. Earlier passes are not repeated;
their verdicts stand unless revised below.

**Headline.** No hit defeats the theory's claims as stated. Two need
sharpening: the glitch-model *phenomenon* (optimizers moving or removing
registers break masking) is already known and must be disclaimed, and the
shared-value layer must answer pass 3's warning that a usable relation must be
*finer than the decode kernel*. The novelty that survives is narrow and sits at
**medium** confidence. The author decides whether to make any novelty claim
(`AGENTS.md` stop-and-ask).

---

## 1. Claims under attack

| ID | Claim (from `docs/theory.md`) |
|---|---|
| T1 | Identifying sharings by value makes refresh and gadget substitution ordinary e-graph rewrites (C3, C4) |
| T2 | A value-preserving, leakage-changing (VPLC) operator makes safety non-class-local and one-node-per-class extraction incomplete; occurrence-aware extraction with a monotone leak cut repairs it (C5, C7) |
| T3 | Registers are VPLC in the glitch-extended model; glitch safety is not a function of the wire; register-oblivious optimization breaks it; register placement repairs it (C2, C6) |
| T4 | Citation: e-graph semantics is a partial congruence (Suciu, Wang, Zhang) |

## 2. Queries run

1. `eVer ePrint 2026/208 masking verification refresh optimization e-graph`
2. `equality saturation masked circuits gadget level rewriting refresh`
3. `e-graph extraction different representatives same e-class occurrence context-dependent extraction`
4. `automated register insertion glitch-robust masking AGEMA register placement`
5. `e-graphs registers retiming pipelining hardware equality saturation RTL`
6. `equality saturation e-graph side-channel security constant-time masking optimization 2025 2026` (extended)
7. `automatic register insertion glitch extended probing security masked circuit tool search optimization` (extended)
8. `"Semantic foundations of equality saturation" ICDT 2025 Suciu Wang Zhang`
9. `Glitch-Stopping Circuits Hardware Secure Masking without Registers eprint`
10. `colored e-graphs contextual equality saturation conditional equalities Singher Itzhaky`
11. `retiming breaks masking glitch security synthesis tool register retiming side-channel leakage`
12. `e-graph extraction same e-class extracted differently at each use duplication tree extraction versus DAG extraction`

## 3. Hits

### Fetched (primary page read)

| Work | What it shows | Verdict |
|---|---|---|
| **eVer** — Gourjon, Orlt, Pauls, Treff, *eVer: Universal and Automated Verification of Side-Channel Security for Additive, Inner Product, Polynomial and General Code-Based Masking*, IACR ePrint 2026/208 (posted 2026-02-09) | Abstract page: a proof rule for joint probabilistic independence, implemented as a verifier; keywords include *probabilistic equivalence*. The current abstract does **not** mention refresh optimization, e-graphs or glitches | **Partially overlaps T1** (via pass 3, which quoted refresh-sequence optimization from the PDF read through a mirror). The PDF is bot-blocked and was **not re-read** today; the pass-3 characterisation stands but is unconfirmed |
| **Semantic Foundations of Equality Saturation** — Suciu, Wang, Zhang, ICDT 2025, LIPIcs vol. 328, 11:1–11:18 (arXiv 2501.02413) | §3.1, Def. 5: an e-graph's semantics is a **Partial Congruence Relation (PCR)**, "a congruent and reachable PER" | **T4 verified.** Cite as "partial congruence relation (PCR)"; the abstract itself does not say this, the body does |
| **Towards Relational Contextual Equality Saturation** — Hou, Laddad, Hellerstein, arXiv 2507.11897 (2025) | Rewrite rules "conditioned on where a term appears in an expression", in egglog | **Partially overlaps T2** in spirit (context-dependence) but on the *equality* side; nothing on extraction or security. Must be cited and distinguished |
| **Fraunhofer AISEC / BSI study on synthesis of cryptographic hardware** — blog post by Oberhansl, Stelzer, Schink, 7 Nov 2024 | Re-timing is "a potentially fatal modification for masked implementations"; shown on a masked AES S-box; Yosys optimizations analysed | **Partially anticipates T3's phenomenon** (register-moving optimization breaks masking). Secondary source; cite the underlying study if found |
| **Glitch-Stopping Circuits** — Zhang, Nikova, Nikov, ePrint 2024/891 (ext. of ACM CCS 2024) | Glitch-immune masking without registers, using clocked gates or latches | Context for T3 (role of registers); no automation or e-graphs |
| **Can We Tolerate Small Side-Channel Leakages: The Role of Registers in Glitch-Stopping Circuits** — Ovchinnikov, Biesmans, Myny, Nikov, Nikova, ePrint 2026/1011 | Studies removing pipeline registers from a provably secure design; TVLA shows no detectable leakage | Context for T3; shows register removal is an active design question |
| **Optimizing AES Threshold Implementation under the Glitch-Extended Probing Model** — Yao et al., ePrint 2023/1856 | Design approach for first-order glitch-extended TI; credits Shahmirzadi et al. (CHES 2021) with a search method for 2-share TI | Context for T3: search-based glitch-secure design exists, not via e-graphs |
| **AGMNC** — Wu, Fan, Preneel, Wang, Wang, ePrint 2023/831 | Automated generation of masked nonlinear components; builds on AGEMA; SILVER-verified | Context; abstract does not mention register placement |
| **AGEMA** — Knichel et al., *Automated Generation of Masked Hardware*, TCHES (ePrint 2021/569) | Automated masked-hardware generation from composable gadgets | Context; register handling not checked today (**do not** claim register placement is new) |
| **ROVER** — Coward, Drane, Constantinides, arXiv 2406.12421 | E-graph RTL datapath optimization with ILP extraction and certificates | Context: e-graphs for hardware exist; abstract does not mention registers or security |
| **E-Graphs as a Persistent Compiler Abstraction** — Merckx et al., arXiv 2602.16707 | MLIR `eqsat` dialect | Not relevant (false-positive hit) |

### Seen as titles only — UNVERIFIED, do not cite from here

e-boost (arXiv 2508.13020) and SmoothE (ASPLOS 2025) on e-graph extraction;
*Cut Tracing with E-Graphs for Boolean FHE Circuit Synthesis* (arXiv 2506.12883);
*Automatic Datapath Optimization using E-Graphs* (arXiv 2204.11478);
*Colored E-Graph* (arXiv 2305.19203, fetched in pass 3);
BoolE (arXiv 2504.05577); MaskedHLS (fetched in pass 3).

## 4. Verdicts

### T1 — value-level rewriting of re-sharing

**Survives in a narrow form; medium confidence.** No hit applies e-graph
rewriting over a value-identified sharing algebra. The risks:

- eVer's refresh optimization (pass 3) works by proof rules and
  re-verification; the overlap is in *what* is optimised, not *how*.
- Pass 3, §C3, warned that "same decoded value alone is too coarse": it would
  identify a secure `(x0, x1)` with the insecure `(x, 0)`. **The theory must
  answer this explicitly.** The answer: the value layer is the decode kernel
  restricted to a *masking-closed* term language (inputs, share-wise XOR,
  refresh, register, gadgets) in which `(x, 0)` is not expressible, and
  security is moved out of the equality into extraction. C5 is precisely the
  price of that move. (`docs/theory.md` now carries this remark.)
- The equivalence itself is standard masking semantics (pass 3, §C2:
  ISW, SNI, tightPROVE's `Flatten`); only its use as an e-graph search relation
  may be new.

### T2 — VPLC operators, class-locality, extraction

**Survives; medium confidence; phrase as an observation, not a "first".**
Contextual equality saturation (Hou et al.) makes *equalities* context-
dependent; nothing found makes *extraction* occurrence-dependent for a
semantic side property. Residual risk: the general fact that one-node-per-class
extraction cannot assign different representatives to different occurrences is
folklore in the extraction literature (not verified today — the extraction
papers above are unread). Claim only the security consequence.

### T3 — registers as VPLC; glitch model

**Phenomenon partially anticipated; formalisation survives at medium
confidence.** That register-moving optimizations (re-timing) can break masked
hardware is known (Fraunhofer/BSI 2024; pass 3: MaskedHLS for software-level
reassociation). Search-based glitch-secure design exists (Shahmirzadi et al.,
via Yao et al.). Not found: registers treated as value-preserving operators in
an e-graph, with the same extraction obstruction and repair as refresh.
Register *placement* by our extractor must **not** be claimed as new.

### T4 — citation

**Verified.** Suciu, Wang, Zhang, ICDT 2025 (LIPIcs 328), §3.1 Def. 5.

## 5. What must not be claimed (additions to pass 3's list)

- That optimizers breaking glitch-robust masking is a new observation.
- That automatic register placement for glitch security is new.
- That context-dependence in e-graphs is new (contextual EqSat exists).
- Any statement about eVer beyond what the abstract page says, until its PDF is
  read directly.

## 6. Residual uncertainty

- One pass, one agent, web-index-limited; paywalled 2026 venue papers could
  hide a collision. Pass 3 used two independent passes; this one did not.
- eVer's body not re-read; the AGEMA paper not read for its register handling;
  the extraction papers (e-boost, SmoothE) not read.
- The Fraunhofer/BSI finding is from a blog post, not the study itself.
- The surviving novelty for T1–T3 is a **negative result at medium
  confidence**.
