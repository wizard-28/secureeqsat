# Project Context — SecureEqSat

**Last updated:** 2026-10-26 (language front end)
**Maintainer:** update this file on every meaningful change (see `AGENTS.md` §7).

---

## 1. Identity

- **Project:** Probing-Secure Equality Saturation — *SecureEqSat*
- **Current framing (after `design/0010`):** three claims, in order —
  1. unconstrained equality saturation is **unsound** for masked-circuit
     optimization, with a concrete mechanism;
  2. it can be **repaired** (exact cross-validated checker, safety labelling,
     security-constrained extraction);
  3. the optimizations worth having are **not function equalities** — the
     re-sharing gap is the research question.
- **Context:** compiler-design research project.
- **Review 1 deliverable:** title + novelty claim + plan (30% implementation is a
  later milestone; its foundations are already built — see §3).
- **Team:** Shreyash Panigrahy, solo since 2026-10-17. Earlier work was done
  as a team (with Sourajyoti Basak and J. Nandhakishor); code authorship is in
  the git history, and earlier contributions must be credited in the paper and
  report.
- **Primary venue target:** EGRAPHS workshop class (theory + negative results),
  decided in `design/0018`.

---

## 2. Summary

Masking splits a secret into random-looking shares and requires every
intermediate wire to be statistically independent of the secret. Existing tools
either *generate* masked circuits from fixed gadget libraries (Tornado, AGEMA,
COMPRESS, POMMES/CoMEMS) or *verify* them (maskVerif, tightPROVE, SILVER,
PROLEAD, VerifMSI). Equality saturation — the non-destructive, order-independent
rewrite search from compiler design — had not been applied to masked circuits at
all.

We have now shown that applying it naively is **unsound**: ordinary Boolean
rewriting (distributivity run backwards) refolds shares and materialises the
unmasked secret, and cost-optimal extraction *prefers* this because it is
cheaper. We have built the exact checker, the safety labelling, and the
security-constrained extraction that repair it — and we have evidence that the
payoff question is harder than it looks, because the optimizations the masking
literature exploits (refresh insertion/removal, randomness reuse, gadget
substitution) are equivalences **up to re-sharing**, not Boolean equalities.

---

## 3. Status

| State | Item |
|---|---|
| ✅ done | Original direction investigated and closed (`docs/original/`, `docs/team-briefing-plan-a.md`) |
| ✅ done | Plan A selected; novelty boundary established; proposal and team briefing written |
| ✅ done | **Trust boundary CLOSED** — VerifMSI cross-check, 1,216 circuits / 21,760 wires, **0 violations** (`design/0005`) |
| ✅ done | **Premise confirmed on two engines** (in-house + egglog), leaking on identical wires |
| ✅ done | **Security-constrained extraction implemented and working** (`design/0006`) — recovers a secure circuit from the insecure optimum |
| ✅ done | **Scalability answered** — `egglog` saturates the two-gadget chain instantly; the in-house blowup was an engine artifact (`design/0009`) |
| ⚠️ negative | **Payoff not demonstrated.** Gadget scale: constrained optimum == known construction. Chain scale: the entire sampled cheap frontier is insecure (`docs/feasibility-report.md` §4) |
| ⚠️ medium | Abstraction-level explanation: the useful optimizations are **not congruences** of the wire-term algebra (`docs/feasibility-report.md` §6, corrected in `design/0011`) |
| ✅ done | **Third adversarial pass** on the reframed proposal: claims corrected, disclaimers added, eVer collision found (`docs/adversarial-search-3.md`, `design/0011`) |
| ✅ done | **Labelling bottleneck resolved at chain scale** — bitsliced exact labeller (`design/0015`): depth-5 chain labelled in ~0.4 s vs ~50 min (est.); identical verdicts vs reference and VerifMSI (22,463 wires, 0 violations) |
| ⏳ deferred | **Symbolic labeller** (ANF/BDD, VerifMSI oracle, pre-filters) — only needed past the bitsliced `2**26` cap (S-box scale) |
| ✅ done | **Re-sharing representation** — shared-value layer in egglog (`design/0016`): R2 (ISW = DOM = HPC1) and R3 (refresh) are ordinary rules there; constrained extraction blocks a cheaper leaking refresh removal; gains only where the start circuit has slack (redundant refreshes 30→18, factoring 20→11); hand-written chain still 18. VerifMSI: 914 wires, 0 violations |
| ✅ done | **Language front end** (`design/0020`, `experiments/frontend/`): a parser, a masking pass, the existing pipeline and a netlist/Verilog emitter. Source programs compile end to end; every compiled circuit is functionally equal to its source and has 0 leaking wires, cross-checked against VerifMSI (6 runs, 0 disagreements). No new research claim |
| ✅ done | **PINI composition analysis** (`design/0019`, `experiments/composition/`): on the PINI fragment safety is a class label again and plain DAG extraction is sound (theory C9). Gadget verdicts agree with VerifMSI; 234 random PINI terms, 0 leaks; Keccak χ to 32 bits (2^128 points) decided in ≤ 0.03 s and certified by VerifMSI; cost premium up to +33 % |
| ✅ done | **Scope widened to the glitch-extended model; theory drafted** (`design/0018`). `docs/theory.md` states the result once for both models (claims C1–C8), each with an executable witness in `experiments/claims/` |
| ✅ probe | **Glitch model: go for the theory, no gains** (`design/0017`). In-house glitch-extended checker agrees with VerifMSI (167 probes, 0 disagreements). Opaque registers block rewriting; transparent registers reproduce the premise (registered DOM 10→5, leaks); occurrence-aware extraction repairs it by placing registers, exactly as with refresh (`experiments/glitch_probe/`) |
| ⚠️ negative | **Tight starts gain nothing.** Keccak chi (3- and 5-bit rows, direct ISW masking) is unchanged under every rule class; the unmodelled lever is randomness reuse (`experiments/resharing/RESULTS.md`) |
| ⚠️ new limit | **Term-based extraction** is now the bottleneck at the value layer (~144 s at chain depth 5) |
| 🔔 realised | **eVer (ePrint 2026/208) now optimizes refresh sequences and gadgets** with re-verification. Repositioned: claim the e-graph + congruence angle, never "optimize refreshes" |

**Headline result:** unconstrained Boolean equality saturation turns a secure
ISW masked AND into a functionally equivalent but probing-insecure circuit, and
the insecure circuit is **cheaper** (7 vs 8 gates) — so the failure is
systematic. Same function, same leak, on two independent engines.

---

## 4. Decision log

Full records in [`design/`](design/README.md).

| ADR | Decision | Status |
|---|---|---|
| `0001` | Pivot from LLM/agent-guided EqSat to probing-secure EqSat (Plan A) | accepted |
| `0002` | Scope: first order, 2 shares, straight-line, glitch-free | superseded by `0018` |
| `0003` | Toolchain: uv + ruff + pytest, devcontainer-managed, no manual installs | accepted |
| `0004` | Minimal in-repo e-graph for the premise test; `egglog`/`egg` for the real engine | accepted |
| `0005` | In-house checker + external-oracle cross-check as the trust boundary | **closed** (0 violations) |
| `0006` | Security-constrained extraction: per-class admissibility + lazy separation oracle | accepted, **prototype implemented** |
| `0007` | Adopt git: trunk-based, logical commits, `.gitignore` authoritative | accepted |
| `0008` | Automate venv creation in `postCreateCommand`; keep git identity local | accepted |
| `0009` | Add `egglog` for the engine feasibility check | accepted, **answered** |
| `0010` | Reframe around soundness and the re-sharing gap | accepted |
| `0011` | Correct the novelty claims after adversarial pass 3 (congruence framing, eVer disclaimer, labelling bottleneck) | accepted |
| `0012` | Make the shared dev container agent-neutral; per-user agents opt in via `.devcontainer/personal/` | accepted |
| `0013` | Publication scope: PDFs tracked, teammate PPTX untracked, no licence until public | accepted |
| `0014` | Provision the VerifMSI oracle for every teammate (shared volume + auto-setup, non-fatal) | accepted |
| `0015` | Bitsliced exact labeller replaces per-class materialisation; symbolic routes deferred | accepted |
| `0019` | PINI composition as an e-class analysis; class-level extraction on the composable fragment | accepted |
| `0018` | Scope: first order, 2 shares, glitch-free **and** glitch-extended; deliverable is a workshop paper | accepted |
| `0017` | Feasibility probe of the glitch-extended model, core scope unchanged | accepted (probe) |
| `0020` | Language front end: parser, masking pass, emitter over the existing pipeline | accepted |
| `0021` | Theory claim C5(b) stated for R3 alone; R1 + R3 admits a secure DAG extraction | proposed |
| `0016` | Shared-value layer: sharings identified by value; R2/R3 as rules; lowering + term-based constrained extraction; cost = gates + randoms | accepted |

---

## 5. Artifact map

| Path | Contents |
|---|---|
| `docs/original/` | Original research overview + first adversarial search — **historical, do not edit** |
| `docs/adversarial-search-2.md` | Second adversarial pass + auditable search record |
| `docs/adversarial-search-3.md` | Third adversarial pass (on the reframed proposal) + scaling measurements |
| `docs/probing-secure-eqsat-proposal.md` | Proposal (revision 3: soundness, repair, congruence obstruction) |
| `docs/team-briefing-plan-a.md` | Team-facing argument for why the original direction is dead |
| `docs/feasibility-report.md` | **Consolidated feasibility checks and confidence levels** |
| `findings/` | **Verification folder**: index of findings F1–F10, `verify.py` re-runs each and writes `outputs/MANIFEST.json` |
| `docs/adversarial-search-4.md` | Fourth adversarial pass: citation check of the theory (T1–T4) |
| `docs/theory.md` | **Theory draft for the paper**: claims C1–C8 with proofs and witnesses |
| `experiments/frontend/` | **Compiler front end**: `lang.py` (parser), `seqc.py` (mask, optimise, verify, emit; CLI), `examples/*.sec`, tests, `RESULTS.md` |
| `experiments/composition/` | PINI checker, VerifMSI PINI/certificate drivers, composition analysis, `run_composition.py`, tests, `RESULTS.md` |
| `docs/adversarial-search-5.md` | Fifth adversarial pass: PINI theorem verification and composition prior art |
| `experiments/claims/` | `test_claims.py` — one executable witness per claim in `docs/theory.md` |
| `docs/getting-up-to-speed.md` | 15-minute orientation for new readers |
| `experiments/premise_test/` | `egraph.py`, `masked.py`, `run.py`, `test_premise.py`, `RESULTS.md` |
| `experiments/oracle_crosscheck/` | VerifMSI driver, cross-check protocol, tests, `RESULTS.md` |
| `experiments/constrained_extraction/` | `constrained.py`, `run_constrained.py`, `run_chain.py` |
| `experiments/egglog_port/` | `port.py`, `kbest.py`, `RESULTS.md` |
| `experiments/labeller/` | Bitsliced exact labeller: `labeller.py`, `test_labeller.py`, `measure.py`, `RESULTS.md` |
| `experiments/glitch_probe/` | Glitch feasibility probe: `glitch.py` (checker), `glitch_driver.py` (VerifMSI), `gextract.py`, `probe.py`, `test_glitch.py`, `RESULTS.md` |
| `experiments/resharing/` | Shared-value layer: `gadgets.py` (lowering), `layer.py` (egglog rules), `extract.py`, `fixtures.py`, `run.py`, `test_resharing.py`, `RESULTS.md` |
| `AGENTS.md` | **Canonical working norms** — read natively by most agents |
| `CLAUDE.md` | Thin `@AGENTS.md` pointer; Claude Code stops reading `AGENTS.md` once any `CLAUDE.md`/`CLAUDE.local.md` exists |
| `.claude/skills/` | Repo procedures as skills — read by both Claude Code and opencode |
| `design/` | ADRs |
| `README.md` | Entry point: what this is, how to run it, dev container instructions |
| `scripts/` | Container provisioning — `setup-tools.sh` (team-wide), `setup-opencode.sh` (opt-in, per user) |
| `.devcontainer/` | Shared **agent-neutral** container; `personal/` holds the gitignored per-user config plus a tracked example |
| `pyproject.toml`, `uv.lock`, `.venv/` | uv project (dev deps: pytest, ruff, egglog) |

---

## 6. Open risks and unknowns

1. **Payoff (HIGH, evidenced).** No secure circuit cheaper than the known
   construction has been found at either scale, and the sampled cheap frontier
   is entirely insecure. Mitigation: the re-sharing formulation (`design/0010`);
   if that fails, the project's deliverable is the soundness + repair + gap
   story, which is already strong.
   *Update 2026-10-11:* the shared-value layer (`design/0016`) finds gains only
   where the start circuit has slack (redundant refreshes, unfactored products);
   the tight hand-written chain still gains nothing, and neither do the
   tight Keccak chi starts (3- and 5-bit rows). The remaining lever is
   randomness reuse across gadgets, which the layer does not model.
2. **Abstraction level (MEDIUM).** The valuable optimizations may not be
   expressible as e-graph equalities at all. This is now the central research
   question rather than an unexamined assumption.
   *Update 2026-10-11 (MEDIUM → LOW for R2/R3):* they are expressible one layer
   up, where sharings are identified by value (`design/0016`); the price is that
   safety stops being a per-class label and extraction must be term-based.
3. **Novelty window (MEDIUM → partially realised; re-checked 2026-10-18,
   `docs/adversarial-search-4.md`: theory claims survive narrowly, glitch
   phenomenon and register placement not claimable).** superVer (EGRAPHS 2024)
   verifies probing security with e-graphs; **eVer (2026) now optimizes refresh
   sequences and gadgets** with re-verification. Reposition onto the soundness +
   congruence framing, which they have not claimed (`design/0011`).
4. **Scope (MEDIUM).** First order, 2 shares, glitch-free and glitch-extended
   (`design/0018`). PINI composition in the glitch-free model only (C9,
   `design/0019`); nothing on SNI, higher orders or glitch-robust composition,
   and no claim about transitions or register timing.
5. **Labelling bottleneck (HIGH → LOW at chain scale, measured).** The
   bitsliced labeller (`design/0015`) labels a depth-5 chain in ~0.4 s, but is
   still exact and exponential: spaces above `2**26` are refused. S-box-scale
   circuits will need the deferred symbolic route (VerifMSI oracle, ANF/BDD,
   structural pre-filters, on-demand frontier labelling).
6. **Oracle dependency (LOW).** The cross-check requires an external GPL tool;
   the tests skip when it is absent, so CI without the oracle silently loses
   coverage.
7. **Licensing (LOW).** VerifMSI/tightPROVE are GPLv3 — external processes only.
8. **Publication (LOW while private, HIGH on a public flip).** The teammate PPTX
   was untracked but **remains in git history** (`df67155`), and there is no
   `LICENSE`. Both must be handled before the repository goes public —
   `design/0013` carries the purge command.
9. **Container friction (LOW).** The per-user agent configuration must be
   re-selected on each rebuild and is unavailable in Codespaces; the shared
   container is otherwise sufficient (`design/0012`).

---

## 7. Next actions (ordered)

0. **Paper (`design/0018`):** author checks every proof in `docs/theory.md`
   (second-reader notes in `docs/proof-review-1.md`; confirm `design/0021`);
   ~~citation check~~ done (`docs/adversarial-search-4.md`) — still read eVer's
   PDF, AGEMA's register handling and the extraction papers; author decides any
   novelty wording; then write the paper around the theorem in §3, with
   `findings/` as the artifact.

1. ~~Build a faster safety labeller~~ — **done** for chain scale (`design/0015`).
   A symbolic labeller is deferred until a benchmark exceeds `2**26`. Labelling
   `egglog` e-graphs still needs an export of their classes.
2. ~~Re-sharing representation~~ — **done** (`design/0016`). Follow-ups: make
   value-layer extraction scale (it is ~144 s at chain depth 5); find a
   benchmark where the *start* circuit is a published, tight construction and
   R1–R3 still help (Keccak chi: none — done); model **randomness reuse** as the
   next lever; run the citation check before any novelty claim about the
   representation.
3. **Expand fixtures** beyond ISW/DOM/chain: VerifMSI's benchmark gadget set and
   MaskedVerifBench, now that the labeller question is being addressed.
4. **Wire the cross-check into the default test run** where the oracle is
   present, and document the skip behaviour.
5. **Monitor** eVer (already optimizing refresh gadgets) and the re-sharing
   literature (RNI-f / COMAR line).
6. **Push to a private GitHub remote.** Create the empty repository, then
   `git remote add origin …` and push `main` (`design/0013`).
7. **Before any public flip:** purge `docs/teammates-made/` from history, add a
   `LICENSE`, and re-read the proposal for claims that only hold internally
   (`design/0013`).

---

## 8. Non-goals

- LLM/agent-guided equality saturation for general compiler IR (dead — see
  `docs/team-briefing-plan-a.md`)
- Constant-time-constrained EqSat on LLVM/MLIR (dead on novelty and feasibility)
- Higher-order security claims, SNI or glitch-robust composition claims
  (glitch-extended probing is in scope since `design/0018`; PINI composition,
  glitch-free only, since `design/0019`)
- Building a production masking compiler or a replacement for
  Tornado/AGEMA/COMPRESS
- New side-channel attacks or new leakage models

---

## 9. Reproduce

```bash
uv sync
uv run pytest -q                                    # 171 tests (18 skip without the oracle)
uv run python experiments/premise_test/run.py       # premise, in-house
bash experiments/oracle_crosscheck/setup_oracles.sh # one-off, outside the repo
uv run python experiments/oracle_crosscheck/crosscheck.py --random 20
uv run python experiments/constrained_extraction/run_constrained.py
uv run python experiments/egglog_port/port.py --circuit chain --rules full --iters 4
uv run python experiments/labeller/measure.py       # labelling cost, ~1.5 min
uv run python experiments/frontend/seqc.py experiments/frontend/examples/factor.sec --crosscheck
```

---

## 10. Change log

- **2026-10-06** — Original direction closed after two adversarial passes; Plan A
  adopted. `docs/adversarial-search-2.md`, `docs/probing-secure-eqsat-proposal.md`,
  `docs/team-briefing-plan-a.md`.
- **2026-10-06** — Premise test built and passing (`experiments/premise_test/`,
  `design/0001`, `0004`).
- **2026-10-06** — Toolchain moved to uv/ruff under the devcontainer
  (`pyproject.toml`, `design/0003`).
- **2026-10-06** — Governance added: `AGENTS.md`, this file, `design/`.
- **2026-10-06** — Git adopted; commits reattributed; devcontainer now provisions
  the venv (`design/0007`, `0008`).
- **2026-10-06** — **Feasibility push.** Trust boundary closed via VerifMSI
  cross-check (21,760 wires, 0 violations); premise confirmed on egglog;
  security-constrained extraction implemented; chain blowup shown to be an
  engine artifact; payoff shown to be unsupported at both scales;
  re-sharing gap identified. `docs/feasibility-report.md`, `design/0005`,
  `0006`, `0009`, `0010`, `experiments/*/RESULTS.md`.
- **2026-10-06** — **Third adversarial pass** on the reframed proposal. Soundness
  claim sharpened and disclaimed (MaskedHLS, FRAIG-CAD, SecCG); repair claim
  narrowed to a semantic-hyperproperty constraint and disclaimed against eVer;
  re-sharing claim **corrected** to a congruence obstruction (it is standard
  masking semantics, not a new notion). Measured: search scales (egglog, chain
  depth 5, <0.01 s), **labelling is the bottleneck** (6.7 s/check at 16
  randoms). `docs/adversarial-search-3.md`, `design/0011`, proposal v3.
- **2026-10-06** — **Push preparation.** Added `README.md` and `.gitattributes`;
  untracked the teammate PPTX and gitignored `docs/teammates-made/`
  (`design/0013`). Made the dev container **agent-neutral**: provisioning moved
  to `scripts/setup-tools.sh`, the per-user agent install is opt-in via
  `scripts/setup-opencode.sh` and `.devcontainer/personal/` (`design/0012`), and
  the README documents both. Fixed stale ADR status lines for `0005` (gate
  closed) and `0006` (prototype implemented).
- **2026-10-06** — **Agent-facing configuration.** Added a thin `CLAUDE.md` that
  imports `AGENTS.md` — without it, Claude Code stops reading `AGENTS.md` when any
  `CLAUDE.md`/`CLAUDE.local.md` is present, including a teammate's personal one.
  Added three skills under `.claude/skills/`, a location both Claude Code and
  opencode read: `secureeqsat-gate`, `secureeqsat-adr`,
  `secureeqsat-citation-check`. Documented the dev container CLI workflow
  (`up` / `exec` / `--config` / `--remove-existing-container`) in the README, and
  recorded in `design/0012` that `--config` and `--override-config` supply the
  local override a filename could not.
- **2026-10-06** — **First real rebuild exposed a provisioning bug, fixed, and
  the oracle became shared infrastructure.** Docker creates mount-point parents
  as root and mounts volumes root-owned, so `~/.local/share` was created
  root-owned and `uv sync` failed; `setup-tools.sh` now restores ownership from a
  `HOME_DIRS` list kept in sync with the devcontainer `mounts` (an initial fix
  missed `~/.config`). A fourth volume, `secureeqsat-oracles` → `~/oracles`, moved
  into the **shared** configuration, and `setup-tools.sh` now runs
  `setup_oracles.sh` **non-fatally**, so a network failure warns instead of
  breaking the container. Previously every rebuild silently turned the three
  VerifMSI cross-check tests from passes into skips — a trust-boundary hole for
  onboarding (`design/0012`, `0014`).
- **2026-10-07** — **Labelling bottleneck resolved at chain scale.** Added the
  bitsliced exact labeller (`experiments/labeller/`, `design/0015`):
  `constrained.class_safety` now uses it, the original is kept as
  `class_safety_reference`. Identical verdicts against the reference checker,
  the reference labeller and VerifMSI (new RULE 1b in the cross-check; 1,265
  circuits / 22,463 wires, 0 violations). Depth-5 chain labelled in ~0.4 s vs
  ~50 min (est.); saturation now dominates. Fixed `run_chain.py` passing all
  free variables as randoms.
- **2026-10-11** — **Shared-value layer for re-sharing.** Added
  `experiments/resharing/` and `design/0016`: an egglog layer whose classes
  identify sharings by value, with R1 (Boolean), R2 (ISW = DOM = HPC1) and R3
  (refresh) as ordinary rules, lowering to wire circuits, and term-based
  constrained extraction (cost = gates + randoms). Ablation over five fixtures:
  hand-written chain unchanged (18); over-refreshed chain 30 → 18 via R3;
  square: unconstrained drops a needed refresh (11, leaks), constrained keeps it
  (14); factoring 20 → 11, secure; HPC1 chain 24 → 18 (glitch-free model only).
  VerifMSI: 19 circuits / 458 wires, 0 violations. Extraction is the new limit.
- **2026-10-11** — **Tight starts.** Added Keccak chi (3- and 5-bit rows,
  FIPS 202) as tight fixtures, plus share-wise NOT and a gate-free output bundle
  in the layer. No rule class improves either start (36 and 60); VerifMSI now
  27 circuits / 914 wires, 0 violations. VerifMSI's own gadget set was not used:
  single gadgets are atoms at this layer (`experiments/resharing/RESULTS.md`).
- **2026-10-11** — Added `docs/getting-up-to-speed.md` (orientation for new
  readers) and linked it from the README; corrected the README's test counts
  (65 passed, 4 oracle skips).
- **2026-10-18** — **Glitch feasibility probe** (`design/0017`,
  `experiments/glitch_probe/`). New glitch-extended checker, cross-checked
  against VerifMSI's own leakage sets (167 probes, 0 disagreements;
  `checkSecurity` agrees on all 10 circuits). Opaque registers block Boolean
  rewriting; transparent registers make cost-optimal extraction drop them
  (registered DOM 10 → 5, chain 20 → 10, both leaking); the occurrence-aware
  extractor restores glitch security by placing registers, including on
  unregistered ISW and DOM. Verdict: go for the theory (register ≈ refresh),
  no gains.
- **2026-10-18** — **Scope adds the glitch-extended model** (`design/0018`,
  superseding `0002`'s glitch-free restriction; deliverable is now a workshop
  paper). Drafted `docs/theory.md` — claims C1–C8 for value-preserving,
  leakage-changing operators (refresh, register) — with one executable witness
  per claim in `experiments/claims/test_claims.py` (12 tests).
- **2026-10-18** — **Citation check of the theory** (`docs/adversarial-search-4.md`):
  PCR citation verified (ICDT 2025, §3.1); register-moving optimizations
  breaking masking is known (Fraunhofer/BSI 2024) and register placement is
  not claimable; T1–T3 survive at medium confidence. `docs/theory.md` now
  answers pass 3's decode-kernel objection. Added `findings/` — an index of
  findings F1–F10 and `verify.py`, which re-runs each and records a manifest.
- **2026-10-22** — **PINI composition analysis** (`design/0019`,
  `experiments/composition/`, `docs/adversarial-search-5.md`). Exhaustive 1-PINI
  checker per gadget (XOR, NOT, refresh, HPC1 pass; ISW, DOM fail; VerifMSI
  agrees on all 6); composable-class analysis and PINI-only DAG extraction;
  theory claim C9 with witnesses. Scales past the exact range: Keccak χ on a
  32-bit row (2^128 points) in ≤ 0.03 s, every wire certified by VerifMSI's
  symbolic check. Cost premium up to +33 %; glitch-free only.
- **2026-10-26** — **Language front end** (`design/0020`, `experiments/frontend/`). Added a
  hand-written parser for a small Boolean language, a masking pass with two policies
  (`refresh`, `naive`), the `seqc.py` driver (parse, mask, saturate, extract with and without
  the security constraint, verify, emit) and netlist/Verilog emitters. Examples: factor,
  square, mux, full adder, majority. All compiled circuits equal their source on every input and
  have 0 leaking wires; VerifMSI agrees on 6 runs (0 disagreements). On `square`, the headline
  result holds on a compiled program: cost 11 leaks, constrained 14 is secure. 54 new tests
  (about 1.6 s). No change to any claim; Verilog is glitch-free-model only.
- **2026-10-26** — **Verification re-run** on a clean checkout of `4607443`: 14 of 14
  steps pass with VerifMSI present; pytest counted 171 tests (117 + 54 front end); 173 after `test_c5b_*`.
  `uv sync` needs `--python 3.14` (no interpreter pin; egglog does not build on 3.15).
- **2026-10-26** — **Proof review #1** (`docs/proof-review-1.md`). C5(b) holds for R3
  alone and fails for R1 + R3 (16 secure DAG extractions of `square`, VerifMSI agrees);
  claim narrowed and test added (`design/0021`, `test_c5b_*`). Other gaps listed for the
  author, not patched.
- **2026-10-26** — **Stale PINI scope lines fixed** to "PINI composition in the
  glitch-free model only (C9)" in `findings/README.md`, `docs/theory.md` §4, this
  file §6 risk 4 and §8, and `docs/getting-up-to-speed.md` §4 and §9.
- **2026-10-26** — **README rewritten** findings-first: nine findings with their numbers,
  then the working method, the experiments in order, and how to reproduce (`README.md`).
- **2026-10-27** — Documented nine files with purpose, per-function docstrings,
  step-by-step algorithm notes and inline comments on variables (purpose plus an example
  value), bitwise operations and non-obvious lines (`premise_test/{masked,egraph,run}.py`,
  `egglog_port/{port,kbest}.py`, `constrained_extraction/{constrained,run_constrained,run_chain}.py`,
  `oracle_crosscheck/crosscheck.py`). Comments and docstrings only: the syntax trees match
  the originals, ruff is clean, 171 tests pass.
- **2026-10-27** — Extended the same documentation (purpose section, docstrings, step-by-step
  algorithm notes, inline comments on variables and bitwise operations) to every other
  Python file under `experiments/` and `findings/verify.py`, and added explanatory comments
  to the three shell scripts and `pyproject.toml`. Comments and docstrings only: each file's
  syntax tree matches HEAD, ruff is clean, 171 tests pass.
