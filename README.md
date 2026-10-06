# SecureEqSat — Probing-Secure Equality Saturation

Equality saturation (e-graphs) for optimizing masked cryptographic circuits under
a first-order probing-security constraint.

> **Status: mid-flight.** This repository is at Review 1. The headline result is a
> *soundness* finding plus a repair, **not** an optimization win. See
> [`project_context.md`](project_context.md) for the live snapshot, and
> [`docs/adversarial-search-3.md`](docs/adversarial-search-3.md) for the
> calibrated novelty claims and their residual risks.

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

## Quick start

Requires [uv](https://docs.astral.sh/uv/). There is no system Python.

```bash
uv sync
uv run pytest -q
uv run ruff check .
```

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

`uv run <cmd>` is the only sanctioned way to execute Python. `ruff` and `pyright`
are installed as `uv tool`s and invoked as bare commands.

## Dev container

Prerequisites: Docker, and the VS Code **Dev Containers** extension.

Open the folder in a container: `F1` → **Dev Containers: Reopen in Container**.
`postCreateCommand` runs [`scripts/setup-tools.sh`](scripts/setup-tools.sh), which
installs `uv`, `ruff` and `pyright`, then builds `.venv` from the committed
`uv.lock`.

Rebuild after editing anything under `.devcontainer/` or `pyproject.toml`:
`F1` → **Dev Containers: Rebuild Container**.

### The container is agent-neutral

It installs **no** coding agent. Install whichever one you use, following that
tool's own instructions.

If you use **opencode** specifically, there is an opt-in personal configuration:

```bash
cp .devcontainer/personal/devcontainer.example.json \
   .devcontainer/personal/devcontainer.json
```

Then pick **"Research (personal)"** from the Dev Containers configuration picker
when you rebuild. That configuration adds the three named volumes that keep
opencode's config, data and cache alive across rebuilds, and runs
[`scripts/setup-opencode.sh`](scripts/setup-opencode.sh).

It is deliberately **not** part of the shared configuration: teammates using
other agents should not have opencode installed for them. `.devcontainer/personal/`
is gitignored apart from the example template. See `design/0012`.

### Without a container

```bash
uv sync && uv run pytest -q
```

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
| [`experiments/`](experiments/) | Premise test, oracle cross-check, constrained extraction, `egglog` port |
| `docs/original/` | Historical record of the closed direction — **do not edit** |

Negative results in this repository carry the exact queries that produced them,
and novelty claims are calibrated rather than asserted. See `AGENTS.md` §5.

## Licence

Not yet chosen — the repository is private. Add a licence before making it
public.
