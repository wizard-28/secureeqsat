---
name: secureeqsat-gate
description: Run the SecureEqSat definition-of-done gate and its bookkeeping checklist before committing or reporting a change. Use when finishing any code or documentation change, before a git commit, or when asked whether the repo is clean.
---

# SecureEqSat gate

Implements `AGENTS.md` §10 (definition of done). Run everything from the repo
root.

`uv run <cmd>` is the **only** sanctioned way to execute Python. Never call
`.venv/bin/python` directly and never use a system interpreter — there is none.

## 1. Automated gate

```bash
uv run ruff check .            # must pass
uv run ruff format --check .   # must pass; drop --check to fix
uv run pytest -q               # must pass
```

Narrative premise test — slower, run it when the premise, checker or engine
changed:

```bash
uv run python experiments/premise_test/run.py
```

**Skipped is not passing.** The oracle cross-check tests skip when VerifMSI is
absent. Report that explicitly rather than describing the suite as fully green.

Do not suppress a lint rule to make the gate pass; narrowing the rule set
requires an ADR.

## 2. Bookkeeping — the part that gets forgotten

- [ ] Experiment changed → update its `experiments/*/RESULTS.md`: question,
      method, results table, **what it does and does not prove**, known
      limitations, raw output.
- [ ] A decision was made (scope, toolchain or dependency, security model or
      trust boundary, architecture, or superseding a decision) → write an ADR;
      use the `secureeqsat-adr` skill.
- [ ] `project_context.md` updated where relevant — status, risks, next actions —
      and **always** a dated change-log line.
- [ ] Commit prefix is one of `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`,
      `test:`, and the message says **why** (the diff already says what).

Everything above belongs in the **same commit** as the change it describes. "I'll
document it later" shows up as a missing change-log line.

## 3. Report

State plainly what passed, what was skipped, and why. Never describe a skipped
test as a pass, and never state a security property that the external-oracle
cross-check has not covered (`AGENTS.md` §6.3).
