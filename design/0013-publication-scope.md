# 0013 — Publication scope for the repository

- **Status:** accepted
- **Date:** 2026-10-06
- **Deciders:** Sourajyoti Basak

## Context

The repository is being given a git remote and pushed to a **private** GitHub
repository. Three binary artifacts are tracked:

| File | Size | Authorship |
|---|---|---|
| `docs/original/llm-agent-equality-saturation-research-overview.pdf` | 27 KB | team (ReportLab) |
| `docs/original/llm-eqsat-group-pitch.pdf` | 287 KB | team (Skia) |
| `docs/teammates-made/secureeqsat-review1 (2).pptx` | 106 KB | **a teammate** (PptxGenJS/LibreOffice) |

An audit found no secrets, no API keys and no personal names in any tracked text
file, and no author names embedded in the binaries (`dc:creator` is empty). The
PDFs are the historical record of the **closed** direction, which `AGENTS.md`
designates as do-not-edit provenance. The PPTX is a third party's work product,
and is a presentation rather than a curated artifact.

## Decision

The two PDFs stay tracked. The teammate's PPTX is untracked (`git rm --cached`;
the file stays on disk) and `docs/teammates-made/` is gitignored, to be published
only with its author's recorded consent. No `LICENSE` is added while the
repository is private.

## Consequences

- **The PPTX remains in git history** — it was added in `df67155`, and untracking
  does not unpublish it. Anyone with repo access can retrieve it, and it would
  become public on a public flip. This is accepted *because the repository is
  private*; it is a blocking item for going public.
- Before a public flip: purge it from history **and** add a `LICENSE`.
- Purge command — no new tooling, `git filter-branch` ships with git:

  ```bash
  git filter-branch --index-filter \
    'git rm -r --cached --ignore-unmatch docs/teammates-made' -- --all
  rm -rf .git/refs/original
  git reflog expire --expire=now --all && git gc --prune=now
  ```

  This rewrites **every** commit hash, so it must happen before the first push
  (or before any hash is quoted). It also invalidates the commit-hash references
  in `project_context.md` and `design/0008`.
- Publishing `docs/adversarial-search-*.md` publishes our novelty boundaries and
  residual risks. That is deliberate: it is the audit trail that defends
  priority, and `AGENTS.md` §5 requires the negative results to be auditable.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Purge the PPTX from history now | Rewrites all 10 commit hashes and invalidates hash references in `project_context.md` / `design/0008`, for an artifact already visible to the team in a private repo. Cheaper and safer at the public flip |
| Publish the PPTX | A third party's work product; no recorded consent |
| Drop the PDFs from the repo | They are the designated historical record and team-authored; provenance is the point of `docs/original/` |
| Add a permissive `LICENSE` now | Premature for a private repo, and it is a scope decision worth taking deliberately |

## Evidence

- `git log --diff-filter=A -- "docs/teammates-made/secureeqsat-review1 (2).pptx"`
  → added in `df67155`.
- `unzip -p … docProps/core.xml` → empty `dc:creator`, no author name.
- `strings docs/original/*.pdf` → ReportLab / Skia producers only.
- Email/secret scan over `git ls-files` → no hits.
- `git filter-branch -h` available; no dependency added.
