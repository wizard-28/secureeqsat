# 0003 — Toolchain: uv, ruff, pytest, devcontainer-managed

- **Status:** accepted
- **Date:** 2026-10-06
- **Deciders:** project team

## Context

The container has no system Python. Early in the project, Python was installed manually
with `apt` to unblock the premise test, which was against the project's stated environment
rule. The human then rebuilt the environment so that `postCreateCommand` installs `uv` and
provisions `ruff` and `pyright` as `uv` tools (`uv tool install --python 3.14`), with no
features block and no system interpreter.

The project needs: reproducibility (a rebuilt container must produce the same results),
linting and formatting (the premise test caught real bugs and must stay readable), and a
test runner that is the artifact of record.

## Decision

- The project is a **uv-managed Python project**: `pyproject.toml` + `uv.lock` + `.venv`,
  CPython 3.14.
- **ruff** is the linter and formatter, **pytest** the test runner; both live in
  `[dependency-groups].dev`. The enabled ruff rule set is `E, F, I, UP, B, SIM`.
- `uv run <cmd>` is the only sanctioned way to execute Python. Never call `.venv/bin/python`
  directly, never rely on a system interpreter.
- **No manual installs.** Environment changes go through
  `.devcontainer/devcontainer.json` and require a human rebuild.
- The premise test stays **stdlib-only**. Adding any runtime dependency requires an ADR.

## Consequences

- After a devcontainer rebuild, one `uv sync` is required, because `postCreateCommand` does
  not create the project venv. (Known gap; may be automated later.) — **resolved by
  [0008](0008-automate-venv-and-identity.md).**
- Lint/format cleanliness is a hard gate for every change (`AGENTS.md` §10).
- Narrowing the ruff rule set to dodge a fix is not allowed without an ADR.
- Adding tooling is a conversation with the human, not a shell command.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| System Python + pip | Not reproducible; directly against the project's environment rule; the manual install already caused a rebuild |
| A devcontainer feature for Python (tried first) | Superseded by the human's uv-based approach; uv is now authoritative and also manages the interpreter |
| No linter | Regressions in the checker are exactly the class of bug linting and tests catch |
| uv with no lockfile | Reproducibility gate |

## Evidence

- `pyproject.toml`, `uv.lock`, `.devcontainer/devcontainer.json`.
- `AGENTS.md` §3 (environment rules), §6.6 (ruff bar).
- Interpreter provisioned by `uv sync`: CPython 3.14.8.
