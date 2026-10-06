# Design records

Architecture Decision Records (ADRs) for this project. One file per non-trivial decision.

## When an ADR is required

Write one when the change involves any of:

- a scope change (what is in / out of the project)
- a toolchain, dependency, or environment decision
- the security model, the security checker, or the trust boundary
- an architectural decision (engine, extraction, IR, evaluation methodology)
- superseding a previous decision

Small fixes, refactors, and test additions do not need an ADR. If in doubt, write one — it
is cheap, and the alternative is relitigating decisions in week six.

## Rules

- Files are numbered `NNNN-kebab-case-title.md`, monotonically, never reused.
- **ADRs are append-only.** To reverse a decision, write a new ADR and update the old one's
  `Status` line to `superseded by NNNN`. Never rewrite the reasoning of a past decision.
- Keep each ADR short: context, decision, consequences, alternatives. One screen is ideal.
- Every ADR ends with the evidence that justified it (links, experiment paths, or
  "judgement — no experiment").

## Template

```markdown
# NNNN — Title

- **Status:** proposed | accepted | superseded by NNNN
- **Date:** YYYY-MM-DD
- **Deciders:**

## Context
What forces are at play. What was true before this decision.

## Decision
The decision, stated in one or two sentences, active voice.

## Consequences
What becomes easier, what becomes harder, what is now a constraint on future work.
Include the cost of being wrong.

## Alternatives considered
| Alternative | Why rejected |
|---|---|

## Evidence
Links to experiments, fetched sources, or an explicit note that this was judgement.
```

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-pivot-to-probing-secure-eqsat.md) | Pivot to probing-secure equality saturation | accepted |
| [0002](0002-scope-first-order-2-share-glitch-free.md) | Scope: first order, 2 shares, straight-line, glitch-free | accepted |
| [0003](0003-toolchain-uv-ruff-devcontainer.md) | Toolchain: uv, ruff, pytest, devcontainer-managed | accepted |
| [0004](0004-minimal-egraph-for-premise-test.md) | Minimal in-repo e-graph for the premise test; egglog for the real engine | accepted |
| [0005](0005-security-checker-and-trust-boundary.md) | Security checker and the external-oracle trust boundary | accepted — **gate open** |
| [0006](0006-security-constrained-extraction.md) | Security-constrained extraction design | accepted — unimplemented |
| [0007](0007-git-workflow.md) | Adopt git with trunk-based, logical-commit history | accepted |
| [0008](0008-automate-venv-and-identity.md) | Automate venv creation; keep git identity local | accepted |
| [0009](0009-egglog-for-engine-check.md) | Add `egglog` for the engine feasibility check | accepted |
| [0010](0010-reframe-soundness-and-resharing.md) | Reframe around soundness and the re-sharing gap | accepted |
