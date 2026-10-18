# SecureEqSat — Probing-Secure Equality Saturation

Equality saturation (e-graphs) for optimizing masked cryptographic circuits under
a first-order probing-security constraint.

> **New here?** Start with [`docs/getting-up-to-speed.md`](docs/getting-up-to-speed.md) — a 15-minute orientation.

> **Status: mid-flight.** This repository is at Review 1. The headline result is a
> *soundness* finding plus a repair, **not** an optimization win. See
> [`project_context.md`](project_context.md) for the live snapshot, and
> [`docs/adversarial-search-3.md`](docs/adversarial-search-3.md) for the
> calibrated novelty claims and their residual risks. Explicit non-claims are
> listed in the proposal, §11.2.

## What we found

Applying ordinary Boolean equality saturation to a masked circuit is **unsound**:
running distributivity backwards refolds the shares and materialises the unmasked
secret — and cost-optimal extraction *prefers* that outcome, because it is
cheaper (7 gates vs 8). Reproduced on two independent engines, leaking on
identical wires.

The leak is found by an in-house exact checker that has itself been
cross-validated against VerifMSI over 1,216 circuits / 21,760 wires (0
disagreements).

The repair is security-constrained extraction. The open research question is why
the optimizations that matter — refresh insertion/removal, randomness reuse,
gadget substitution — are **not congruences** of the wire-term algebra, and so
cannot be the equality relation of a plain e-graph.

## Onboarding

```bash
git clone <repo-url> && cd <repo>
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . bash -lc 'uv run pytest -q'
```

That is the whole setup. `postCreateCommand` provisions everything:

1. `uv`, `ruff`, `pyright`, and `.venv` from the committed `uv.lock`
2. the **VerifMSI oracle**, shallow-cloned into a named volume at `~/oracles`

Expect **77 passed** on a fresh container. There is nothing else to install.

If the oracle clone fails — offline, or a blocked network — the container still
comes up, and the five cross-check tests **skip**. A skip is not a pass: re-run
`bash experiments/oracle_crosscheck/setup_oracles.sh` and re-check before making
any security claim (`AGENTS.md` §6.3).

Working without a container is also fine:

```bash
uv sync && uv run pytest -q
```

Requires [uv](https://docs.astral.sh/uv/). There is no system Python: `uv`
provisions the interpreter (`requires-python = ">=3.12"`; the container pins
CPython 3.14).

## Commands

| Command | What it does |
|---|---|
| `uv sync` | Create/refresh `.venv` from the committed `uv.lock` |
| `uv run pytest -q` | Regression tests |
| `uv run ruff check .` | Lint |
| `uv run ruff format --check .` | Format check |
| `uv run python experiments/premise_test/run.py` | Narrative premise test |
| `uv run python experiments/constrained_extraction/run_constrained.py` | Constrained extraction |
| `uv run python experiments/egglog_port/port.py --circuit chain --rules full --iters 4` | `egglog` engine check |
| `uv run python experiments/labeller/measure.py` | Labelling cost: reference vs bitsliced labeller |

`uv run <cmd>` is the only sanctioned way to execute Python. `ruff` and `pyright`
are installed as `uv tool`s and invoked as bare commands.

## Dev container

Prerequisites: Docker, and the
[dev container CLI](https://github.com/devcontainers/cli) (`devcontainer`). VS Code's
Dev Containers extension also works — see below.

```bash
devcontainer up --workspace-folder .                              # create and start
devcontainer up --workspace-folder . --remove-existing-container  # rebuild
devcontainer exec --workspace-folder . bash                       # shell inside it
```

Rebuild after editing anything under `.devcontainer/` or `pyproject.toml`.
`postCreateCommand` runs [`scripts/setup-tools.sh`](scripts/setup-tools.sh), which
installs `uv`, `ruff` and `pyright`, then builds `.venv` from the committed
`uv.lock`.

The CLI generates `.devcontainer-lock.json` to pin dev container **Feature**
versions, and it is worth committing when it appears — like `uv.lock`. This
configuration declares no Features, so none is written; `--no-lockfile` opts out
and `--frozen-lockfile` enforces an existing one if you add any.

The shared configuration also declares one named volume, `secureeqsat-oracles`,
mounted at `~/oracles`. It holds the VerifMSI oracle, which the trust boundary
requires but which is GPLv3 and so must stay outside the repository
(`AGENTS.md` §6.4, `design/0005`). The volume means it is cloned once rather
than on every rebuild.

> **If you add a mount below `$HOME`**, add its target to `VOLUME_MOUNTS` in
> `scripts/setup-tools.sh`. Docker creates mount points and any missing parents
> as **root**, and an omitted entry fails later as a confusing permission error
> that only appears on a fresh container.

### The container is agent-neutral

It installs **no** coding agent. Install whichever one you use, following that
tool's own instructions.

If you use **opencode** specifically, there is an opt-in personal configuration:

```bash
cp .devcontainer/personal/devcontainer.example.json \
   .devcontainer/personal/devcontainer.json
```

Then select it on the command line — `--config` applies for that invocation only,
so nothing is imposed on anyone else:

```bash
devcontainer up --workspace-folder . \
  --config .devcontainer/personal/devcontainer.json \
  --remove-existing-container
```

That configuration adds the three named volumes that keep opencode's config, data
and cache alive across rebuilds, and runs
[`scripts/setup-opencode.sh`](scripts/setup-opencode.sh). If you would rather keep
using the default configuration and overlay only a partial file, the CLI also
accepts `--override-config <path>`.

It is deliberately **not** part of the shared configuration: teammates using
other agents should not have opencode installed for them. `.devcontainer/personal/`
is gitignored apart from the example template. See `design/0012`.

<details>
<summary>Using VS Code instead of the CLI</summary>

`F1` → **Dev Containers: Reopen in Container**, and pick **"Research (personal)"**
from the configuration picker to get the personal configuration. Rebuild with
`F1` → **Dev Containers: Rebuild Container**.

</details>

### Agent instructions

Normative guidance lives in [`AGENTS.md`](AGENTS.md), which is read natively by
Codex, Claude Code, Cursor, Copilot, opencode and others.

A thin [`CLAUDE.md`](CLAUDE.md) imports it with `@AGENTS.md`. That is not
decoration: Claude Code stops reading `AGENTS.md` once **any** `CLAUDE.md` or
`CLAUDE.local.md` exists — including a teammate's personal one — so without the
pointer a local preferences file would silently drop the entire protocol.

Repeatable procedures are packaged as skills in [`.claude/skills/`](.claude/skills/),
a location both Claude Code and opencode read, so they are shared rather than
duplicated per tool:

| Skill | Use it when |
|---|---|
| `secureeqsat-gate` | Finishing a change, or before any commit |
| `secureeqsat-adr` | A decision needs recording in `design/` |
| `secureeqsat-citation-check` | A citation or novelty claim is about to enter a document |

`CLAUDE.local.md` is gitignored — personal preferences only, never committed.

## Where things live

| Path | Contents |
|---|---|
| [`project_context.md`](project_context.md) | **Live project state — read this first** |
| [`AGENTS.md`](AGENTS.md) | Working norms: research, engineering, documentation, git |
| [`design/`](design/) | ADRs, one file per non-trivial decision |
| [`docs/probing-secure-eqsat-proposal.md`](docs/probing-secure-eqsat-proposal.md) | The Review 1 proposal (revision 3) |
| [`docs/feasibility-report.md`](docs/feasibility-report.md) | Consolidated feasibility checks and confidence levels |
| [`docs/adversarial-search-2.md`](docs/adversarial-search-2.md) | Second adversarial pass, with its query log |
| [`docs/adversarial-search-3.md`](docs/adversarial-search-3.md) | Third adversarial pass + scaling measurements |
| [`docs/team-briefing-plan-a.md`](docs/team-briefing-plan-a.md) | Why the original direction was closed, and what replaced it |
| [`experiments/`](experiments/) | Premise test, oracle cross-check, constrained extraction, `egglog` port |
| `docs/original/` | Historical record of the closed direction — **do not edit** |

Negative results in this repository carry the exact queries that produced them,
and novelty claims are calibrated rather than asserted. See `AGENTS.md` §5.

## Licence

Not yet chosen — the repository is private. Add a licence before making it
public.
