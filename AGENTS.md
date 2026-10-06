# AGENTS.md — SecureEqSat working norms

**Read [`project_context.md`](project_context.md) first.** It is the current state of the
world. Design decisions live in [`design/`](design/). The historical record lives in
[`docs/original/`](docs/original/) — **do not edit it**; it is what the pivot was argued
against.

---

## 1. What this repo is

A compiler-design research project: **probing-secure equality saturation (SecureEqSat)** —
using e-graphs to optimize masked cryptographic circuits under a first-order
probing-security constraint.

Status at last update: Plan A selected, central premise validated experimentally, external
security-oracle cross-check **not yet done**. See `project_context.md` for the live
snapshot.

---

## 2. Commands

```bash
uv sync                                          # create/refresh .venv (CPython 3.14)
uv run pytest -q                                 # regression tests
uv run ruff check .                              # lint
uv run ruff format --check .                     # format check (use format without --check to fix)
uv run python experiments/premise_test/run.py    # narrative premise test
```

`uv run <cmd>` is the only sanctioned way to execute Python. Do not call `.venv/bin/python`
directly and do not rely on a system interpreter.

---

## 3. Environment rules (non-negotiable)

- **There is no system Python.** `uv` provisions interpreters and manages `.venv`.
- **Never install tools with `apt`, `pip`, or `curl | sh`.** If something is missing, edit
  `.devcontainer/devcontainer.json` and ask the human to rebuild. This is the single most
  explicitly-stated instruction on this project.
- `ruff` and `pyright` are installed as `uv tool`s by `postCreateCommand`; they are invoked
  as bare commands, not via `uv run`.
- **`postCreateCommand` provisions `.venv` via `uv sync`** (`design/0008`). If a rebuild
  leaves `.venv/` missing or stale, run `uv sync` manually.
- Keep the Python toolchain in `pyproject.toml` under `[dependency-groups].dev`. Adding any
  **runtime** dependency requires an ADR first (`design/`), because the premise test is
  deliberately stdlib-only.

---

## 4. Repo map

| Path | What it is | Edit? |
|---|---|---|
| `project_context.md` | Live project state and change log | **Yes, on every meaningful change** |
| `design/` | ADRs: one file per non-trivial decision | **Yes, append-only** |
| `docs/original/` | Original research overview + first adversarial search | **No — historical record** |
| `docs/adversarial-search-2.md` | Second adversarial pass; auditable search record | Yes (append a new pass, don't rewrite) |
| `docs/probing-secure-eqsat-proposal.md` | Full Plan A proposal (review-1 deliverable) | Yes, keep release-quality |
| `docs/team-briefing-plan-a.md` | Why the original direction is dead + Plan A (sent to team) | Yes, if the argument changes, tell the team |
| `experiments/premise_test/` | The premise falsification harness + tests + `RESULTS.md` | Yes |
| `pyproject.toml`, `uv.lock` | Toolchain and pinned deps | Yes |

---

## 5. Research protocol

This project already made expensive mistakes in each of these areas. The rules exist
because of specific incidents — noted in brackets.

1. **Never cite what you have not fetched.** Before a citation enters any document, fetch
   the primary source (arXiv abstract page, venue listing, DOI, repo). If you cannot fetch
   it, mark it `UNVERIFIED` in the text. No exceptions. [Fabricated-looking arXiv IDs in
   the first search turned out to be real; the risk runs both directions.]
2. **Verify recommendations, not only citations.** The first adversarial search's citations
   all checked out, but both of its *recommended survivors* were already occupied. Check
   the conclusion, not just the footnote. [Omelette, 2022.]
3. **Read the full paper for any load-bearing claim.** Abstracts hide the details that
   decide novelty. [CryptOpt's abstract never mentions that its verified equivalence
   checker uses an e-graph; the full text does.]
4. **Record negative results auditably.** When you conclude "nobody has done X", write down
   the exact queries you ran, in the document itself. A negative result without a query log
   is an opinion.
5. **State confidence, never certainty.** Novelty is a negative claim and cannot be proven.
   Use calibrated labels (`high` / `medium-high` / `speculative`) and name the residual
   risk. Anyone writing "100% confident about novelty" is wrong and should be corrected.
6. **Always state what we do *not* claim.** Every novelty section needs an explicit
   disclaimer list. [Plan A must always disclaim superVer's e-graph × probing-security
   verification, and the masked-optimizer lineage.]
7. **Adversarial before constructive.** Before building anything, spend the effort trying to
   kill the idea: find the collision, the ill-posedness, the representation mismatch.
   Building first is how the original direction consumed weeks.
8. **Tag evidence status.** In research documents, separate *verified by direct fetch*,
   *secondary / inferred*, and *unverified*. [Appendix A pattern in the team briefing.]

---

## 6. Engineering protocol

1. **Tests are the artifact of record.** A claim that is not a test is a hope. Every
   experiment ends with assertions that would fail if the finding were wrong.
2. **Every experiment directory has a `RESULTS.md`** containing: the question, the
   method, the results table, what it does and does not prove, known limitations, and the
   raw output. [`experiments/premise_test/RESULTS.md`](experiments/premise_test/RESULTS.md)
   is the template.
3. **The security trust boundary is mandatory.** No security claim may be made on the
   in-house checker alone. Cross-validation against an independent oracle (VerifMSI or
   tightPROVE) is a **stopping condition**: if they disagree on any fixture, stop and fix
   before building further. This gate is currently **open**.
4. **GPL oracles are invoked as external processes only.** VerifMSI and tightPROVE are
   GPLv3; do not link or vendor them into our code.
5. **Reproduce before extending.** Run `uv run pytest -q` and the premise test before
   changing anything. If they do not pass, that is the task.
6. **Ruff clean and formatted is the bar.** `uv run ruff check .` and
   `uv run ruff format --check .` must pass. Do not suppress rules to avoid fixing code;
   narrow the rule set only via an ADR.
7. **The minimal e-graph is a test harness, not the product.** Do not add features to
   `experiments/premise_test/egraph.py` beyond what the falsification needs. The real engine
   is `egglog`/`egg` (see `design/0004`).
8. **Pin versions.** `uv.lock` is committed; do not hand-edit it.
9. **Never optimize before the premise is safe.** The premise test is cheap and fast; keep
   it that way.

---

## 7. Documentation protocol

1. **`project_context.md` is updated on every meaningful change** — status, decisions,
   risks, next actions, and a change-log line. If you did something and the context file
   does not mention it, the work is not done.
2. **A `design/NNNN-*.md` ADR is required for:** a scope change, a toolchain or dependency
   change, a change to the security model or trust boundary, an architecture decision, or
   superseding a previous decision. Use the template in `design/README.md`.
3. **ADRs are append-only.** To reverse a decision, write a new ADR that supersedes the old
   one and update the old one's status line. Never rewrite history.
4. **`docs/` documents are human deliverables** (proposal, briefings, adversarial searches).
   Keep them release-quality: verified citations, calibrated confidence, disclaimers.
5. **Change-log entries are dated and terse.** One line, past tense, with the file or ADR
   reference.

---

## 8. Git workflow

- **Trunk is `main`; commit directly to it.** No branch/PR ceremony at this size (see
  `design/0007`).
- **Set your git identity before committing** — it is per-clone and deliberately not in the
  committed devcontainer: `git config user.name "..." && git config user.email "..."`.
- **Small, logical commits**, Conventional-Commit prefixes: `feat:`, `fix:`, `docs:`,
  `chore:`, `refactor:`, `test:`.
- **Never commit** environments, caches, editor artifacts, or harness exports. `.gitignore`
  owns that list; reaching for `git add -f` means you should be writing an ADR instead.
- **`uv.lock` is committed** — it is the reproducibility contract.
- **A change lands with its bookkeeping**: tests, `RESULTS.md` update, ADR (if a decision
  was made), and the `project_context.md` change-log line, all in the same commit. "I'll
  document it later" shows up as a missing change-log line.
- **Commit messages say why.** The diff already says what.
- **Never rewrite published history.** ADRs are append-only for the same reason.

---

## 9. Anti-patterns (hard-won — do not repeat)

| Anti-pattern | Why it burned us |
|---|---|
| Rebuilding an e-graph prototype for general compiler IR "to see if it works" | The single most expensive way to rediscover that the original direction is dead |
| Claiming "first to use e-graphs for probing security" | **superVer** (EGRAPHS 2024) did verification; we may only claim the *optimization* problem |
| Treating functional equivalence as security | `xor(a0,a1)` is a valid Boolean simplification and is the unmasked secret |
| Comparing value *sequences* instead of *distributions* in the checker | A uniform wire permutes across assignments; the first checker version flagged secure circuits as broken |
| Trusting a fixture written from memory | The first "ISW" fixture was insecure because `r` was folded in too late; the checker caught it |
| Assuming a property is expressible in the chosen representation | Constant-time is about control flow and memory; straight-line terms have neither, so the constraint was vacuous |
| Quoting an abstract as if you read the paper | CryptOpt's e-graph detail is only in the full text |
| Promoting an idea because it is in *our* lane | Lane-fit is a tiebreaker, not evidence; every direction still needs falsification |

---

## 10. Definition of done

**For code changes:**
- [ ] `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] `uv run pytest -q` passes, with new assertions for new claims
- [ ] `RESULTS.md` updated (if the change affects an experiment)
- [ ] ADR added (if a decision was made)
- [ ] `project_context.md` updated with status + change-log line

**For research documents:**
- [ ] every citation fetched and verified, or explicitly marked unverified
- [ ] confidence calibrated; residual risk named
- [ ] "what we do not claim" section present
- [ ] negative results carry their search queries

---

## 11. Stop and ask the human when

- changing `.devcontainer/devcontainer.json` (requires a rebuild)
- adding a runtime dependency
- making or changing a security claim
- making a novelty claim, or citing anything as prior art
- changing project scope or the security model
- the external-oracle cross-check disagrees with the in-house checker
