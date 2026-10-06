---
name: secureeqsat-adr
description: Write an Architecture Decision Record for SecureEqSat in the design/ directory, including numbering, template, index update and the append-only rules. Use when a change involves scope, toolchain or dependencies, the security model or trust boundary, architecture, or superseding an earlier decision.
---

# Writing an ADR

Canonical rules: `AGENTS.md` §7.2–7.3 and `design/README.md`. This skill is the
operational checklist; those files win if they disagree.

## 1. Does this need an ADR?

Yes if the change involves any of:

- a **scope** change (what is in or out of the project)
- a **toolchain, dependency or environment** decision
- the **security model, the checker, or the trust boundary**
- an **architectural** decision (engine, extraction, IR, evaluation methodology)
- **superseding** a previous decision

Small fixes, refactors and test additions do not. If in doubt, write one — it is
cheap, and the alternative is relitigating the decision in week six.

## 2. Number and file name

```bash
ls design/            # find the next free NNNN
```

`design/NNNN-kebab-case-title.md`. Numbers are monotonic and never reused.

## 3. Template

Use the template in `design/README.md`. In order: Status / Date / Deciders, then

- **Context** — what forces are at play, what was true before this decision
- **Decision** — one or two sentences, active voice
- **Consequences** — what becomes easier, what becomes harder, what is now a
  constraint, and **the cost of being wrong**
- **Alternatives considered** — a table, each with why it was rejected
- **Evidence** — fetched sources, experiment paths, or an explicit note that this
  was judgement

Roughly one screen. `Status:` is `proposed`, `accepted`, or `superseded by NNNN`.

## 4. Append-only — do not rewrite history

Never rewrite the reasoning, consequences or alternatives of an existing ADR.

- **Reversing** a decision: write a **new** ADR, and set the old one's status line
  to `superseded by NNNN`.
- **Completing** a decision, or its location changing: leave the body alone,
  append a dated `## Status updates` section, and update its index row.

## 5. Finish

- [ ] ADR file written.
- [ ] Row added to the `design/README.md` index.
- [ ] `project_context.md`: decision-log row **and** a change-log line.
- [ ] All of it in the same commit as the change the ADR describes.
