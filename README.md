# SecureEqSat — Probing-Secure Equality Saturation

What happens when you optimize **masked cryptographic circuits** with
**equality saturation** (e-graphs), the rewrite-everything-then-pick-the-cheapest
technique from modern compilers? This repository answers that question
experimentally and theoretically for first-order, 2-share, straight-line
circuits.

**Short answer:** it silently breaks the masking. It can be repaired, but the
optimizations that matter for masking are not plain equalities of circuits, and
that changes how extraction has to work.

> **Scope of every result:** first order, 2 shares, straight-line Boolean
> circuits; glitch-free probing unless the glitch-extended model is named
> (`design/0018`). Every security verdict is cross-checked against an
> independent tool, VerifMSI.
>
> **Checking the results?** [`findings/README.md`](findings/README.md) indexes
> every finding, and `uv run python findings/verify.py --full` re-runs all of
> them (14 steps, about 5 minutes; last full run: 14 of 14 pass).
>
> **New here?** [`docs/getting-up-to-speed.md`](docs/getting-up-to-speed.md) is
> a 15-minute orientation. [`project_context.md`](project_context.md) is the live
> project state.

---

## Findings

Each finding has an ID that matches [`findings/README.md`](findings/README.md)
and a step in `findings/verify.py`.

### 1. Equality saturation is unsound for masked circuits (F1)

Take the secure 8-gate ISW masked AND, add ordinary, correct Boolean rewrite
rules (commutativity, associativity, distributivity, factoring), saturate, and
extract the cheapest circuit. You get **7 gates that compute `b0 ⊕ b1`, the
unmasked secret `b`**. The optimizer prefers the leak *because* it is cheaper.
The same leak appears on the in-house e-graph and on egglog.

### 2. The checkers are trustworthy (F2)

The in-house exact checker agrees with VerifMSI on **1,216 circuits / 21,760
wires**, and the fast bitsliced labeller on **1,265 circuits / 22,463 wires**,
with **0 disagreements**. No security claim here rests on the in-house checker
alone.

### 3. Security-constrained extraction repairs it (F3)

In the glitch-free model, a wire's safety depends only on the function it
computes, so each e-class can be labelled safe or unsafe once. Extracting only
from safe classes recovers the **secure 8-gate ISW**: security costs 1 gate
over the cheapest insecure circuit.

### 4. Plain Boolean rewriting does not pay at chain scale (F4, F5)

On a hand-written two-gadget ISW chain (16 gates, secure), the cheapest
extraction is 14 gates and insecure, and **none of the 240 sampled
extractions is secure** (28 are cheaper than the 16-gate chain, 58 equal it, 154
cost more). Search and labelling are not the bottleneck: egglog
saturates a depth-5 chain in under 0.01 s, and the bitsliced labeller labels
it in about 0.4 s.

### 5. One level up, masking moves become rewrites, but only remove slack (F6, F7)

At a **shared-value layer**, where sharings are identified by the value they
reconstruct, refresh removal (`refresh(x) = x`) and gadget substitution
(`isw = dom = hpc1`) are ordinary e-graph rewrites. Results, with cost = gates +
random bits:

- over-refreshed chain **30 → 18**;
- `a&b ⊕ a&d` **20 → 11** (factoring);
- dropping a refresh that is *needed* is cheaper (11) and leaks; the
  constrained extractor keeps it (14).

**Tight published constructions gain nothing:** the chain (18) and Keccak χ on
3- and 5-bit rows (36, 60) are unchanged under every rule class. Every gain
removes slack someone put in the start circuit.

### 6. Same class, different security: extraction must be occurrence-aware (theory C3–C7)

Refresh, and registers in the glitch model, are **value-preserving but
leakage-changing**. They put a secure term and a leaking term in the same
e-class: `isw(z, z)` leaks while `isw(z, refresh(z))` is secure. So safety is
no longer a label of the class, and extraction must choose per occurrence.
The repair is term-based extraction with a **monotone leak cut**: a leaking
subterm leaks in every context, so it can be discarded for good.

With refresh removal alone (rule set R3), ordinary one-node-per-class
extraction of `square` misses every secure circuit. With the Boolean rules
added (R1 + R3), secure DAG extractions exist again (16 of 338; VerifMSI
agrees). The obstruction depends on the rule set (`design/0021`).

### 7. The story carries over to glitches (F8, theory C6)

In the glitch-extended model, safety is **not** a function of the wire: two
wires computing the same function can differ in glitch security, depending on
where registers sit. If registers are treated as removable, a registered DOM
gadget shrinks **10 → 5** and a chain **20 → 10**, and both leak.
Occurrence-aware extraction puts the registers back (**10** and **20**,
secure). The glitch checker agrees with VerifMSI's own leakage sets on **167
probes**, with 0 disagreements.

### 8. On PINI gadgets, safety is a class label again, at any size (F11, theory C9)

Built only from gadgets that compose safely (**PINI**: share-wise XOR and NOT,
refresh, HPC1), any composition is first-order secure, so ordinary
one-node-per-class extraction is sound with no enumeration at all.

- Gadget PINI verdicts agree with VerifMSI on all 6 operators.
- 234 random PINI-only terms: 0 leaking.
- Keccak χ on a 32-bit row (a 2^128-point space) and ISW chains to depth 15
  are decided in ≤ 0.03 s and certified wire by wire by VerifMSI.
- **Price:** up to **+33 %** cost over the exact optimum. **Glitch-free model
  only.**

### 9. What we do *not* claim (F10)

- **No win over any tight, published construction.**
- The optimizations themselves (refresh removal, factoring, gadget choice,
  register placement) are known in masking compilers.
- That optimizers can break (glitch-robust) masking is known.
- PINI composition is used in the glitch-free model only; nothing on SNI,
  higher orders or glitch-robust composition.
- Extraction is exact only on its k-best frontier.

What may be new is narrow: the unsoundness result, the shared-value
representation, the same-class-different-security obstruction and its two
repairs. Prior-art passes put this at **medium confidence**
([`docs/adversarial-search-4.md`](docs/adversarial-search-4.md),
[`-5.md`](docs/adversarial-search-5.md)); a sixth pass is still outstanding.

---

## How we found it

### The working method

1. **Kill the idea before building it.** The project began as LLM-guided
   equality saturation for general compiler IR. Two adversarial literature
   searches showed that direction was occupied, and it was closed
   ([`docs/team-briefing-plan-a.md`](docs/team-briefing-plan-a.md)). Every later
   claim went through a further pass with a recorded query log
   (`docs/adversarial-search-*.md`).
2. **A claim that is not a test is a hope.** Every experiment ends in
   assertions that fail if the finding is wrong, and every directory has a
   `RESULTS.md` (question, method, results, what it does and does not show).
3. **An external trust boundary.** Security verdicts are cross-checked against
   [VerifMSI](https://github.com/quentin-meunier/VerifMSI), run as a separate
   process (it is GPL). A disagreement is a stopping condition.
4. **Decisions are written down** as ADRs in [`design/`](design/), one per
   decision, append-only.

### The experiments, in order

| Step | Question | How | Where |
|---|---|---|---|
| Premise test | Does ordinary rewriting break masking? | A minimal in-repo e-graph saturates ISW AND with Boolean rules; an exact first-order checker compares each wire's **distribution** (not its values) across all secret assignments | `experiments/premise_test/` |
| Engine check | Is that an artifact of our e-graph? | The same circuits on egglog, with its own extractor and a k-best frontier | `experiments/egglog_port/` |
| Trust boundary | Can we trust our checker? | 1,216 circuits (fixtures plus random circuits) lowered to VerifMSI and checked wire by wire | `experiments/oracle_crosscheck/` |
| Repair | Can extraction avoid the leak? | Label every e-class safe/unsafe, extract the cheapest circuit from safe classes only | `experiments/constrained_extraction/` |
| Scale | Is labelling the bottleneck? | A **bitsliced** labeller: each function is one truth table packed into an integer, and a wire is safe iff its 1-count is equal in every secret block | `experiments/labeller/` |
| Re-sharing | Can refresh and gadget choice be rewrites? | A shared-value sort in egglog with rule classes R1 (Boolean), R2 (gadget swap) and R3 (refresh); terms are lowered to 2-share circuits; term-based, occurrence-aware k-best extraction (cost = gates + randoms) with a leak cut | `experiments/resharing/` |
| Glitches | Does the story survive the glitch-extended model? | A stable-set checker (inputs and registers in a wire's cone); registers **opaque** vs **transparent** in egglog; VerifMSI's own leakage sets and `checkSecurity(withGlitches=True)` as the oracle | `experiments/glitch_probe/` |
| Theory | Why does it happen? | Claims C1–C9 in [`docs/theory.md`](docs/theory.md), each with an executable witness | `experiments/claims/` |
| Composition | Can extraction scale past exact checking? | An exhaustive 1-PINI checker per gadget, an e-class analysis ("composable" classes, least fixed point), and PINI-only DAG extraction; VerifMSI PINI mode and a symbolic certificate | `experiments/composition/` |
| Front end | Does it work as a compiler? | `seqc.py`: parse a small Boolean language, mask, saturate, extract with and without the constraint, verify, emit a netlist or Verilog | `experiments/frontend/` |

The proofs in `docs/theory.md` are being checked by hand
([`docs/proof-review-1.md`](docs/proof-review-1.md)). The executable witnesses
show each claim holds on the instances they try; they do not replace the
proofs.

### Reproduce everything

```bash
uv sync --python 3.14
bash experiments/oracle_crosscheck/setup_oracles.sh   # VerifMSI, outside the repo (GPL)
uv run python findings/verify.py --full               # 14 steps, ~5 min
uv run pytest -q                                      # 173 tests
```

A step that needs VerifMSI is **skipped** without it, and a skip is not a pass.
`findings/outputs/MANIFEST.json` records the commit, tool versions, VerifMSI
commit and a SHA-256 per output. Pass `--python 3.14`: without it, `uv` may
pick a newer interpreter for which egglog has no build.

---

## Setup

```bash
git clone <repo-url> && cd <repo>
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . bash -lc 'uv run pytest -q'
```

That is the whole setup. `postCreateCommand` provisions everything:

1. `uv`, `ruff`, `pyright`, and `.venv` from the committed `uv.lock`
2. the **VerifMSI oracle**, shallow-cloned into a named volume at `~/oracles`

Expect **173 passed** on a fresh container (19 skip if the VerifMSI oracle is absent). There is nothing else to install.

If the oracle clone fails — offline, or a blocked network — the container still
comes up, and the 19 oracle-dependent tests **skip**. A skip is not a pass: re-run
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
| `uv run python experiments/frontend/seqc.py experiments/frontend/examples/factor.sec` | Compile a source program to a masked netlist |
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
| [`findings/`](findings/README.md) | **Every finding, with `verify.py` to re-run it** |
| [`project_context.md`](project_context.md) | Live project state and change log |
| [`docs/theory.md`](docs/theory.md) | Claims C1–C9 and their proofs |
| [`docs/getting-up-to-speed.md`](docs/getting-up-to-speed.md) | 15-minute orientation |
| [`AGENTS.md`](AGENTS.md) | Working norms: research, engineering, documentation, git |
| [`design/`](design/) | ADRs, one file per non-trivial decision |
| [`experiments/`](experiments/) | One directory per experiment, each with a `RESULTS.md` |
| [`docs/adversarial-search-2.md`](docs/adversarial-search-2.md) … [`-5.md`](docs/adversarial-search-5.md) | Prior-art passes, with query logs |
| [`docs/probing-secure-eqsat-proposal.md`](docs/probing-secure-eqsat-proposal.md) | The Review 1 proposal |
| [`docs/feasibility-report.md`](docs/feasibility-report.md) | Feasibility checks and confidence levels |
| [`docs/team-briefing-plan-a.md`](docs/team-briefing-plan-a.md) | Why the original direction was closed |
| `docs/original/` | Historical record of the closed direction — **do not edit** |

## Licence

Not yet chosen — the repository is private. Add a licence before making it
public.
