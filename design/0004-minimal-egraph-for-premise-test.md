# 0004 — Minimal in-repo e-graph for the premise test; egglog for the real engine

- **Status:** accepted
- **Date:** 2026-10-06
- **Deciders:** project team

## Context

The project's go/no-go question was: *does unrestricted Boolean equality saturation plus
cost-minimal extraction actually produce a functionally equivalent but probing-insecure
circuit?* Answering it required a working e-graph quickly, with enough transparency to
audit the result.

Two incidents made auditability decisive rather than nice-to-have: the first checker version
compared value sequences instead of distributions and flagged secure circuits as broken; and
the first "ISW" fixture was itself insecure because the fresh random was folded in too late.
Both were caught only because the code was small enough to inspect and test. Pulling in a
large external engine would have made both bugs harder to localize.

At the same time, the project's real system must run on a mature e-graph engine — the
proposal specifies `egglog-python` (primary) and `egg` (fallback).

## Decision

- For the premise test, implement a **minimal in-repo e-graph** (`experiments/premise_test/egraph.py`):
  union-find, hashcons, rebuild, saturation with a Boolean rule set, tree-cost fixed-point
  extraction, and materialization to a circuit.
- The real system will use **`egglog-python`** (or `egg` if the Python engine becomes a
  bottleneck). This was decided in the proposal, not by this ADR.
- The minimal e-graph is a **test harness, not a product**: it does not grow features beyond
  what the falsification needs.

## Consequences

- The premise result is currently established on a home-grown engine. It **must be
  re-confirmed under `egglog`** before being treated as a systems result. This is a planned
  next action, not an open question.
- The harness stays dependency-free and fast (full suite runs in ~0.02 s), which keeps the
  go/no-go loop cheap.
- Risk: the minimal extractor is tree-cost only and may differ from a production engine's
  DAG-aware extraction. The phenomenon it demonstrates (refactoring shares produces a
  strictly cheaper insecure circuit) is algebraic and should transfer, but that is an
  assumption to verify, not a fact.
- Contributors must resist "improving" the harness — every added feature is a liability
  (`AGENTS.md` §6.7).

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Use `egglog` from the start | Slower to falsify; adds a dependency and version churn; harder to audit the two bugs that mattered |
| Hand-construct the insecure circuit without an e-graph | Would not test the premise — the claim is that *search plus cost extraction* finds it |
| Use `egg` (Rust) for the harness | Best control, but a compile step and Rust context switch for a one-day falsification |

## Evidence

- `experiments/premise_test/egraph.py`, `masked.py`, `test_premise.py`, `RESULTS.md`.
- `docs/probing-secure-eqsat-proposal.md` §14 (engine choice).
- `AGENTS.md` §9 (the sequence-vs-distribution and ISW-ordering anti-patterns).
