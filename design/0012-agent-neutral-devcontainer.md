# 0012 — Make the shared dev container agent-neutral

- **Status:** accepted
- **Date:** 2026-10-06
- **Deciders:** Sourajyoti Basak

## Context

`devcontainer.json` installed opencode (via `curl | bash`) and declared three
named volumes holding its config, data and cache. That was fine while the whole
team used opencode; the team also uses Claude Code, so the shared configuration
was imposing one agent on everybody.

The request was to move the personal parts into a `devcontainer.local.json`,
described as a community standard built on the `extends` key. Investigation:

- **Nothing auto-loads a file by that name.** Discovery is path-based and fixed
  by the spec: `.devcontainer/devcontainer.json` (highest precedence),
  `.devcontainer.json`, `.devcontainer/<folder>/devcontainer.json`. A file named
  `devcontainer.local.json` under `.devcontainer/` is never read — the name is
  cosmetic, the *path* is the mechanism.
- **`extends` is real but unshipped.** `devcontainers/spec` issue #22 proposes it
  with Docker-Compose-style merge semantics (arrays are unioned, scalars
  overwrite, new keys added) and is still **open**, labelled `finalization`
  (last updated 2026-05-04). It appears in **neither** the base spec reference
  **nor** VS Code's own `devContainer.vscode.schema.json`.
- The documented alternative is a **sub-folder configuration**, which supporting
  tools offer as a separate *selectable* configuration rather than a merge.
  VS Code issue #10091 — the identical request — was closed pointing at exactly
  that.

## Decision

The shared `.devcontainer/devcontainer.json` provisions only team tooling
(`uv`, `ruff`, `pyright`, `.venv`) through `scripts/setup-tools.sh`, and installs
**no** coding agent. Optional personal additions live in
`.devcontainer/personal/devcontainer.json`, which is gitignored, with a tracked
`devcontainer.example.json` template. The opencode volumes and install move
there.

## Consequences

- Teammates on any agent get a clean container; nothing agent-specific is
  imposed. CI and Codespaces are unaffected, because they read
  `.devcontainer/devcontainer.json`.
- The personal configuration is **self-sufficient** and does not depend on
  `extends`, so it is correct whether or not a tool implements it; `extends` is
  documented as a commented-out option.
- The personal configuration must be **re-selected on each rebuild**, and
  Codespaces cannot offer it at all. Fallback: run
  `scripts/setup-opencode.sh` by hand.
- opencode state persists only under the personal configuration. The script
  warns when the state directories are not mounted volumes.
- A rebuild is required. Cost of being wrong is low: the shared configuration is
  strictly simpler, and the personal one is reproducible with a single `cp`.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| `.devcontainer/devcontainer.local.json` | Never read — the discovery paths above are the whole mechanism |
| Rely on `extends` for the personal config | Unshipped: spec #22 open, absent from both schemas. Self-sufficiency costs four repeated lines and removes the risk |
| Keep opencode in the shared configuration | Imposes one agent on teammates using a different one |
| Docker Compose + `docker-compose.override.yml` | Auto-merge does exist there, but converting from `image:` to Compose for one install line is disproportionate and changes CI behaviour |

## Evidence

- Fetched: `devcontainers/spec` `devcontainerjson-reference.md` and the live
  metadata reference (containers.dev) — no `extends`, three fixed discovery
  paths.
- Fetched: `microsoft/vscode`
  `extensions/configuration-editing/schemas/devContainer.vscode.schema.json` —
  adds only `customizations`/`extensions`/`settings`/`devPort`/`mcp`; no
  `extends`.
- `devcontainers/spec` #22 (open, `finalization`), #305 (open); discussion #28
  (maintainer: *"There is not today."*); `microsoft/vscode-remote-release` #10091
  (closed → sub-folder configurations).
- Local: `git log` on `.devcontainer/devcontainer.json`; `sudo -n true` confirms
  passwordless sudo for the volume `chown`.
