# Adversarial search #5 — the composition analysis

**Date:** 2026-10-22
**Target:** claim C9 in `docs/theory.md` and `design/0019`: a PINI-based
e-class analysis that makes safety class-local again on the PINI fragment.
**Method:** one pass by Claude (AI assistant) for the author; fetched hits read
from the primary page, titles-only hits marked UNVERIFIED. Rules:
`.claude/skills/secureeqsat-citation-check`.

**Headline.** The theorem C9 rests on is verified at the level of its
statements: PINI composition (Property 12) and PINI-to-probing-security
(Property 11) in Cassiers & Standaert. Composition notions, composable gadgets
and composition-aware masking compilers are mature and must be cited; no hit
uses a composition notion as an **e-graph analysis to restore class-level
extraction**. Medium confidence, negative result.

## 1. Claims under attack

| ID | Claim |
|---|---|
| T5 | C9's foundation: PINI gadgets compose, and PINI + independent inputs gives probing security |
| T6 | Using PINI as an e-class analysis, so safety is a class label on the PINI fragment and one-node-per-class extraction is sound there, is not prior work |

## 2. Queries run

1. `PINI composable gadgets e-graph equality saturation masking`
2. `type system composition masking compiler SNI PINI automatic refresh insertion maskComp Tornado`
3. `HPC1 HPC2 PINI glitch-robust composition hardware private circuits AGEMA composable gadgets`

Plus direct fetches of ePrint 2018/438 (abstract page and PDF).

## 3. Hits

### Fetched

| Work | What it shows | Verdict |
|---|---|---|
| **Cassiers & Standaert**, *Trivially and Efficiently Composing Masked Gadgets with Probe Isolating Non-Interference*, IEEE TIFS 2020 (DOI 10.1109/TIFS.2020.2971153), ePrint 2018/438 | Def. 12 (d-PINI); **Property 12**: "A composite gadget made of d-PINI composing gadgets is d-PINI"; **Property 11**: a d-PINI gadget is d-probing secure "if the encodings of the inputs are independent of each other"; Property 13: trivial linear gadgets are PINI; Property 14: their multiplication (an ISW variant) is PINI. No explicit restriction on fan-out; the backward-induction proof implicitly assumes acyclicity. ISW, DOM and refresh are not claimed PINI there | **T5 verified** (statements, read from the PDF). Our gadget verdicts are not taken from it: each gadget is checked exhaustively and with VerifMSI |
| **Hardware Private Cubic Circuits** — Reiter, Moradi, TCHES 2026, ePrint 2026/1351 | 3-input PINI gadgets, glitch-extended model, composable AES S-box | Context: PINI gadget design is active; no compiler or e-graph |
| **Prime-Field PINI** — Iskander, Kirah, arXiv 2604.25878 (2026) | Lean 4 machine-checked composition theorems for arithmetic masking | Context: composition theorems; no e-graphs or optimization |
| **High Assurance Masking Compilation** — bachelor thesis topic, ENCRYPTO, TU Darmstadt (2026) | A front end that compiles unprotected code with verified gadgets, refresh insertion and gadget composition; pattern-matched gadget optimization | **Partially overlaps** in spirit (composition-aware masking compilation with optimization); no e-graphs |

### Titles only — UNVERIFIED

Low-Latency Hardware Private Circuits (ePrint 2022/507, fetched in pass 3 via
a secondary source); the HPC paper (ePrint 2020/185, not fetched); maskComp
and Tornado (named in pass 3, composition-based masking compilers).

## 4. Verdicts

**T5 — verified,** with two notes for the paper: state Property 11's
precondition (independent input encodings) and the implicit acyclicity.

**T6 — survives at medium confidence.** Composition-aware masking compilers
(maskComp, Tornado, the libmasking front end) choose refreshes and gadgets from
composition notions; that is prior art for *using composition in compilation*
and must be cited. Not found: a composition notion used as an *e-class
analysis* over an e-graph, so that safety becomes a class label and ordinary
DAG extraction is sound on the composable fragment.

## 5. What must not be claimed

- That PINI-based composition, or composition-aware masking compilation, is new.
- That HPC1 or any gadget is newly shown PINI (we only re-check it).
- Anything in the glitch-extended model for C9 (registered gadgets not modelled).

## 6. Residual uncertainty

One pass; web-index limited; maskComp/Tornado internals not re-read; paywalled
2026 work could collide.
