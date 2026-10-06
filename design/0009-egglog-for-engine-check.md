# 0009 — Add `egglog-python` for the engine feasibility check

- **Status:** accepted
- **Date:** 2026-10-06
- **Deciders:** Sourajyoti Basak

## Context

`design/0004` decided that the premise test runs on a minimal in-repo e-graph
(for speed of falsification and auditability) while the real system would use
`egglog-python` or `egg`. The feasibility push now needs to answer a question
the minimal engine cannot: **is the search-space blowup observed on a
two-gadget chain (3,000 classes in 2 saturation iterations with
distributivity) an artifact of an unoptimised toy engine, or is it inherent to
the rule set?**

That question decides whether the project's scalable path is engineering
(use a better engine) or research (restrict/schedule the rules).

`egglog` is a Datalog + equality-saturation engine (PLDI 2023) with official
Python bindings, MIT licensed.

## Decision

Add `egglog` to the project's dependency groups (dev group for now, since it is
used by `experiments/` and tests rather than by any shipped code), and port the
premise plus the chain to it under `experiments/egglog_port/`.

If `egglog` handles the chain with the full rule set, the blowup is an engine
limitation and the project can proceed on engineering; if it does not, the
blowup is in the rule set and must be addressed by rule design.

## Consequences

- One new dependency, MIT licensed, pinned by `uv.lock`.
- The port must reproduce the premise independently: if it does not, that is a
  finding about the minimal engine, not something to paper over.
- `design/0004` stands: the minimal e-graph remains the falsification harness;
  `egglog` is the candidate production engine.
- If the port shows the blowup is inherent, the project's feasibility assessment
  must be revised accordingly (see the feasibility report).

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Keep only the in-house engine | Cannot distinguish "toy engine is slow" from "rule set explodes", which is exactly the question |
| Use `egg` (Rust) | Strongest engine but a Rust build for a question `egglog` can answer in Python |
| Restrict rules first, never test a real engine | Would concede the engineering path without evidence |

## Evidence

- `experiments/egglog_port/` (port + measurements).
- `experiments/constrained_extraction/run_chain.py` — the chain that exposes the
  blowup in the minimal engine.
- `docs/feasibility-report.md` — consolidated findings.
