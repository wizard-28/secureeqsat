# Team Briefing: Why the Original Direction Is Dead, and Plan A

**Audience:** project team (assumes you've read `docs/original/`)
**Date:** 6 October 2026
**Purpose:** state plainly where we stand, why the original research direction cannot carry a
novelty-first project, and what we propose instead. Ends with what we need from you.
**Status:** recommendation, not a decision. Push back if you disagree with the reasoning.

---

## TL;DR

1. **The original plan** ("LLM/agent-guided equality saturation and superoptimization",
   `original/llm-agent-equality-saturation-research-overview.pdf`) is no longer viable.
   Its central claim — that replacing human guidance in equality saturation with an
   LLM/ML model is a new research program — was published between 2024 and 2026.
2. **The two fallback ideas** from `original/adversarial-search.md` (a learned
   stop/continue controller, and guide-usefulness prediction) are also occupied.
3. **The security/constant-time niche** (§5.7 of the overview), which the first search
   rated highest, fails on both novelty and feasibility. Details in §2.3 — this one
   matters because several of us liked it.
4. **Plan A** — *probing-secure equality saturation*: use e-graphs to optimize masked
   cryptographic circuits under a probing-security constraint. It is unclaimed, it is
   in our lane, and we have already validated its central premise experimentally.
5. **We ran the feasibility check today.** The premise holds, and the failure mode is
   systematic. Results in §4.

Everything below is verifiable; citations are in Appendix B and the method is in
Appendix A.

---

## 1. Where we were

The original overview proposed replacing the human-written "guides" in Guided Equality
Saturation (POPL 2024) with LLM/ML guidance, with two threads:

- **Thread 1:** LLM proposes high-level rewrite checkpoints; the e-graph supplies the
  sound low-level rewrite chain.
- **Thread 2:** broader agentic compiler-LLM cooperation, with tests or compiler passes
  instead of e-graph proofs as the correctness substrate.

It listed nine open problems (§5.1–5.9), a five-phase seven-week plan, and flagged the
constant-time/security angle (§5.7) as the most ambitious option and the one overlapping
with our existing side-channel tooling.

`original/adversarial-search.md` then argued NO-GO for the broad project and proposed two
survivors: a **learned stop/continue controller** for equality saturation, and **guide
usefulness prediction**.

## 2. Why the original direction is dead

### 2.1 The core framing is occupied (Thread 1)

The overview's sentence — *"the third row is the new thing"* — was a reasonable
characterization in early 2025 and is no longer defensible:

| Work | Venue / date | What it does | Why it kills the framing |
|---|---|---|---|
| Guided Equality Saturation | POPL 2024 | Human-specified checkpoints | The baseline being replaced |
| Machine Learning Guided Equality Saturation | EGRAPHS 2025 | Explicitly: "replace the expert providing the guides with a machine learning model" | Is exactly §5.1's proposal, stated as their research direction |
| **LGuess** | arXiv 2511.00403, EGRAPHS 2025 | LLM proposes checkpoints; e-graph supplies sound rewrite chains | Is exactly Thread 1, implemented and evaluated |
| **EggMind** (LLM-Guided Strategy Synthesis) | arXiv 2604.17364, Apr 2026 | LLM synthesizes full EqSat strategies: rule partitioning, scheduling, tractability guidance, motif caching | Closes §5.4 (unifying checkpoints and strategies); reports 45.1% lower cost, 69.1% lower peak RAM |

So §5.1 (generalization), §5.3 (rule synthesis — also Ruler/Enumo lineage), §5.4
(checkpoint+strategy unification), and the "new subfield" claim itself are all occupied.
The other §5 items are listed in §2.5.

### 2.2 The two fallback survivors are occupied

The first adversarial search rated both at "novelty 6?, investigate" and told us to run a
dedicated novelty gate on them. We ran it. Both fail:

- **Learned stop/continue controller = Omelette** (MPhil, University of Cambridge, 2022;
  `github.com/ucamrl/eqs`). A GAT + PPO reinforcement-learning agent over e-graph
  construction whose action space includes an explicit **`end` action**: *"stop an episode
  if it believes the optimal expression is already represented and that additional rewrite
  rule applications will not help."* Its stated motivation is verbatim the motivating
  problem: *"egg has no method of knowing when to stop when saturation is impossible…
  even if it could have extracted the optimal expression long ago."*
  Also in this space: MCTS-GEB (arXiv 2303.04651, 2023), Aurora (arXiv 2407.12794, 2024),
  and Caviar's non-provable-pattern early stopping (arXiv 2111.12116).
- **Guide usefulness prediction ≈ EggMind's tractability guidance** — the paper
  describes exactly "tractability guidance" as part of its strategy search.

### 2.3 The security/constant-time niche fails on both axes

This was the part of the original overview most of us found most compelling (§5.7), and
the first adversarial search rated it 6–7/10 novelty. Two separate problems:

**(a) Novelty — a direct collision nobody had found.** **Cryptonite** (arXiv 2505.14657)
already runs egg-based equality saturation on **straight-line cryptographic kernels from
Fiat Cryptography** — Curve25519 and secp256k1, the exact proposed domain. It even
discusses the security property: *"critical properties of the original code, particularly
those related to constant-time arithmetic… are preserved."* The argument that crypto
kernels are the one domain where EqSat is natively adequate is therefore not an
observation we can claim; it is already someone's design rationale. Separately,
**CryptOpt** (PLDI 2023, Distinguished Paper) already uses an **e-graph inside its
Coq-verified equivalence checker**, so we cannot write "no prior work puts e-graphs in a
verified cryptographic pipeline" either.

**(b) Feasibility — an abstraction-level problem, not an engineering one.** Constant-time
is a property of **control flow and memory addresses**. A straight-line bitvector e-graph
term has *neither*. A taint or e-class-analysis constraint attached to e-graph terms is
therefore **vacuous** — every term passes, because nothing branches or indexes at that
level. The leakage that matters appears at *lowering*: integer division, secret-dependent
shifts, register spills. Those are properties of the lowering function, not of the term.
Only two architectures exist:

- **Per-rule admissibility** — lower both sides of each candidate rewrite and check the
  leakage profiles agree. Tractable, but the mechanism is a *rule filter*, not a property
  of the saturation substrate. This is CryptOpt's architecture applied to a different
  search method, and the novelty claim shrinks accordingly.
- **Model the target inside the e-graph** — then EqSat runs over x86-64 with memory and
  flags, i.e. the intractable representation problem, while competing with CryptOpt's
  verified checker. Out of scope.

Two further problems: the word "verified" is unsupportable with our described tooling
(TIMECOP is dynamic and statistical, not a proof), and the whole area is crowded —
Breaking Bad (2024), Fun with Flags (2025), CTgrep, CT-LLVM, an active LLVM `ct.select`
RFC, FaCT, Jasmin, CompCert-CT, RoboCop (PLDI 2025), plus security-aware register
allocation (SecCG, POMMES, CoMEMS, SNIP). And the performance baseline is hand-tuned
assembly in a domain where CryptOpt itself only beats hand-tuned libsecp256k1 by ~1.04×.
We would be carrying an extra constraint into an area where the state of the art is
hand-tuned assembly.

**Net:** novelty revised from 6–7 to about 4/10, feasibility 3/10.

### 2.4 The schedule was internally infeasible

The overview's own phases sum to **11 weeks at their minimum** (1 + 2 + 2 + 4 + 2) before
any contingency, and that assumes the e-graph infrastructure, the LLM interface,
extraction, LLVM/MLIR integration, model training, baseline reproduction, and evaluation
all work. The document's own §5.1 names control flow + memory + side effects as the hard
frontier — which is precisely where equality saturation is least tractable. This is not a
planning nitpick; it is the reason two of the three failure modes above compound.

### 2.5 Status of every §5 open problem in the original overview

| § | Proposed direction | Status |
|---|---|---|
| 5.1 | Generalize to real compiler IR (LLVM/MLIR) | **Dead.** Hard representation problem (CFG, memory, aliasing, poison) + actively worked: `eqsat` MLIR dialect, Tamagoyaki, E-Path. "We applied it to LLVM" is not novelty. |
| 5.2 | Checkpoint-extraction sample efficiency | **Weak (4–5).** Improving an internal component of a 2025 workshop paper; no new algorithmic principle. |
| 5.3 | LLM proposes rules, SMT verifies | **Weak (5).** Ruler + Enumo lineage; the LLM is swapped in as proposal generator. |
| 5.4 | Unify checkpoints and strategies | **Occupied.** EggMind. |
| 5.5 | Agent participates in the cost model | **Weak (5).** Reviewer's first question: why isn't this hyperparameter search? Competes with SmoothE, e-boost, adaptive extraction. |
| 5.6 | Bridge formal EqSat + agentic testing | **Crowded (5–6).** Agentic Code Optimization, LLM-Vectorizer, Magellan. |
| 5.7 | Security / constant-time EqSat | **Dead on novelty and feasibility.** See §2.3. |
| 5.8 | Shared benchmark suite | **Low novelty (4).** |
| 5.9 | Ablate LLM vs ML vs human guides | **Low novelty (4–5), high feasibility.** The one thing that finishes; not enough on its own. |

## 3. Plan A: the pivot

### 3.1 What changed

**From:** make equality saturation scale by replacing human/LLM guidance in general
purpose compiler IR.

**To:** **probing-secure equality saturation** — use equality saturation to search the
space of *masked cryptographic circuits* subject to a *probing-security* constraint.

Concretely: a secret is split into shares; every intermediate wire must be statistically
independent of the secret. Existing tools either *generate* masked circuits from fixed
gadget libraries or *verify* a circuit after the fact. **Nobody uses equality saturation
to optimize under the security constraint.** We build that, and we study the algorithmic
problem it creates: **security-constrained extraction**.

### 3.2 The novelty claim, stated precisely

> We are not the first to use e-graphs in side-channel reasoning — **superVer** (EGRAPHS
> 2024, work-in-progress) uses equivalence graphs to *verify* threshold probing security.
> Our contribution is the *optimization* problem: selecting a cost-minimal circuit from
> an e-graph when the admissible set is defined by a probabilistic independence property
> that is a per-class label at first order and a set-valued hyperproperty at higher orders.

That distinction is real and is the defensible part. Supporting observations:

- **superVer** verifies a given design; no search, no extraction, no cost optimization.
- **Masked-circuit optimizers exist but without e-graphs:** Rosita (NDSS 2021, fixed
  rewrite rules + leakage emulator), Eldib & Wang (CAV 2014, SAT synthesis), AGEMA
  (TCHES 2022, BDD/ANF gadget mapping), COMPRESS (TCHES 2024, constraint programming),
  Feldtkeller et al. (ePrint 2022/882, MLIR randomness reuse), TETRIS, Tornado's
  refresh-placement search.
- **E-graphs carry non-algebraic side conditions already** — constraint-aware e-graphs
  (`ASSUME`, Coward et al.) and colored e-graphs (Singher & Itzhaky) — but never a
  security property. We must cite these as methodological precedent.

Assessed novelty: **~6/10** (verified absent; main risk is that superVer's group adds the
optimization step first). Honest, not inflated.

### 3.3 Why this is feasible for us specifically

- **It stays in our lane.** Equality saturation we have been reading for weeks; masked
  circuits are straight-line Boolean circuits, which is the *native* EqSat domain. The
  control-flow/memory problem that killed §5.7 does not arise.
- **Tooling exists and is verified:** `egg`/`egglog-python` for the engine; VerifMSI
  (pure Python) and tightPROVE for independent security oracles; MaskedVerifBench,
  VerifMSI's gadget set, REBECCA's `dom_and.v` and Tornado samples as fixtures.
- **The critical mechanism is implementable:** first-order probing security is checkable
  by symbolic/exhaustive simulation at gadget scale (tens of lines of code, already
  working — see §4).

## 4. The feasibility check we ran today

We did not want to recommend this on paper alone, so we built the smallest thing that
could falsify the central assumption:

> **Premise:** unrestricted Boolean equality saturation plus cost-minimal extraction
> actually turns a secure masked circuit into a functionally equivalent but
> probing-insecure one.

If that were false — if unconstrained extraction stayed secure — the project's motivation
would collapse. So we tested it directly.

### 4.1 What was built

`experiments/premise_test/` (uv-managed, no third-party runtime dependencies):

- `egraph.py` — a minimal equality-saturation e-graph (union-find, hashcons, rebuild,
  saturation, cost extraction, materialization) with a Boolean rule set split into core
  algebraic rules and the share-refolding rules (distributivity/factoring).
- `masked.py` — masked circuit IR plus a **first-order probing-security checker**: for
  each secret assignment, enumerate all free-uniform assignments, and compare each wire's
  value **distribution** across secrets.
- `run.py` — the experiment; `test_premise.py` — 7 regression tests; `RESULTS.md` — the
  written record.

### 4.2 Results

**Checker validation:**

| Fixture | Expected | Verdict |
|---|---|---|
| Masked buffer `(a0^r, a1^r)` | secure | SECURE |
| ISW masked AND (correct construction) | secure | SECURE |
| Naive masking via unmasked intermediate `(a0^a1)&(b0^b1)` | insecure | INSECURE — flags the unmasked secrets |

**Premise test — saturate secure ISW AND, extract by cost:**

| Ruleset | AND | XOR | Gates | Functionally equiv. | Security |
|---|---:|---:|---:|---|---|
| Core only (comm/assoc/identity/involution/idempotence/annihilator) | 4 | 4 | 8 | yes | **SECURE** |
| Full (+ distributivity + factoring) | 3 | 4 | **7** | yes | **INSECURE** |

With the full ruleset the extractor returns a circuit that is **one gate cheaper** than the
secure ISW gadget and functionally identical (verified over all 32 input assignments), but
which materializes `xor(b0, b1)` — that is the **unmasked secret `b`** — as an internal
wire, plus `and(a1, xor(b0,b1))` which depends on it.

**Conclusion: the premise holds, and the failure is systematic.** The insecure circuit is
*cheaper*, so a cost-only extractor is actively biased toward it. The enabling rule is
factoring `(x&y)^(x&z) → x&(y^z)`, i.e. distributivity run backwards to refold shares.
Core algebraic rules alone left the circuit secure on this fixture. That is precisely the
gap security-constrained extraction has to close.

### 4.3 An unplanned finding that strengthens the case

While building the fixture we wrote an "ISW" circuit with a naive XOR tree — same final
function, but `r` folded in too late. **The checker flagged it as insecure, correctly:**
the intermediate `a0&b1 ^ a1&b0 = a0·b ^ a·b0` leaks. Real ISW is secure only because the
fresh random is folded into every intermediate of the `c1` chain. Two takeaways: the
security property is genuinely structure- and order-sensitive (which is the whole reason
e-graph search is interesting here), and our checker is doing real work rather than
rubber-stamping.

### 4.4 What this does and does not prove

**Does prove:** the central premise; that a first-order checker is implementable at gadget
scale with no dependencies; that a naive e-graph plus cost extraction reproduces the
failure; and that distributivity/factoring is the specific culprit.

**Does not prove:** that the security constraint leaves *useful* optimization freedom at
scale, or that we beat fixed-gadget constructions on real benchmarks. Those are the open
empirical questions and they are the project.

**Known limitations (must be closed before any security claim):**

1. The checker is validated against **internal fixtures only**. Cross-validation against
   an independent tool (VerifMSI or tightPROVE) is the trust boundary and is the next task.
2. The e-graph is minimal (tree-cost fixed point, no scheduler). Should be re-confirmed
   with `egglog`/`egg` before being treated as a systems result.
3. One gadget (ISW AND), first order, 2 shares, glitch-free model only. Needs the
   MaskedVerifBench gadget set and higher-order tests.

## 5. What we need from you

1. **Read `docs/probing-secure-eqsat-proposal.md`** — the full Plan A proposal (title,
   novelty, prior-art matrix, architecture, rule taxonomy, evaluation plan, risks,
   timeline). It is written to be review-1 ready.
2. **Sanity-check the pivot itself.** The strongest objection we know of is: *"superVer
   already did e-graphs + probing security; is optimization-under-constraint really a
   different problem?"* Our answer is in §3.2, but if you can break it, we want to know
   now, not in week six.
3. **Agree on the go/no-go experiment.** The 30% milestone doubles as the premise test we
   already ran; the next gate is the external-oracle cross-check. If the checker disagrees
   with VerifMSI/tightPROVE on any fixture, we stop and fix before building anything else.
4. **Volunteer for one of the three tracks** (proposal §19): search/extraction,
   security/semantics, benchmarks/evaluation.
5. **Do not spend time on the original direction.** In particular, do not build an e-graph
   prototype for general compiler IR "to see if it works" — that is the single most
   expensive way to rediscover §2.

## Appendix A — how these claims were verified, and how confident we are

- **Novelty claims:** adversarial literature search with 30+ query formulations, direct
  fetching of the primary source for every load-bearing citation (arXiv abstract pages,
  venue listings, project repos), and explicit falsification attempts. Search query lists
  are recorded in `docs/adversarial-search-2.md` §11.4 and the premise-test `RESULTS.md`.
- **The first search's citations were independently re-verified** and all check out, so
  its NO-GO verdict on the broad project is trustworthy. Its two survivor recommendations
  were the part that did not hold up.
- **Confidence:**
  - Original direction dead: **high** (multiple independent, verified collisions).
  - Plan A novelty ~6/10: **medium-high**; the residual risk is superVer/eVer's line
    adding optimization, which we should monitor before committing to a venue.
  - Plan A feasibility: **medium-high** for the prototype and the premise; **medium** for
    a publishable empirical win, because the security constraint might leave little
    optimization freedom (a null result is a real possible outcome, and is a reportable
    finding, but it is not the story we want).
- **Honest statement about certainty:** novelty is a negative claim and cannot be proven
  from a search. What we have is: every collision cited here was verified by fetching the
  source; the searches that came up empty are recorded; and the residual risk is stated.
  Anyone claiming 100% certainty about novelty is wrong.

## Appendix B — key citations

**Original direction (the collisions)**
- Koehler, Goens, Bhat, Grosser, Trinder, Steuwer. *Guided Equality Saturation.* POPL 2024.
- *Machine Learning Guided Equality Saturation.* EGRAPHS 2025 (Steuwer group).
- Peng, Ji, Xiong. *Equality Saturation Guided by Large Language Models (LGuess).* arXiv
  2511.00403, EGRAPHS 2025.
- Yin, Xiao, Luo, Zou, Liang. *LLM-Guided Strategy Synthesis for Scalable Equality
  Saturation (EggMind).* arXiv 2604.17364, Apr 2026.
- Mikek, Vashchilenko, Lu, Xu. *Agentic Code Optimization via Compiler-LLM Cooperation.*
  arXiv 2604.04238, Apr 2026.
- Chen et al. *Magellan.* arXiv 2601.21096, Jan 2026.
- Omelette (stop/continue RL): MPhil thesis, University of Cambridge, 2022;
  `github.com/ucamrl/eqs`. Related: MCTS-GEB (arXiv 2303.04651), Aurora (arXiv
  2407.12794), Caviar (arXiv 2111.12116).

**Security / constant-time (why §5.7 is dead)**
- Cryptonite. arXiv 2505.14657 (EqSat on straight-line Fiat crypto kernels).
- CryptOpt. PLDI 2023, arXiv 2211.10665 (e-graph inside a Coq-verified equivalence
  checker).
- Schneider et al. *Breaking Bad: How Compilers Break Constant-Time Implementations.*
  arXiv 2410.13489.
- *Fun with flags: How Compilers Break and Fix Constant-Time Code.* arXiv 2507.06112.
- CTgrep; CT-LLVM (ePrint 2025/338); LLVM `ct.select` RFC (discourse.llvm.org, 2025).
- Barthe et al. *Formal Verification of a Constant-Time Preserving C Compiler.* ITP 2020.
- Kolosick et al. *Robust Constant-Time Cryptography (RoboCop).* PLDI 2025.

**Plan A (novelty boundary and tooling)**
- Treff, Pauls, Orlt, Gourjon. *superVer: Verifying Probabilistic Independence of
  Systems of Expressions using Equality Saturation.* EGRAPHS 2024 (WIP) — closest prior
  art; verification only.
- Coward, Constantinides, Drane. *Automating Constraint-Aware Datapath Optimization using
  E-Graphs.* arXiv 2303.01839. And Singher, Itzhaky. *Colored E-Graphs.* arXiv 2305.19203.
- Ishai, Sahai, Wagner. *Private Circuits.* CRYPTO 2003 (ISW).
- Barthe et al. *Strong Non-Interference and Type-Directed Higher-Order Masking.* CCS 2016.
- Belaïd, Dagand, Mercadier, Rivain, Wintersdorff. *Tornado.* EUROCRYPT 2020.
- Knichel, Moradi, Müller, Sasdrich. *AGEMA.* TCHES 2022.
- Cassiers, Gigerl, Mangard, Momin, Nagpal. *COMPRESS.* TCHES 2024.
- Feldtkeller et al. *Randomness Optimization for Gadget Compositions.* ePrint 2022/882.
- Shelton et al. *Rosita.* NDSS 2021. Eldib, Wang. CAV 2014.
- Belaïd, Goudarzi, Rivain. *tightPROVE.* ASIACRYPT 2018 (oracle).
- VerifMSI / LeakageVerif (Python oracle), MaskedVerifBench (fixture corpus).

**Reproduce the feasibility check**
```
uv sync
uv run python experiments/premise_test/run.py
uv run pytest -q          # 7 regression tests
```
