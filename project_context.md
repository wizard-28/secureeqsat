# Project Context — SecureEqSat

**Last updated:** 2026-10-06
**Maintainer:** update this file on every meaningful change (see `AGENTS.md` §7).

---

## 1. Identity

- **Project:** Probing-Secure Equality Saturation — *SecureEqSat*
- **One-liner:** use equality saturation to optimize masked cryptographic circuits under a
  first-order probing-security constraint, and study the security-constrained-extraction
  problem this creates.
- **Context:** compiler-design research project.
- **Review 1 deliverable:** project title + novelty claim + plan. The 30% implementation is
  a later milestone (its foundations are already built — see §3).
- **Team:** _to be filled in (names + track ownership, see proposal §19)_
- **Primary venue target (when ready):** EGRAPHS workshop (PLDI) or a security/HW venue
  depending on results.

---

## 2. Summary

Masking splits a secret into random-looking shares and requires every intermediate wire to
be statistically independent of the secret. Existing tooling either *generates* masked
circuits from fixed gadget libraries (Tornado, AGEMA, COMPRESS, POMMES/CoMEMS) or
*verifies* them (maskVerif, tightPROVE, SILVER, PROLEAD). Equality saturation — the
non-destructive, order-independent rewrite search from compiler design — has not been used
to *optimize* under this constraint. Our project builds that, and its technical core is
**security-constrained extraction**: choosing a cost-minimal circuit from an e-graph when
admissibility is a probabilistic-independence property (a per-e-class label at first order,
a set-valued hyperproperty at higher orders).

---

## 3. Status

| State | Item |
|---|---|
| ✅ done | Original direction investigated and closed (`docs/original/`, `docs/team-briefing-plan-a.md`) |
| ✅ done | Plan A selected; novelty boundary established |
| ✅ done | Full proposal written: `docs/probing-secure-eqsat-proposal.md` |
| ✅ done | Team briefing written and shared with the team |
| ✅ done | **Premise validated experimentally** — `experiments/premise_test/`, 7 passing tests |
| ✅ done | Toolchain: uv-managed venv, ruff-clean, pytest, devcontainer-managed |
| ⏳ **next gate** | **External security-oracle cross-check (VerifMSI / tightPROVE). Mandatory trust boundary.** |
| ⏳ planned | Port premise test to `egglog-python`; re-confirm under a real engine |
| ⏳ planned | Expand fixtures to the MaskedVerifBench gadget set |
| ⏳ planned | Implement first-order security-constrained extraction; measure cost delta |
| ⏳ watch | superVer / eVer (Verification group) — if they add optimization, reposition |

**Premise-test headline result:** unconstrained Boolean equality saturation +
cost-minimal extraction turns a secure ISW masked AND into a *functionally equivalent but
probing-insecure* circuit, and the insecure circuit is **cheaper** (7 vs 8 gates), so the
failure is systematic. The enabling rule is distributivity/factoring
(`(x&y)^(x&z) → x&(y^z)`).

---

## 4. Decision log

Full records in [`design/`](design/README.md).

| ADR | Decision | Status |
|---|---|---|
| `0001` | Pivot from LLM/agent-guided EqSat to probing-secure EqSat (Plan A) | accepted |
| `0002` | Scope: first order, 2 shares, straight-line, glitch-free | accepted |
| `0003` | Toolchain: uv + ruff + pytest, devcontainer-managed, no manual installs | accepted |
| `0004` | Minimal in-repo e-graph for the premise test; `egglog`/`egg` for the real engine | accepted |
| `0005` | In-house checker + mandatory external-oracle cross-check as the trust boundary | accepted, **gate open** |
| `0006` | Security-constrained extraction: per-class admissibility (first order) + lazy separation oracle (`t ≥ 2`) | accepted, unimplemented |
| `0007` | Adopt git: trunk-based, logical commits, `.gitignore` authoritative | accepted |

---

## 5. Artifact map

| Path | Contents |
|---|---|
| `docs/original/` | Original research overview (PDF) + first adversarial search — **historical, do not edit** |
| `docs/adversarial-search-2.md` | Second adversarial pass (CT/EqSat survivor attacked) + auditable search record |
| `docs/probing-secure-eqsat-proposal.md` | Full Plan A proposal: novelty, prior-art matrix, architecture, plan, risks |
| `docs/team-briefing-plan-a.md` | Team-facing argument for why the original direction is dead and why Plan A |
| `experiments/premise_test/` | `egraph.py`, `masked.py`, `run.py`, `test_premise.py`, `RESULTS.md` |
| `design/` | ADRs |
| `pyproject.toml`, `uv.lock`, `.venv/` | uv project |

---

## 6. Open risks and unknowns

1. **Trust boundary open.** The in-house first-order checker is validated against internal
   fixtures only. An independent oracle may disagree. *If it does, that is a stopping
   condition, not a detail.*
2. **Novelty window.** superVer (EGRAPHS 2024) already uses e-graphs for probing-security
   *verification*; their group is active. If they add optimization, our claim must be
   repositioned. Assessed novelty ~6/10.
3. **Null result.** The security constraint may leave little optimization freedom, i.e.
   constrained search may find nothing cheaper than fixed gadget constructions. This is
   reportable but is not the story we want; the evaluation plan must surface it early.
4. **Scale.** XOR associativity/commutativity is a known e-graph blowup source; DAG-aware
   extraction is NP-hard. Needs scheduling and limits.
5. **Checker scope.** First order, glitch-free, 2 shares. No robust-probing or PINI claims
   may be made from this code.
6. **Licensing.** VerifMSI and tightPROVE are GPLv3 — external processes only.

---

## 7. Next actions (ordered)

1. **Close the trust boundary.** Cross-validate the checker against VerifMSI (Python-first)
   then tightPROVE on all fixtures. Add the comparison as a test. Zero disagreements
   required.
2. **Port to `egglog-python`** and re-run the same assertions, to confirm the premise under
   a real e-graph engine rather than our minimal one.
3. **Expand fixtures** to the MaskedVerifBench gadget set (DOM, refresh, NI/SNI multipliers,
   masked S-box variants).
4. **Implement first-order security-constrained extraction** (ADR 0006) and measure the
   cost delta versus fixed gadget constructions and unconstrained extraction.
5. **Prepare Review 1** from `docs/probing-secure-eqsat-proposal.md` (title, novelty claim,
   plan) — already in review-ready shape.
6. **Monitor** superVer / eVer.

---

## 8. Non-goals

- LLM/agent-guided equality saturation for general compiler IR (the original direction —
  dead, see `docs/team-briefing-plan-a.md`)
- Constant-time-constrained EqSat on LLVM/MLIR (dead on novelty and feasibility)
- Higher-order / glitch-extended / PINI security claims
- Building a production masking compiler, or a replacement for Tornado/AGEMA/COMPRESS
- New side-channel attacks or new leakage models

---

## 9. Reproduce

```bash
uv sync
uv run pytest -q                                # 7 regression tests
uv run python experiments/premise_test/run.py   # full narrative run
```

---

## 10. Change log

- **2026-10-06** — Original direction closed after two adversarial passes; Plan A
  (probing-secure equality saturation) adopted. `docs/adversarial-search-2.md`,
  `docs/probing-secure-eqsat-proposal.md`, `docs/team-briefing-plan-a.md`.
- **2026-10-06** — Premise test built and passing; assumption validated
  (`experiments/premise_test/`, `design/0001`, `0004`).
- **2026-10-06** — Toolchain moved to uv/ruff under the devcontainer
  (`pyproject.toml`, `design/0003`).
- **2026-10-06** — Project governance added: `AGENTS.md`, this file, `design/`.
- **2026-10-06** — Adopted git; repository initialised with logical historical commits
  (`.gitignore`, `design/0007`, `AGENTS.md` §8).
