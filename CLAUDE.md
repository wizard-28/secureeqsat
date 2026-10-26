# Claude Code

@AGENTS.md

That import is the entire point of this file: [`AGENTS.md`](AGENTS.md) is the
single source of truth for this project's working norms, and nearly every agent
reads it natively.

This pointer exists because Claude Code **stops reading `AGENTS.md`** as soon as
any `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` is present — including a
teammate's *personal* `CLAUDE.local.md`. Without this file, one teammate adding a
local preferences file would silently lose the whole research, engineering and git
protocol, with no error.

## Claude-specific notes

- Project skills live in [`.claude/skills/`](.claude/skills/). opencode reads that
  directory too, so the procedures are shared rather than duplicated per tool:
  - `secureeqsat-gate` — definition-of-done checks and bookkeeping
  - `secureeqsat-adr` — writing an ADR in `design/`
  - `secureeqsat-citation-check` — prior-art and novelty verification
- `CLAUDE.local.md` is gitignored. Use it for personal preferences; never commit it.
- Keep skills to the portable frontmatter fields (`name`, `description`).
  Claude-only keys are silently ignored elsewhere, and rejected by the Skills API.
- **If this file and `AGENTS.md` ever disagree, `AGENTS.md` wins.** Fix the
  disagreement rather than encoding it here.

## Working practices

From the [Claude Code best practices](https://code.claude.com/docs/en/best-practices).
They add to `AGENTS.md`; none of them relaxes it.

- **Verify, and show the evidence.** Run a check that returns pass/fail
  (`uv run pytest -q`, `ruff`, `findings/verify.py`) and quote its output. Never
  report success on "looks done". A skipped oracle test is not a pass.
- **Explore, plan, then change.** Read first. For anything touching several files
  or an unfamiliar area, give a short plan before editing. If the diff fits in one
  sentence, just do it.
- **Subagents keep research out of the main context.** Use one for broad reads or
  for an independent second look, not for small tasks.
  - `haiku`: mechanical sweeps (e.g. checking every number in a document against
    the `RESULTS.md` files).
  - `sonnet`: the default for reading and summarising code or docs.
  - `opus`: hard reasoning, e.g. refuting a proof in `docs/theory.md`.
  - A reviewer is told to flag only gaps that affect correctness or the stated
    requirements, so findings do not turn into over-engineering.
- **Manage context.** Read the section you need, not whole directories; put
  scratch output in the scratchpad. `/clear` between unrelated tasks, and after two
  failed corrections restart with a sharper prompt. When compacting, keep the list
  of modified files and the test commands.
- **Ask when the decision is the human's** (`AGENTS.md` §11); otherwise pick the
  conventional default and say so.
