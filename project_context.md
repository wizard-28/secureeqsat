# Project Context — SecureEqSat

**Last updated:** 2026-10-06 (after the feasibility push)
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
| ⚠️ medium | Abstraction-level explanation: the useful optimizations are not Boolean equalities (`docs/feasibility-report.md` §6) |
| ⏳ next | **Re-sharing formulation** — refresh as a first-class rewrite with randomness side conditions; the only identified route to genuine gains |
| ⏳ next | Revise the Review-1 title/novelty claim per `design/0010` |
| ⏳ watch | superVer / eVer (verification group) — if they add optimization, reposition |

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

---

## 5. Artifact map

| Path | Contents |
|---|---|
| `docs/original/` | Original research overview + first adversarial search — **historical, do not edit** |
| `docs/adversarial-search-2.md` | Second adversarial pass + auditable search record |
| `docs/probing-secure-eqsat-proposal.md` | Plan A proposal (carries a revision note after the feasibility push) |
| `docs/team-briefing-plan-a.md` | Team-facing argument for why the original direction is dead |
| `docs/feasibility-report.md` | **Consolidated feasibility checks and confidence levels** |
| `experiments/premise_test/` | `egraph.py`, `masked.py`, `run.py`, `test_premise.py`, `RESULTS.md` |
| `experiments/oracle_crosscheck/` | VerifMSI driver, cross-check protocol, tests, `RESULTS.md` |
| `experiments/constrained_extraction/` | `constrained.py`, `run_constrained.py`, `run_chain.py` |
| `experiments/egglog_port/` | `port.py`, `kbest.py`, `RESULTS.md` |
| `design/` | ADRs |
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
3. **Novelty window (MEDIUM).** superVer (EGRAPHS 2024) verifies probing
   security with e-graphs; if that group adds optimization, reposition onto the
   soundness/re-sharing framing, which they have not claimed.
4. **Scope (MEDIUM).** First order, 2 shares, glitch-free only. No claim about
   robust probing, glitches, PINI or higher orders.
5. **Oracle dependency (LOW).** The cross-check requires an external GPL tool;
   the tests skip when it is absent, so CI without the oracle silently loses
   coverage.
6. **Licensing (LOW).** VerifMSI/tightPROVE are GPLv3 — external processes only.

---

## 7. Next actions (ordered)

1. **Revise the Review-1 material** to the `design/0010` framing: title,
   novelty claim, and the three supported claims.
2. **Re-sharing formulation** (highest leverage): model refresh/randomness
   reuse as first-class rewrites with randomness side conditions, and test
   whether they produce a secure improvement where Boolean refactoring cannot.
3. **Expand fixtures** beyond ISW/DOM/chain: use VerifMSI's benchmark gadget set
   and MaskedVerifBench for the checker and the extraction.
4. **Wire the cross-check into the default test run** where the oracle is
   present, and document the skip behaviour.
5. **Monitor** superVer / eVer.

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
