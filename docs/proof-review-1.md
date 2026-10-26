# Proof review #1 — `docs/theory.md` C1–C9

**Date:** 2026-10-26 · **Commit reviewed:** `4607443` · **Reviewer:** Claude (AI
assistant), for the author.

This is a second reader's pass, not the author's sign-off. The checklist in
the verification plan asks the author to tick each claim only when they would
defend it at the review, so nothing here ticks a box. One finding changed a
claim (C5(b), `design/0021`); the other gaps are listed for the author and
were **not** patched in `docs/theory.md`.

## Summary

| Claim | Verdict | Gap or note |
|---|---|---|
| C1 | Holds | Needs one fixed variable set (inputs and randoms named globally), which the wire-level e-graph has |
| C2 | Holds | Recomputed by hand from `F1.txt`/`F1b.txt` (below) |
| C3 | Holds | Share equations match `gadgets.py` |
| C4 (a) | Holds | R1 also rewrites with `not`, which the §1 grammar omits |
| C4 (b) | Holds against the code; **papers not re-read** | Induction omits the `not` and `reg` cases (both one line); gadget base cases checked against `gadgets.py` and standard first-order forms, not against the papers' text |
| C5 (a) | Holds | — |
| C5 (b) | Holds **for R3 alone**; false for R1 + R3 | Counterexample below; claim narrowed (`design/0021`) |
| C6 | Holds | — |
| C7 | Holds | The last proof sentence can be tightened (below) |
| C8 | Holds for circuits without dead wires | "Every wire lies in some output's cone" is a precondition; extracted circuits satisfy it, arbitrary ones need not. First order only, as stated |
| C9 | Substance holds; **citation numbering unconfirmed** | "Composable" must be a least fixed point; "safety is a class label" overstates (below) |

## Details

**C2.** The 7-gate extraction is `c0 = a0b0 ⊕ r`, `c1 = (r ⊕ a0b1) ⊕ a1(b0 ⊕ b1)`:
3 AND + 4 XOR; `c0 ⊕ c1 = ab`; the wire `b0 ⊕ b1` equals `b`, and
`a1 ∧ (b0 ⊕ b1)` also leaks. Both checkers report exactly these two wires.

**C4(b) base cases vs `experiments/resharing/gadgets.py`.**
ISW: `c0 = a0b0 ⊕ r`, `c1 = ((r ⊕ a0b1) ⊕ a1b0) ⊕ a1b1`, the 2-share ISW
order. DOM-indep: `c0 = a0b0 ⊕ (a0b1 ⊕ z)`, `c1 = a1b1 ⊕ (a1b0 ⊕ z)`,
registers elided. HPC1: DOM-indep with the second operand refreshed by one
random (2 randoms). All XOR to `a ∧ b`. Still open: the gate-by-gate
comparison with the original papers (ISW CRYPTO 2003, DOM ePrint 2016/486,
HPC ePrint 2020/185). They were not fetched in this pass, and `gadgets.py`
cites Knichel & Moradi for HPC1, not the HPC paper.

**C5(b) counterexample.** All acyclic one-node-per-class extractions of
`square` were enumerated. Under R3 alone there is 1 (`isw(z, z)`), and it
leaks, as claimed. Under R1 + R3 there are 338, of which 16 are secure. The
in-house checker and VerifMSI agree on all 16 (416 wires, 0 disagreements).
One of them is `isw(a, a ⊕ b) ⊕ isw(b, a ⊕ b)`. The witness test only ran R3,
so it could not catch this; `test_c5b_is_specific_to_r3_alone` (mutation-
checked: it fails with R3 alone) and `test_c5b_counterexample_agrees_with_verifmsi`
now record it.

**C7, suggested wording.** The proof is sound, but "the context adds only
variables that are uniform and independent of that observation, or secrets
that it does not depend on" does more work than needed. Simpler: the
observation is a function of the cone's variables only. Those variables are
shares of the cone's secrets plus the cone's randoms, and their joint
distribution, for each assignment of the cone's secrets, is the same in the
subterm and in the context, because sharings of distinct secrets are
independent and memoised lowering reuses a subterm's randoms consistently. So
a secret-dependent distribution stays secret-dependent. This holds in both
models: the glitch-extended stable set is a function of the cone.

**C9.** Checked against the text of a 2018 copy of Cassiers & Standaert
(`perso.uclouvain.be/fstandae/PUBLIS/237.pdf`). The final 2020 ePrint PDF was
not reachable from this session. In that copy the two results are
*Proposition 2* ("Any t-PINI gadget (with a number of shares d > t) is
t-probing secure", with independent input encodings used in the proof) and
*Proposition 3* ("Any composite gadget made of t-PINI composing gadgets is
t-PINI"). Their preconditions hold here:

- the composition is a DAG (their Definition 1; our terms are acyclic);
- random gates are fresh per invocation (lowering allocates per gadget instance);
- input vertices may fan out to any number of gadgets, so `hpc1(z, z)` is covered;
- 2 shares > 1 probe;
- the primary inputs are independent sharings;
- the model is glitch-free probing.

Three notes for the author:

1. **Numbering.** `docs/adversarial-search-5.md` and this theory cite "Property 11"
   and "Property 12". In Cassiers's 2022 PhD thesis, Propositions 11 and 12 are
   *different* results, about duplicated PINI with 2t + 1 shares. Confirm the
   numbers against the 2020 ePrint PDF, or cite by statement and version.
2. **Least fixed point.** The definition "a node whose operator is 1-PINI and
   whose children are composable" must be read as a least fixed point. Under
   R3, `refresh(z)` sits in `z`'s own class, so a greatest fixed point would
   accept a class on a self-loop. `analysis.composable_classes` already
   computes the least fixed point; the text should say so.
3. **"Safety is a class label."** A composable class can still hold a leaking
   ISW/DOM term. What C9 shows is that every PINI-only extraction of a
   composable class is secure. The "Relation to C5" paragraph says this, but
   the claim's first sentence reads stronger.

## Not done in this pass

- The author's own line-by-line check, and the ticks.
- C4(b) against the original gadget papers; C9 against the 2020 PDF (both
  need sources this session could not fetch).
