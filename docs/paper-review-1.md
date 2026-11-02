# Paper review 1 — `Probing_Secure_EqSat_IEEE.tex` (from `docs/research paper.zip`)

Reviewer: Claude (Sonnet 5.5), 2026-11-02. Inline review, no subagents.

## 0. What this review can and cannot say

- **The "AI% < 20" and "plagiarism < 20%" targets cannot be certified here.** Those numbers come from
  commercial tools (Turnitin/iThenticate, GPTZero, etc.) that are not available in this sandbox. Anything
  below is a *local proxy*, labelled as such. Run the real checkers yourselves before submission.
- **I did not rewrite prose to move a detector score.** The paper's Acknowledgment already discloses AI
  assistance; keep it. Venue policies on AI-assisted text apply regardless of any score.
- **LaTeX did not compile here:** `stmaryrd.sty` is missing and AGENTS.md §3 forbids installing it.
  Compile checks below are by inspection. Please build on your side.

## 1. Adversarial review (ranked)

### Must fix (correctness / reviewer-kill risk)

1. **Head-to-head is not like-for-like.** seqc's gadget is glitch-free ISW; AGEMA (HPC2/HPC3) and COMPRESS are
   glitch-robust and pipelined. Footnote (a) admits this, but the abstract and §H2H text still say seqc
   "needs no more AND gadgets". A reviewer will say the gadget count is bought with a weaker security model.
   Fix: say so in the abstract, or add a seqc-with-HPC/PINI column.
2. **Missing baseline.** The wins come from the benchmarks being written with removable waste (COMPRESS "keeps
   the logic as written"). A plain multiplicative-complexity / AND-count minimiser (ABC, XAG-style) followed
   by COMPRESS may match them with no e-graph. Without it the paper does not show equality saturation is needed.
3. **Number mismatches with the repo's own records** (`docs/presentation-v1-compression.md` item 7 already
   flagged these; the paper was not updated):
   - Keccak χ 32-bit PINI time: paper **0.04 s**; `experiments/composition/RESULTS.md` records **0.03 s**.
   - Depth-4 extraction: paper **7.4 s**; `experiments/resharing/RESULTS.md` records **5.2 s**.
   - Depth-5: paper **144–193 s**; recorded **143.6 s**. The 193 s is not in any RESULTS file I found.
     (The paper may reflect other runs; if so, put them in a `RESULTS.md`.)
4. **"16 of the 338 one-node-per-class choices" is attributed to "all three rule groups"** in §V. The repo
   (`docs/proof-review-1.md`) says it was measured under **R1 + R3**. Align the sentence.
5. **LaTeX defect, Fig. congruence caption (≈ line 406):** `... and $f(y)=1.` opens a math group and a
   quote that are never closed. This will break the build (or swallow text). Fix: `$f(y)=1$.''`
6. **Broken code link.** Acknowledgment points to `github.com/wizard-28/secureeqsat`; `git remote` is
   `wizard-28/compiler-design-project`. Fix before submission.
7. **Unsupported absolute claims.**
   - Abstract/Intro: "with two shares this always happens". The argument covers factoring *inside the ISW
     gadget's four products*, not arbitrary two-share circuits. Scope it.
   - §III-B: "We found no earlier statement of this point for e-graphs" is a negative novelty claim with no
     query log in the paper. AGENTS §5.4 requires one: add an appendix citing `docs/adversarial-search-*.md`
     queries, or soften. (§11: novelty claims need a human decision.)

### Should fix

8. **Keccak "certified in 0.04 s" is PINI by construction** on the bigger HPC1 circuit (25–33% larger), glitch-free
   only. The speed is a property of PINI composition, not of the e-graph. Say so next to the headline.
9. **Table "Agreement with VerifMSI" says 7 compiled programs; Table "Compiled programs" lists 6.** Explain or fix.
10. **"Two registers" wording:** ISW-no-registers goes 7 → 10 against cost-only (one gate + two registers),
    8 → 10 against start. The sentence says only "two registers".
11. **maskVerif appears in Table I but has no `\cite`/bibliography entry**; "synthesis tools" and
    "plain e-graphs" rows have no citations either. (Citation must be fetched before adding, §5.1.)
12. **Chain figure:** the 240 sampled circuits exclude the hand design; say so, or readers ask why "none
    secure" when the 16-gate hand design is secure.
13. **Proposition "leak cut"** proof sketch is plausible but relies on a "piece" being a closed subterm with
    identical dependence on primary inputs; state that definition. The multi-probe remark in the proof
    sits oddly with the one-probe scope.
14. **Labeller speedup "≈ 50 min (est.)"** is an estimate; a measured number or an explicit "extrapolated" is safer.
15. **Abstract length:** ~230 words; IEEE conference abstracts are normally ≤ 200. Page count unverified (no build).
16. **Bib key `knichel2021agema` vs. year 2022** — cosmetic.

### Verified (direct checks)

- 55,977 = 21,760 + 22,463 + 914 + 6,054 + 4,608 + 178 ✓.
- Chain histogram sums to 240 and 28 circuits fall below 16 gates ✓.
- Saving percentages in the compiled-programs table and the COMPRESS area column (45%, 27%, 17%) recompute ✓.
- Gadget-count claims ("strictly fewer than AGEMA on 3, than COMPRESS on 3") match the table ✓.
- Truth tables for `isw(z,z)` (½ vs 0) and `isw(z,refresh(z))` (¼ vs ¼) ✓; congruence table ✓.
- `784` and `6,054`/`240` match `experiments/glitch_probe` and `experiments/oracle_crosscheck` RESULTS ✓.
- Citations fetched this session: eVer (ePrint 2026/208) and TETRIS (ePrint 2026/1306) exist with the stated
  titles and authors ✓. **The other 16 bibliography entries were not re-fetched in this pass: treat as UNVERIFIED
  for this review** (some were verified earlier per the repo's search logs).

## 2. Stylometry (local proxies only — not an AI-detector score)

Method: `scratchpad/proxy.py` on prose extracted from the `.tex` (math, tables, figures stripped), 4,262 words, 224 sentences.

| Signal | Value | Reading |
|---|---|---|
| Sentence length mean / SD / CV | 19.2 / 11.6 / 0.61 | Healthy variation (flat, uniform text has CV < 0.4) |
| Type-token ratio | 0.204 | Low, but inflated by length and technical repetition; not informative |
| Stock "AI vocabulary" (delve, tapestry, pivotal, …) | 1 hit ("robust") | Clean |
| Em-dashes | 2 | Low |
| Contrast frames ("not X but Y", "rather than") | 10 | Moderate; slightly characteristic |
| Bold-lead call-outs (`\textbf`) | 79 | High for a research paper; the strongest "assistant-style" signal |

Honest read: the text is plain-spoken, uses short declarative sentences, rhetorical questions ("Why not simply
ban…?"), and many bolded take-aways, which commercial detectors sometimes flag on technical prose. I cannot
predict the real score. Genuinely useful (not detector-driven) edits: cut bolded call-outs to ~20, merge a few
of the "Finding" boxes, and add authors' own experience (why the project pivoted, what failed). The disclosure
in the Acknowledgment remains.

## 3. Plagiarism (local proxies only)

- **Self-overlap with this repo's docs** (8-gram shingles, prose only): 3 shared 8-grams, 0.1% of the paper
  (all vs `docs/theory.md`). Low in the prose, but the repo is public and the proposal/briefing share ideas
  and tables; a checker may flag the **GitHub repo and slide decks** as sources. Declare prior internal
  reports (course submissions) where the venue requires it.
- **External exact-phrase web searches** (3 queries: abstract opener, the "every gate-saving factoring…" claim,
  title/tool name): **no matches** found for any. This is a spot check, not a similarity scan.
- Not checked: overlap with the cited papers' text. The Background section paraphrases ISW/PINI/HPC; run the
  real tool and inspect those paragraphs first.

## 4. What more could be added (ordered by value / cost)

1. **Three-share test of Finding 1.** The "every saving recombines a secret" argument is specific to two
   shares (`a_i(b_0⊕b_1)` is a secret only when there are two). Run the same pipeline at d = 2 and report
   whether the leaking-cheaper-circuit result survives. It could be the paper's strongest generalisation or
   a clean negative result. Both are publishable.
2. **A real benchmark.** An AES/PRESENT/Ascon S-box or a full Keccak round, not only χ and toy programs.
3. **A non-e-graph baseline** (item 2 above) to show saturation matters.
4. **Synthesis numbers for seqc's own output** (Yosys/Nangate45, glitch-robust variant using HPC gadgets),
   so the comparison to COMPRESS/AGEMA is like-for-like. Currently listed as a limitation.
5. **Ablation table:** each rule (factoring, distributivity, R2, R3) switched off, showing which rule
   produces which saving and which leak.
6. **Machine-checked proofs** for the leak-cut and class-label propositions (Lean/Coq/SMT), or at least an
   exhaustive small-case check; currently hand proofs.
7. **Threats-to-validity paragraph** and an **artifact appendix** with the exact reproduce commands and run-time
   variance (resolves the timing mismatches above).
8. **Related work to consider (all UNVERIFIED, fetch before citing; AGENTS §5.1):** maskVerif; SILVER/PROLEAD
   verifiers; SNI-based composition work (Barthe et al.); logic-synthesis e-graph work (e.g. E-Syn,
   ROVER). Also the 2025 ePrint 2025/2102 (randomness optimisation by graph colouring, surfaced by search:
   [eprint.iacr.org/2025/2102](https://eprint.iacr.org/2025/2102)) — **found by search snippet only, not
   read**; check for overlap before the "what we claim" paragraph.

## 5. Decisions for the humans (AGENTS §11)

- Whether to soften/keep the "no earlier statement" novelty sentence.
- Whether to restate the abstract's head-to-head claim given item 1.
- No paper edits were made. Nothing was committed.

---

## 6. Follow-up (2026-11-02, after the author's reply)

**Corrections to this review.**
- Timing mismatches (0.04 vs 0.03 s, 7.4 vs 5.2 s, 144-193 vs 143.6 s): the paper's numbers come from a
  teammate's machine. Not an error; item 3 above is withdrawn. Consider stating the machine in Table "Speed".
- The "16 of 338" attribution (item 4) is still open: the repo measured it under R1+R3.
- Repo link: the author has already changed it to `wizard-28/secureeqsat` (item 6 closed).
- **The congruence-caption defect (item 5) was misdescribed.** The math there *is* closed
  (`$f(y)=1$.`); the only defect is a missing closing `''`, so it is a stray opening quote, not a
  build break. Fixed in `docs/paper/Probing_Secure_EqSat_IEEE.tex`. I could not compile (`stmaryrd.sty`
  missing, no installs allowed), so the patched paper is **uncompiled**: braces and `\begin/\end` balance
  by script, nothing more.

**Left to the teammate (time-sensitive):** real benchmark (S-box / full Keccak round), non-e-graph baseline,
synthesis area numbers.

**Done**
| Item | Result | Where |
|---|---|---|
| Three shares | d=2: 8/7/8 reproduced. d=3: 21 / 17 cost-only (leaks) / 18 secure. d=4: 40 / 31 (leaks) / 32 secure. Cost-only still leaks, but **secure savings now exist**, so "every saving recombines a secret" is two-share only. In-house checker only, **not VerifMSI cross-checked** (not installed here). | `experiments/three_share/` |
| Ablation table | Already existed (`experiments/resharing/run.py`, reproduced in 15 s); condensed into a paper table. Each saving has one source rule; only configurations with R3 yield a leaking cost-only optimum. | `docs/paper/` Table "Rule Ablation" |
| Machine-checked proofs | **Not possible here**: no prover in the container (installing one means a `.devcontainer` change, your call). Instead a bounded exhaustive check of the leak-cut proposition: 2,204 leaking terms x 26 contexts = 57,304 checks, 0 counterexamples. This is not a proof; the class-label proposition (R3 example) is already an explicit finite counterexample with tests. | `test_leak_cut_exhaustive.py` |
| Related work | Fetched/verified via search + page: ePrint 2025/2102 (graph-colouring randomness optimisation; abstract says it only rewires randomness, logic unchanged, no e-graphs), E-Syn arXiv 2403.14242 (DAC 2024), SILVER (ePrint 2020/634, ASIACRYPT 2020), SNI/type-directed masking (CCS 2016, ePrint 2015/506). maskVerif (ESORICS 2019): title/pages seen in a search snippet, **author list UNVERIFIED** (HAL page blocked) and marked in the bib. None changes the novelty boundary; 2025/2102 is adjacent (randomness only). | `docs/paper/` Related Work |

**Gate:** `ruff check` and `ruff format --check` clean on `experiments/` and `findings/` (the repo-wide run
fails only on the untracked `.agents/skills/kaggle` folder); `uv run pytest -q experiments`: 159 passed,
19 skipped (VerifMSI-dependent, not installed here). `findings/verify.py` not re-run (needs VerifMSI).

**Needs your decision (AGENTS.md section 11)**
1. The d >= 3 numbers are a security-related measurement without oracle cross-check: keep them as the
   marked section in the paper, or drop until VerifMSI confirms them.
2. Whether the paper keeps "with two shares this always happens" (still true as scoped) next to the new
   subsection.
3. Whether to install a prover (Lean/Z3) via `.devcontainer`.
