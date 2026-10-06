# 0014 — Provision the VerifMSI oracle for every teammate

- **Status:** accepted
- **Date:** 2026-10-06
- **Deciders:** Sourajyoti Basak

## Context

The external VerifMSI oracle is the project's **mandatory trust boundary**
(`AGENTS.md` §6.3, `design/0005`): no security claim may rest on the in-house
checker alone, and `AGENTS.md` §11 makes a disagreement a stopping condition.

It was set up manually, into `~/oracles`, which lives in the container's writable
layer. Consequences observed on the first real rebuild:

- `~/oracles` was destroyed, and the three cross-check tests went from **passing
  to skipping** — silently, since a skip looks like a clean run in a summary line.
- A teammate following the README would therefore get a green-looking suite with
  the trust-boundary check never executed.

`setup_oracles.sh` is a shallow `git clone` plus `uv venv` (VerifMSI is pure
stdlib, so there is nothing to install), and it is already idempotent. Nothing
about it is expensive, and nothing about it needs to be per-user: the oracle is
the same for everyone.

The oracle is GPLv3 and must remain outside the repository (`AGENTS.md` §6.4,
`design/0005`) — cloned at container-create time, never vendored or committed.

## Decision

Add a fourth named volume, `secureeqsat-oracles` → `~/oracles`, to the **shared**
configuration, and have `scripts/setup-tools.sh` run
`experiments/oracle_crosscheck/setup_oracles.sh` as part of
`postCreateCommand` — **non-fatally**: on failure it prints a warning and
continues rather than failing the container.

## Consequences

- A fresh clone reaches **10 passed** in three commands, with the trust boundary
  actually exercised. That is the point of the change.
- The oracle is cloned once, not per rebuild, because the volume persists.
- **Every teammate's container now downloads GPLv3 software at create time,
  whether or not they asked.** The licence is respected (external process,
  outside the tree), but a teammate behind a restrictive network or policy
  should know. Removing the volume from `.devcontainer/devcontainer.json`
  reverts this to the previous opt-in behaviour.
- Container creation now depends on `github.com` being reachable. The non-fatal
  path keeps that from being fatal, at the cost of a warning that is easy to
  miss — so the README's onboarding section states plainly that a skip is not a
  pass.
- `setup-tools.sh` must stay in sync with the `mounts` lists; a drift here fails
  only on a fresh container, which is why the README documents the invariant
  next to the mount example.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Leave it opt-in, document the command | The trust boundary is mandatory, not optional. Making a required check depend on remembering a command produces exactly the silent-skip failure seen on rebuild |
| Volume only, no auto-install | Removes the re-clone cost but still needs a manual step, so the skip failure remains |
| Clone inside the repository | Violates `AGENTS.md` §6.4 and `design/0005` — GPLv3 is never vendored |
| Bake VerifMSI into a custom image | Same licence exposure plus a maintained Dockerfile; heavier than a volume plus a clone |
| Auto-install and *fail* the container on error | A flaky network would leave a broken container, which is worse for onboarding than a warning |

## Evidence

- Observed directly after the 2026-10-06 rebuild: `~/oracles` absent, and
  `uv run pytest -q` reporting `7 passed, 3 skipped` with
  `SKIPPED: VerifMSI oracle not set up (run setup_oracles.sh)`.
- `experiments/oracle_crosscheck/setup_oracles.sh` — idempotent shallow clone +
  `uv venv`; VerifMSI is stdlib-only, so no dependency is introduced.
- `experiments/oracle_crosscheck/test_crosscheck.py` — `skipif(not
  oracle_available())`, i.e. absence is silent by design at the test level.
- `AGENTS.md` §6.3 (mandatory cross-check), §6.4 (GPL handled externally), §11
  (stopping condition).
