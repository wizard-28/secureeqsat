I went after the **entire research direction described in the uploaded document**, including each proposed gap in §5, the claimed novelty of “LLM/agent + equality saturation,” the LLVM/MLIR ambitions, and the 7-week plan.

My conclusion is quite a bit harsher than the document's own framing.

# Executive verdict

## **NO-GO for the broad project.**

The report is describing a **real and exciting research area**, but it has aged badly even within the 2025–2026 literature window. Several of the “open problems” it identifies are now directly occupied by work from 2025/2026.

The most important collision is this:

> The proposed project says: _replace human guidance/checkpoints with ML/LLM guidance to make equality saturation scale._

But there is already:

- **Guided Equality Saturation** — human checkpoints, 2024. ([POPL 2024][1])
- **Machine Learning Guided Equality Saturation** — explicitly replacing the human guide with ML, presented at EGRAPHS 2025. ([PLDI 2025][2])
- **LGuess** — LLM-guided checkpoint generation between e-graph saturation stages, 2025. ([arXiv][3])
- **EggMind / LLM-Guided Strategy Synthesis** — 2026, explicitly synthesizing complete EqSat strategies, including rule selection/scheduling, with measurable improvements. ([arXiv][4])

So the document's central framing—

> “LLM/agent-guided equality saturation is a new research program”

—is now **true historically but no longer a safe novelty position for a student project in September 2026**.

---

# 1. The central idea is already occupied

Your document divides the field into:

```text
LLM
  ↓
high-level checkpoint/strategy
  ↓
e-graph
  ↓
sound low-level rewriting
```

and identifies that as the key new direction.

That was a reasonable framing in early 2025.

But **LGuess already does exactly this**:

> LLM proposes high-level rewrite checkpoints; equality saturation supplies the low-level rewrite chain. ([arXiv][3])

And it isn't merely conceptual; the authors implemented a prototype and evaluated it against both normal equality saturation and direct LLM rewrite-chain generation. ([PLDI 2025][5])

So this is dead:

> “Build LLM-guided EqSat where the LLM proposes intermediate checkpoints.”

**Novelty: ~2/10.**

---

# 2. “Use ML instead of humans to generate guides” is also already occupied

This is an even more direct collision.

Your §5.1 says:

> nobody has shown checkpoint-based LLM guidance on messy real compiler IR.

Your §5.2 suggests improving LGuess's checkpoint extraction.

But the EGRAPHS 2025 **Machine Learning Guided Equality Saturation** work explicitly says its objective is to automatically generate the guides previously supplied by human experts. ([PLDI 2025][2])

Their paper goes further than the overview suggests: they investigate a learned guide-generating model and deliberately choose a structured model rather than an ordinary GNN. ([Michel Steuwer][6])

That kills the idea:

> “Train a model that generates the guides/checkpoints.”

**Novelty: ~3/10.**

It also means the document's proposed contribution:

> “Replace the expert providing guides with a machine-learning model”

is essentially a direct restatement of their published research direction.

---

# 3. EggMind attacks the next obvious novelty escape hatch

Suppose you say:

> Fine, we'll do not just checkpoints, but the **whole strategy**.

That's now occupied too.

The 2026 **EggMind** work introduces `EqSatL`, an explicit language for reusable EqSat strategies, and an LLM-guided workflow that searches over those strategies. It includes **rule-partitioning, scheduling, proof-derived rewrite-motif caching, and tractability guidance**. ([arXiv][4])

And its reported improvements are not tiny:

> 45.1% lower final cost and 69.1% lower peak RAM relative to full EqSat on vectorization benchmarks, with transfer to XLA and a logic-synthesis case study. ([arXiv][4])

That directly attacks your §5.4:

> “Unifying checkpoints and strategies.”

Your proposed:

```text
LLM chooses:
  checkpoint
  +
  rule subset
  +
  saturation schedule
```

is dangerously close to:

```text
EggMind:
  strategy DSL
  +
  rule selection/scheduling
  +
  tractability guidance
```

**Novelty: ~3–4/10.**

This is probably the single biggest reason I would not let your team start this project.

---

# 4. §5.1 “Generalize to real compiler IR” is not enough

The document argues:

> Nobody has shown checkpoint-guided LLM EqSat on large, messy compiler IR with control flow, memory and side effects.

This sounds like a good gap, but there is a fundamental problem:

### “We took an existing EqSat method and applied it to LLVM/MLIR” is not automatically research novelty.

And the infrastructure is moving rapidly toward exactly this.

In 2025, `eqsat` was proposed as an **MLIR-native equality-saturation dialect**, intended to keep e-graphs inside MLIR and allow them to interact with other compiler passes. ([arXiv][7])

In 2026, LLVM developers were discussing **Tamagoyaki: MLIR-Native Equality Saturation**, explicitly aiming to represent equivalences directly in MLIR and make more complex compiler passes part of EqSat. ([LLVM][8])

There is also a 2026 **E-Path** proposal specifically targeting equality-saturation-style optimization over **control-flow graphs**, rather than only expression trees. ([arXiv][9])

So your proposed:

```text
“Let's finally bring LLM-guided equality saturation to real compiler IR.”
```

is stepping into a **very active, rapidly filling space**.

It may still be publishable as an engineering extension, but I would not bet your college project's novelty score on it.

---

# 5. The “messy LLVM IR” problem is much harder than the document makes it sound

This isn't just a missing implementation.

Classic EqSat works extremely naturally on terms:

```text
a + (b * c)
```

But LLVM IR includes:

```text
CFG
SSA
φ nodes
loads
stores
aliasing
exceptions
calls
control dependencies
undefined behavior
poison
memory ordering
target-specific semantics
```

The difficulty is well known.

UW PLSE explicitly notes that most EqSat applications operate on **pure expressions**, while imperative programs introduce context/linearity problems. ([UW PLSE][10])

And Cranelift's e-graph RFC explicitly calls out control-flow embedding and re-extraction as major design problems. ([GitHub][11])

This means that your statement:

> “nobody has done this on messy real IR”

should not be interpreted as:

> “there's a convenient unclaimed project here.”

It may instead mean:

> **there is a hard foundational representation problem here that three students should absolutely not attempt in seven weeks.**

---

# 6. LLVM/MLIR-native EqSat is itself becoming a research area

This is another subtle problem.

Your document proposes an external `egg`/`egglog` layer and then potentially LLVM/MLIR integration.

But the ecosystem now has:

```text
eqsat dialect
Tamagoyaki
Slotted E-Graphs
E-Path
Incremental EqSat
Oatlog
Destructive EqSat
```

all appearing around the 2025–2026 period. ([PLDI 2025][12])

So you'd be entering a research community that is currently producing multiple infrastructure papers **faster than a 7-week student team could digest them**.

That's bad territory for your particular objective.

---

# 7. §5.2 “sample-efficient checkpoint extraction” is already too close to LGuess

Your document identifies:

> LGuess's checkpoint extraction as an open systems problem and proposes distilling it into a smaller amortized model.

But this is essentially attempting to improve an **internal component of the LGuess method**.

That's not necessarily impossible as research.

However, your contribution becomes:

> “Take a 2025 workshop paper, replace one learned component with a cheaper model, measure speed.”

That is a **weak novelty position** unless you discover a genuinely new algorithmic principle.

I'd score it:

**Novelty 4–5/10.**

---

# 8. §5.3 “LLM proposes new rewrite rules, SMT verifies them” sounds good—but Ruler is a huge problem

Your report correctly cites Ruler.

But then proposes:

> LLM proposes candidate rules → independently SMT-verify them.

The novelty defense would be:

> “Ruler synthesizes rules, but not with an LLM.”

True—but the research contribution would still risk becoming:

```text
Ruler
+
LLM as proposal generator
+
existing SMT verifier
```

That's a much weaker position than it first appears.

Ruler already automatically infers rewrite rules and uses equality saturation to efficiently shrink candidate rulesets; its published results show 5.8× smaller rulesets and 25× faster synthesis versus a CVC4-based approach. ([arXiv][13])

And Enumo goes further by providing programmable, strategically guided theory exploration. ([SPLASH 2023][14])

So:

> “Use an LLM to invent rules, SMT-check them”

is **not enough** as a research contribution.

I'd score it **5/10**, maybe 6 with a truly unusual synthesis mechanism.

---

# 9. §5.5 “let the LLM choose the cost model” is interesting, but probably not deep enough

The document calls this unexplored:

> agent participates in cost-model selection/adaptation.

This is one of the more genuinely interesting gaps.

But there's an immediate question:

```text
Why an LLM?
```

Suppose your algorithm is:

```text
LLM looks at e-graph/domain
       ↓
chooses cost weights
       ↓
extract
```

A skeptical professor asks:

> Why isn't this just hyperparameter search?

And now you are competing against:

- learned cost models,
- SmoothE,
- adaptive extraction,
- e-boost,
- autotuning,
- general ML-based optimization.

SmoothE already treats extraction as a differentiable optimization problem.

e-boost explicitly attacks the heuristic-vs-exact extraction tradeoff using adaptive pruning and warm-started exact solving. ([arXiv][15])

So I wouldn't spend seven weeks arguing that an LLM should tune cost weights.

**Novelty: ~5/10.**

---

# 10. §5.6 “combine formal EqSat with agentic test-based verification” is also losing its novelty

The document proposes:

```text
formal e-graph verification
        +
LLM-generated tests
```

as a hybrid verification philosophy.

That sounds sensible, but look at the current agentic compiler literature.

**Agentic Code Optimization via Compiler-LLM Cooperation** explicitly includes:

- compiler components as tools,
- optimization agents,
- a test-generation agent,
- an orchestration agent,
- compute-budget allocation across compiler levels. ([arXiv][16])

So:

> “LLM proposes changes, tests verify them, conventional compiler machinery preserves correctness”

is already a mainstream architectural pattern in the exact field you're considering.

Your extra contribution would have to be specifically:

> **formal e-graph proof for some transformations + generated testing for transformations outside the equational substrate, with a principled trust boundary.**

That _could_ be interesting.

But implementing the trust boundary correctly is substantially harder than the document suggests.

**Novelty: ~5–6/10.**

---

# 11. §5.7 constant-time EqSat is the most genuinely interesting variant

This is the one place where I would not immediately kill the underlying question.

The proposal is:

```text
LLM proposes EqSat checkpoints
             ↓
e-graph only allows
constant-time-preserving rewrites
             ↓
extract optimized CT program
```

Your document argues that this would connect equality saturation with CryptOpt without simply reproducing it.

There is a plausible research question here:

> **Can security properties be incorporated into the EqSat equivalence relation/cost/extraction process rather than used only as post-hoc verification?**

That is genuinely more interesting than:

> “Use an LLM to optimize code.”

However, you have a problem:

### The security literature already has verified constant-time compilation/search.

CryptOpt performs verified compilation using randomized program search for cryptographic primitives. Your own document correctly cites it.

There is also formal work on compilers preserving cryptographic constant time. ([DOI][17])

So you'd have to prove that:

```text
CryptOpt:
randomized search + verification
```

is fundamentally different from:

```text
your system:
EqSat + security-constrained extraction
```

That difference **does exist conceptually**, but implementing a sound CT-aware EqSat framework is not a seven-week project.

**Novelty: ~6–7/10**

**Feasibility: ~3/10**

So this is a fascinating PhD-style direction, not your college project.

---

# 12. §5.8 benchmark-suite contribution is weak

The report says there is no common benchmark suite for LLM-guided EqSat.

That may be true.

But:

> “We created a benchmark suite”

is generally a **low novelty / low research-depth contribution** unless the benchmark itself enables discoveries the field could not previously make.

For your grading objective:

**~4/10 novelty.**

Not enough.

---

# 13. §5.9 “LLM vs ML vs human guide” is a useful experiment, not a strong project

This may actually be an important missing experiment.

Your report correctly notices that LGuess compares against plain EqSat and direct LLM rewriting, but not necessarily against strong non-LLM guides.

A rigorous experiment could be:

```text
human guides
ML guides
LLM guides
MCTS
random guides
full EqSat
```

and measure:

```text
quality
runtime
peak memory
number of LLM calls
generalization
```

That could be a **nice paper section**.

But as the entire project, it is mostly an evaluation study.

**Novelty: ~4–5/10.**

---

# 14. The “superoptimization” angle is much more crowded than the document implies

The document moves naturally from EqSat into superoptimization.

But the field already has:

```text
STOKE
Souper
Alive2
CryptOpt
e-graph systems
LLM-Vectorizer
Astra
Agentic Code Optimization
Magellan
```

and now multiple LLM/e-graph systems.

LLM-Vectorizer is especially relevant: it already has an LLM proposing optimization transformations, uses test-based feedback, and uses Alive2 for correctness validation. It reported speedups over Clang/GCC/Intel in its target benchmarks. ([CGO 2025][18])

So:

> “LLM proposes optimization, formal checker ensures correctness”

is definitely not novel enough.

---

# 15. The project has an enormous scope problem

The document's proposed timeline is internally unrealistic.

It gives:

```text
Phase 0: 1–2 weeks
Phase 1: 2–3
Phase 2: 2–4
Phase 3: 4–6
Phase 4: 2–3
```

as if these are roughly sequential.

Even taking the minima:

```text
1 + 2 + 2 + 4 + 2 = 11 weeks
```

before meaningful contingency.

And that assumes:

- e-graph infrastructure works,
- the LLM interface works,
- extraction works,
- LLVM/MLIR integration works,
- benchmark translation works,
- model training works,
- baseline reproduction works,
- evaluation works.

That's not a seven-week plan.

---

# 16. Real LLVM/MLIR would destroy the schedule

The document itself admits that the hard frontier is:

> control flow + memory + side effects.

And that's precisely where EqSat becomes difficult.

Compare the worlds:

### Toy polynomial

```text
a * (b + c)
```

Easy.

### Real IR

```text
%v = load ptr %p
%cmp = icmp ...
br i1 %cmp, label %A, label %B
...
store %x, ptr %q
```

Now correctness involves:

- memory,
- aliasing,
- control dependence,
- dominance,
- poison/undef,
- exception behavior,
- side effects,
- potentially concurrency.

You don't just need rewrite rules.

You need an **IR semantic model suitable for equational reasoning**.

That is research by itself.

---

# 17. There is another killer: the benchmark/domain may determine the entire result

LGuess currently has a particularly controlled benchmark: multivariable polynomial factorization. ([arXiv][3])

EggMind reports vectorization-focused benchmarks and transfers to XLA/logic synthesis. ([arXiv][4])

This means if your team picks:

```text
polynomials
```

you are directly recreating LGuess.

If you pick:

```text
vectorization
```

you're stepping toward EggMind and LLM-Vectorizer.

If you pick:

```text
RTL
```

you collide with ASPEN and ROVER.

If you pick:

```text
GPU kernels
```

you encounter Astra. ([arXiv][19])

If you pick:

```text
LLVM compiler heuristics
```

Magellan is now a direct competitor. ([arXiv][20])

That leaves surprisingly little obvious territory.

---

# 18. The broad “LLM + compiler” framing is now extremely crowded

Your report characterizes the third row as a new subfield:

> LLM/agent + formal substrate.

That framing is now much harder to defend.

By 2026 we have:

```text
LGuess
ML-guided EqSat
EggMind
ASPEN
Agentic Code Optimization
Magellan
LLM-Vectorizer
Astra
```

covering different versions of:

```text
model/agent
     ↓
compiler/search machinery
     ↓
verification/evaluation
```

([arXiv][3])

So **“LLM-guided compiler optimization with verification” is now a research area, not a research gap.**

---

# 19. But there IS one idea I would salvage

Not the project.

One research question.

### **Can a learned guide predict when equality saturation should stop before the e-graph explodes?**

Notice the change.

Not:

```text
LLM tells EqSat what to do.
```

Not:

```text
LLM generates checkpoints.
```

Not:

```text
LLM invents rewrite rules.
```

Not:

```text
LLM chooses the entire optimization strategy.
```

Instead:

```text
EqSat running
     ↓
observe current e-graph
     ↓
predict:
"another round is likely valuable"
or
"another round is likely wasteful"
     ↓
STOP / CONTINUE
```

That is a much narrower systems question.

The motivation is real because e-graph explosion is a central practical problem. ([UW PLSE][10])

And the existing recent work focuses heavily on **what guide/strategy to choose**, rather than reducing the problem to a tightly defined learned **continuation decision**.

But even this needs another prior-art gate before I'd approve it, because strategy synthesis and tractability guidance from EggMind are close enough to make me nervous. ([arXiv][4])

---

# 20. Another potentially interesting variant: “guide usefulness prediction”

A stronger formulation might be:

> Given a candidate guide/checkpoint, can we predict whether following it will actually improve the final extracted program **before spending the expensive saturation budget**?

That gives:

```text
candidate guide G
       ↓
cheap predictor
       ↓
expected benefit
       ↓
accept / reject guide
       ↓
expensive EqSat only when worthwhile
```

This is more interesting than generating guides.

Because the research question becomes:

> **How do we evaluate the expected utility of guidance itself?**

That potentially separates:

```text
guide generation
```

from:

```text
guide valuation
```

and could be a tractable 7-week systems project.

But again: **I would not call it novel yet.** EggMind's tractability guidance is close enough that it needs a dedicated search. ([arXiv][4])

---

# 21. My adversarial scorecard for the document's proposed ideas

| Proposed direction                             | Novelty | Depth | 7-week feasibility | Verdict                  |
| ---------------------------------------------- | ------: | ----: | -----------------: | ------------------------ |
| LLM-guided EqSat                               |       2 |     6 |                  6 | ❌ already LGuess        |
| ML-generated EqSat guides                      |       3 |     6 |                  6 | ❌ already active work   |
| LLM strategy synthesis                         |     3–4 |     7 |                  5 | ❌ EggMind               |
| LLM new rewrite rules + SMT                    |       5 |     7 |                  4 | ❌ Ruler/Enumo lineage   |
| LLM cost-model selection                       |       5 |     6 |                  6 | ⚠️ weak novelty          |
| EqSat + agentic testing                        |       5 |     6 |                  5 | ⚠️ crowded               |
| ML-vs-LLM-vs-human guide study                 |     4–5 |     5 |                  8 | ⚠️ evaluation project    |
| Common EqSat benchmark                         |       4 |     5 |                  8 | ❌ not enough            |
| Security/CT-constrained EqSat                  | **6–7** | **8** |              **3** | ⚠️ interesting, too hard |
| **Learned guide usefulness predictor**         |  **6?** | **7** |              **7** | ⭐ investigate           |
| **Learned stop/continue controller for EqSat** |  **6?** | **7** |              **7** | ⭐ investigate           |

---

# 22. One important correction to the document

This sentence is too strong:

> “The third row is the new thing.”

It was a reasonable characterization of a developing research direction, but **not a sufficient novelty claim in September 2026**.

The field has moved extremely quickly.

In particular, EggMind's 2026 paper now makes the exact claim that EqSat strategy design is still a bottleneck and proposes an LLM-guided framework for synthesizing reusable strategies. ([arXiv][4])

---

# 23. The professor-AI test

Imagine your professor uploads this project description and asks an AI:

> **“What is novel?”**

For the current project, I expect something like:

> “The use of an LLM to guide equality saturation is novel.”

But then the AI searches:

```text
LGuess — 2025
Machine Learning Guided Equality Saturation — 2025
EggMind — 2026
ASPEN — 2025
Agentic Code Optimization — 2026
```

and the novelty score collapses.

### Current project

**Professor-AI novelty: ~4/10**

### Narrow “guide usefulness prediction”

Potentially:

**6–7/10**

### Security-constrained EqSat

Potentially:

**7/10**

but feasibility kills it.

---

# 24. Final decision

## **Do not start the broad LLM/equality-saturation project.**

The document is excellent as a **literature map**, but it is not yet a good project specification.

The field is currently moving too quickly:

```text
2024
Guided EqSat
     ↓
2025
ML-guided EqSat
LGuess
ASPEN
eqsat / Slotted E-Graphs
     ↓
2026
EggMind
Agentic Compiler-LLM
Magellan
E-Path
MLIR-native EqSat work
```

([POPL 2024][1])

For your **7-week, 3-person, novelty-first constraint**, I would rank the survivors:

**1. Learned guide usefulness / stop-continue prediction — investigate further.**

**2. Security-constrained EqSat — academically strongest, but probably too difficult.**

Everything else in this document is either **already being done, an incremental extension, or too large for the schedule.**

The particularly important thing is that **we should not now spend another week implementing an EqSat prototype merely because EggMind/LGuess look cool**. The next step should be a narrow adversarial novelty gate on those two surviving formulations, with an explicit requirement to find prior art that kills them if necessary.

[1]: https://popl24.sigplan.org/details/POPL-2024-popl-research-papers/60/Guided-Equality-Saturation?utm_source=chatgpt.com "Guided Equality Saturation (POPL 2024 - POPL Research Papers) - POPL 2024"
[2]: https://pldi25.sigplan.org/details/egraphs-2025-papers/6/Machine-Learning-Guided-Equality-Saturation?utm_source=chatgpt.com "Machine Learning Guided Equality Saturation (EGRAPHS 2025) - PLDI 2025"
[3]: https://arxiv.org/abs/2511.00403?utm_source=chatgpt.com "Equality Saturation Guided by Large Language Models"
[4]: https://arxiv.org/abs/2604.17364?utm_source=chatgpt.com "LLM-Guided Strategy Synthesis for Scalable Equality Saturation"
[5]: https://pldi25.sigplan.org/details/egraphs-2025-papers/12/Equality-Saturation-Guided-by-Large-Language-Models?utm_source=chatgpt.com "Equality Saturation Guided by Large Language Models (EGRAPHS 2025) - PLDI 2025"
[6]: https://steuwer.info/files/publications/2025/Machine_Learning_Guided_Equality_Saturation.pdf?utm_source=chatgpt.com "Machine Learning Guided Equality Saturation"
[7]: https://arxiv.org/abs/2505.09363?utm_source=chatgpt.com "eqsat: An Equality Saturation Dialect for Non-destructive Rewriting"
[8]: https://llvm.swoogo.com/2026eurollvm/session/4050968/tamagoyaki-mlir-native-equality-saturation?utm_source=chatgpt.com "Session Details: 2026 European LLVM Developers' Meeting"
[9]: https://arxiv.org/abs/2605.28694?utm_source=chatgpt.com "E-Path: Equality Saturation for Control-Flow Graphs"
[10]: https://uwplse.org/2025/04/14/Phase-ordering.html?utm_source=chatgpt.com "UW PLSE | What is the phase ordering problem and can equality saturation help?"
[11]: https://github.com/bytecodealliance/rfcs/blob/main/accepted/cranelift-egraph.md?utm_source=chatgpt.com "rfcs/accepted/cranelift-egraph.md at main · bytecodealliance/rfcs · GitHub"
[12]: https://pldi25.sigplan.org/details/pldi-2025-papers/77/Slotted-E-Graphs-First-Class-Support-for-Bound-Variables-in-E-Graphs?utm_source=chatgpt.com "Slotted E-Graphs: First-Class Support for (Bound) Variables in E-Graphs (PLDI 2025 - PLDI Research Papers) - PLDI 2025"
[13]: https://arxiv.org/abs/2108.10436?utm_source=chatgpt.com "Rewrite Rule Inference Using Equality Saturation"
[14]: https://2023.splashcon.org/details/splash-2023-oopsla/68/Equality-Saturation-Theory-Exploration-la-Carte?utm_source=chatgpt.com "Equality Saturation Theory Exploration à la Carte (SPLASH 2023 - OOPSLA) - SPLASH 2023"
[15]: https://arxiv.org/abs/2508.13020?utm_source=chatgpt.com "e-boost: Boosted E-Graph Extraction with Adaptive Heuristics and Exact Solving"
[16]: https://arxiv.org/abs/2604.04238?utm_source=chatgpt.com "Agentic Code Optimization via Compiler-LLM Cooperation"
[17]: https://doi.org/10.1145/3460860?utm_source=chatgpt.com "An Extended Account of Trace-relating Compiler Correctness and Secure Compilation | ACM Transactions on Programming Languages and Systems"
[18]: https://2025.cgo.org/details/cgo-2025-papers/14/LLM-Vectorizer-LLM-based-Verified-Loop-Vectorizer?utm_source=chatgpt.com "LLM-Vectorizer: LLM-based Verified Loop Vectorizer (CGO 2025 - Main Conference) - CGO 2025"
[19]: https://arxiv.org/abs/2509.07506?utm_source=chatgpt.com "Astra: A Multi-Agent System for GPU Kernel Performance Optimization"
[20]: https://arxiv.org/abs/2601.21096?utm_source=chatgpt.com "Magellan: Autonomous Discovery of Novel Compiler Optimization Heuristics with AlphaEvolve"
