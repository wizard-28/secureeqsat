# 0021 — State theory claim C5(b) for R3 alone

- **Status:** proposed
- **Date:** 2026-10-26
- **Deciders:** Shreyash Panigrahy (to confirm); analysis with Claude

## Context

`docs/theory.md` C5(b) says that for the `square` fixture every one-node-per-class
(DAG) extraction leaks while a secure term exists, and §5 left open whether to
prove it for every rule set without self-refreshing gadgets. The witness
(`test_c5_no_secure_dag_extraction_of_square_but_a_term_extraction_exists`)
saturates with R3 only.

Enumerating every acyclic DAG extraction of `square` under **R1 + R3** gives 338
extractions, 16 of them secure: in-house checker and VerifMSI agree on all 16
(416 wires, 0 disagreements). Example: `isw(a, a^b) ^ isw(b, a^b)`, reached by
distributivity, whose gadgets see independent operand sharings. R1 contains no
self-refreshing gadget, so the general statement is false. Adding AND-idempotence
(deliberately absent from R1) would also refute it: `square` would join the class
of `z`.

## Decision

State C5(b) only for the `square` fixture under R3 alone, and record the R1 + R3
counterexample as a test (`test_c5b_is_specific_to_r3_alone`, with VerifMSI
agreement in `test_c5b_counterexample_agrees_with_verifmsi`). No general proof is
attempted.

## Consequences

- C5(a) (non-class-locality) and the theorem's item 4 ("can miss every secure
  circuit") are unaffected: they need one rule set, and R3 alone is one.
- The paper must not suggest that DAG extraction is incomplete for rich rule
  sets in general; with R1 it can recover a secure circuit for `square`.
- Cost of being wrong: low; this narrows a claim and is backed by an exhaustive
  enumeration plus the external oracle.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Prove C5(b) for all rule sets without self-refreshing gadgets | False: R1 + R3 is a counterexample |
| Leave the wording as is ("for that fixture") | Ambiguous about the rule set; a reader could assume the full rule set |

## Evidence

- Enumeration and VerifMSI cross-check run 2026-10-26 on `4607443` (338 DAG
  extractions, 16 secure, 0 disagreements).
- `experiments/claims/test_claims.py::test_c5b_*`.
