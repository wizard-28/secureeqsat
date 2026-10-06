# 0007 — Adopt git with trunk-based, logical-commit history

- **Status:** accepted
- **Date:** 2026-10-06
- **Deciders:** project team

## Context

Until now the repository was unversioned: the original research materials, two adversarial
passes, the Plan A proposal, the team briefing, the premise test, and the governance docs
existed only as loose files. Three forces make version control necessary rather than nice
to have:

1. `docs/original/` is a **frozen historical record** — the material the pivot was argued
   against. Git makes "this was not edited afterwards" auditable instead of a promise.
2. The checker and premise test are the project's **scientific record**. Two real bugs were
   found and fixed during their development (distribution-vs-sequence; ISW XOR ordering).
   We need to be able to attribute changes and see what the code looked like when a result
   was produced.
3. Multiple teammates will work concurrently, and the review-1 deliverable needs a stable
   baseline.

At the same time, the working tree contains `.venv/`, tool caches, and a 4.8 MB harness
export (`opencode-share.zip`). None of these belong in history.

## Decision

- Initialise a git repository on **`main`**, **trunk-based** (no branches or PR ceremony at
  this size; revisit via ADR if we add contributors or CI gates).
- **Small, logical commits** with Conventional-Commit prefixes: `feat:`, `fix:`, `docs:`,
  `chore:`, `refactor:`, `test:`.
- **`.gitignore` is authoritative** for excluded paths (environments, caches, harness
  exports, editor artifacts, local secrets). Reaching for `git add -f` requires an ADR.
- **`uv.lock` is committed** — it is the reproducibility contract.
- **A change lands with its bookkeeping**: tests, `RESULTS.md` update, ADR if a decision was
  made, and the `project_context.md` change-log line, all in the same commit.
- **Commit messages state why**, not just what — the diff already says what.
- **Never rewrite published history.** ADRs are append-only for the same reason.
- The existing work is imported as **logical historical batches** (original materials →
  adversarial pass 2 → proposal and briefing → toolchain → premise test → governance)
  rather than one monolithic initial commit.

## Consequences

- The pivot is auditable: `git log` shows the original materials entering before the
  adversarial passes that killed them, and before Plan A.
- Teammates get a real baseline to branch from when they take their tracks.
- Discipline required: the context-file update rides in the same commit as the change, so
  "I'll document it later" becomes visible as a missing change-log line.
- Commit authorship is currently a project placeholder and should be corrected by each
  teammate before they push.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| No version control | The historical-record and scientific-record arguments above; not defensible for a multi-person project |
| Branches + pull requests per change | Overhead not justified at this size; revisit when there is CI or an external reviewer |
| One giant initial commit | Destroys the audit trail that is the main reason for adopting git now |
| Git LFS for the PDFs | PDFs are small (tens of KB); unnecessary complexity |

## Evidence

- `.gitignore`, `AGENTS.md` §8 (git workflow).
- `git log` — initial import sequence.
