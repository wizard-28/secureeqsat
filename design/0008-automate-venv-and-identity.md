# 0008 — Automate project venv creation and keep git identity local

- **Status:** accepted
- **Date:** 2026-10-06
- **Deciders:** Sourajyoti Basak

## Context

Two gaps surfaced once the toolchain was in place:

1. **Rebuilds were not turnkey.** `postCreateCommand` installed `uv`, `ruff` and `pyright`,
   but did not create the project venv. Every rebuild needed a manual `uv sync` before tests
   would run (recorded as a known gap in `design/0003` and `AGENTS.md` §3).
2. **Commits were misattributed.** The initial seven commits carried a placeholder identity
   (`SecureEqSat Team <team@secureeqsat.local>`) because no git identity existed in the
   container. The correct identity is now known, and none of the commits have been pushed.

A design question follows from (2): should the git identity live in the committed
devcontainer so rebuilds configure it automatically, or stay outside the repository?

## Decision

1. **Append `uv sync` to `postCreateCommand`** so a rebuilt container provisions `.venv`
   automatically.
2. **Keep git identity in the local repository config**, not in the committed devcontainer.
   Personal identity does not belong in a shared, committed file; `.git/config` lives inside
   the workspace repo, so it survives rebuilds anyway.
3. **Rewrite the author on the seven unpublished commits** to the correct identity. Safe
   because nothing has been pushed; the rule in `design/0007` (never rewrite *published*
   history) is unaffected.

## Consequences

- Rebuilds are self-provisioning: `uv sync` runs during `postCreate`, `.venv` exists, and
  `uv run pytest` works immediately.
- On a fresh clone elsewhere, a contributor must set their identity themselves; the failure
  mode is git's "Author identity unknown" on first commit. Documented in `AGENTS.md` §8.
- If `uv sync` fails during a rebuild (e.g. transient network failure), the container still
  comes up and a manual `uv sync` fixes it — the postCreate failure is visible in the build
  log rather than silent.
- Adding work to `postCreateCommand` increases rebuild time slightly (interpreter fetch plus
  dependency install).

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Set git identity inside `postCreateCommand` | Bakes a personal email into a committed file; wrong for fresh clones and for any other contributor |
| Keep the manual `uv sync` step | The gap was real and the fix was explicitly requested; rebuilds should be turnkey |
| Mount a host dotfile for gitconfig | More moving parts than needed; repo-local config is sufficient and already survives rebuilds |
| Leave the placeholder authorship | Misattributes the work and poisons `git blame` on the scientific record |

## Evidence

- `.devcontainer/devcontainer.json` — `uv sync` appended to `postCreateCommand`.
- `git log --format='%an <%ae>'` — all commits now attributed.
- `design/0003` (the gap this resolves), `AGENTS.md` §3 and §8.
