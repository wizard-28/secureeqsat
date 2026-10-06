# Project Context — SecureEqSat

**Last updated:** 2026-10-06 (push preparation)
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
- **Team:** _to be filled in (names + track ownership, see proposal §19)_
- **Primary venue target:** EGRAPHS workshop (PLDI) fits the EqSat framing; a
  security/HW venue fits the masking framing. Decide after Review 1.

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
| ⚠️ measured | **Labelling is the scalability bottleneck**: checker doubles per random (6.7 s at 16), called once per e-class; `egglog` saturation scales fine |
| ⏳ next | **Symbolic/lazy safety labeller** — the top implementation task before larger circuits |
| ⏳ next | **Re-sharing formulation** — refresh as a congruence-aware representation; the only identified route to genuine gains |
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
| `0002` | Scope: first order, 2 shares, straight-line, glitch-free | accepted |
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
| `experiments/premise_test/` | `egraph.py`, `masked.py`, `run.py`, `test_premise.py`, `RESULTS.md` |
| `experiments/oracle_crosscheck/` | VerifMSI driver, cross-check protocol, tests, `RESULTS.md` |
| `experiments/constrained_extraction/` | `constrained.py`, `run_constrained.py`, `run_chain.py` |
| `experiments/egglog_port/` | `port.py`, `kbest.py`, `RESULTS.md` |
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
2. **Abstraction level (MEDIUM).** The valuable optimizations may not be
   expressible as e-graph equalities at all. This is now the central research
   question rather than an unexamined assumption.
3. **Novelty window (MEDIUM → partially realised).** superVer (EGRAPHS 2024)
   verifies probing security with e-graphs; **eVer (2026) now optimizes refresh
   sequences and gadgets** with re-verification. Reposition onto the soundness +
   congruence framing, which they have not claimed (`design/0011`).
4. **Scope (MEDIUM).** First order, 2 shares, glitch-free only. No claim about
   robust probing, glitches, PINI or higher orders.
5. **Labelling bottleneck (HIGH, measured).** The exhaustive checker doubles per
   fresh random (6.7 s at 16) and is called once per e-class; `egglog`
   saturation scales fine. Mitigation: symbolic/lazy labeller — VerifMSI as an
   external labelling oracle, ANF/BDD check, structural pre-filters, on-demand
   frontier labelling.
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

1. **Build a symbolic/lazy safety labeller** — the measured bottleneck. Options:
   VerifMSI as an external labelling oracle, an ANF/BDD-based exact check,
   conservative structural pre-filters (non-completeness/uniformity), and/or
   labelling only the extraction frontier on demand.
2. **Re-sharing representation** (highest leverage): what representation can
   carry re-sharing while keeping extraction security-aware, given that
   re-sharing is not a congruence (`design/0011`)?
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
- Higher-order / glitch-extended / PINI security claims
- Building a production masking compiler or a replacement for
  Tornado/AGEMA/COMPRESS
- New side-channel attacks or new leakage models

---

## 9. Reproduce

```bash
uv sync
uv run pytest -q                                    # 10 tests (3 skip without the oracle)
uv run python experiments/premise_test/run.py       # premise, in-house
bash experiments/oracle_crosscheck/setup_oracles.sh # one-off, outside the repo
uv run python experiments/oracle_crosscheck/crosscheck.py --random 20
uv run python experiments/constrained_extraction/run_constrained.py
uv run python experiments/egglog_port/port.py --circuit chain --rules full --iters 4
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
