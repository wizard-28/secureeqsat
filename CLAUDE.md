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
