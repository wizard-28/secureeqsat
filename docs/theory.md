# Theory draft — value-preserving, leakage-changing operators in e-graphs

**Status:** draft for the workshop paper (`design/0018`), 2026-10-18.
Every claim has an executable witness in `experiments/claims/test_claims.py`
(named `test_cN_*`). A witness shows a claim is *stated* correctly on concrete
or random instances; it does not replace the proof. **The proofs below must be
checked line by line by the author before submission.**

---

## 1. Setting

**Masking (first order, 2 shares).** Each secret bit `s` is represented by
shares `(s0, s1)` with `s0` uniform and `s1 = s0 ⊕ s`. Fresh randoms are
uniform and independent. Circuits are straight-line over `⊕`, `∧`, constants,
inputs, and registers `reg(·)`.

**Wire terms.** A circuit is a DAG of wire terms; `⟦w⟧` is the Boolean
function a wire computes over the input variables.

**Leakage models.** A model `L` maps each wire `w` of circuit `C` to an
observation `O_L(w, C)`, a tuple of functions:

- *glitch-free:* `O(w) = ⟦w⟧`;
- *glitch-extended:* `O(w) = (⟦u⟧ : u ∈ St(w))`, where `St(w)`, the *stable
  set*, is the set of inputs and register outputs in `w`'s combinational cone:
  `St(u) = {u}` for an input or register, `St(g(x, y)) = St(x) ∪ St(y)`.

`C` is **L-secure** if for every wire `w`, the distribution of `O_L(w, C)`
under the masking distribution is the same for every secret assignment.

**E-graphs.** An e-graph over wire terms holds a congruence `≡` — formally a
partial congruence relation (Suciu, Wang, Zhang, *Semantic Foundations of
Equality Saturation*, ICDT 2025, §3.1); it is *sound*
if `t ≡ t'` implies `⟦t⟧ = ⟦t'⟧`. Extraction picks a term per root;
*one-node-per-class* (DAG) extraction picks one node per class, so every
occurrence of a class becomes the same wire.

**Shared-value terms.** `x ::= in(s) | xor(x, x) | refresh(x) | reg(x) | g(x, x)`
with gadgets `g ∈ {isw, dom, hpc1}`. The value semantics `V` is homomorphic:
`V(in(s)) = s`, `V(xor(x,y)) = V(x) ⊕ V(y)`, `V(g(x,y)) = V(x) ∧ V(y)`,
`V(refresh(x)) = V(reg(x)) = V(x)`. *Lowering* `low(x)` maps a shared-value
term to a wire circuit with two output shares, a fresh random per gadget or
refresh, and identical subterms lowered once.

**Definition (VPLC operator).** A unary operator `ρ` is *value-preserving,
leakage-changing* in model `L` if `V(ρ(x)) = V(x)` for all `x`, and there are
terms `t[x]`, `t[ρ(x)]` (same context) whose lowerings differ in `L`-security.
`refresh` is VPLC in both models; `reg` is VPLC in the glitch-extended model.

---

## 2. Claims

### C1 — Glitch-free safety is a property of the function

*Claim.* In the glitch-free model, whether wire `w` is safe depends only on
`⟦w⟧`. Hence in a sound wire-level e-graph, safety is a label of the e-class.

*Proof.* `O(w) = ⟦w⟧`, and the masking distribution does not depend on the
circuit, so the distribution of `O(w)` is a function of `⟦w⟧` alone. Merged
terms have equal functions by soundness. ∎

*Consequence.* Per-class constrained extraction (`design/0006`) returns a
circuit whose internal wires are all glitch-free safe: every class it
materialises internally is labelled safe. (The prototype exempts output
classes and checks the outputs after extraction.) *Witness:* `test_c1_*` (400 random circuits; equal functions never
disagree), plus the existing labeller tests.

### C2 — Cost-minimal extraction is unsound

*Claim.* There is a glitch-free-secure circuit and a set of sound Boolean
rewrite rules such that the cost-minimal extraction of the saturated e-graph is
insecure.

*Witness (constructive proof).* 2-share ISW AND (8 gates) with comm/assoc,
identities, distributivity and factoring: the cheapest extraction has 7 gates
and the wire `b0 ⊕ b1 = b` (`test_c2_*`; also on egglog,
`experiments/egglog_port`). ∎

In the glitch-extended model, the same happens once registers are treated as
transparent (`reg(x) ≡ x`): registered DOM 10 → 5, chain 20 → 10, both leaking
(`experiments/glitch_probe/RESULTS.md`).

### C3 — Re-sharing is not an equality of wire terms

*Claim.* Refresh and gadget substitution relate share pairs that reconstruct
the same value but whose individual shares compute different functions. No
sound wire-level e-graph can merge those shares.

*Proof.* `refresh` maps `s0` to `s0 ⊕ r`, and `⟦s0 ⊕ r⟧ ≠ ⟦s0⟧`. For ISW and
DOM, the first output shares are `a0b0 ⊕ r` and `a0b0 ⊕ a0b1 ⊕ r`, different
functions, while `c0 ⊕ c1 = a ∧ b` for both. Soundness forbids merging terms
with different functions. ∎ *Witness:* `test_c3_*`.

### C4 — Value equality is a congruence; lowering is correct

*Claim.* (a) If `V(x) = V(x')` and `V(y) = V(y')`, then `V(op(x, y)) = V(op(x', y'))`
for every operator. Hence R1 (Boolean identities on values), R2
(`isw = dom = hpc1`), R3 (`refresh(x) = x`) and register transparency
(`reg(x) = x`) are sound for `V`. (b) For every term, the two output shares of
`low(x)` XOR to `V(x)` for all inputs.

*Proof.* (a) `V` is defined homomorphically, so `V(op(x, y))` is a function of
`V(x)` and `V(y)`. Each rule equates terms with equal `V` by the gadgets'
correctness and `V(ρ(x)) = V(x)`. (b) Induction on `x`: inputs by definition of
shares; share-wise XOR by linearity; refresh because `r` cancels; each gadget
by its correctness (ISW, DOM: standard; HPC1 = DOM after a refresh). ∎

*Author to verify:* the gadget-correctness base cases against the transcribed
structures in `experiments/resharing/gadgets.py`. *Witness:* `test_c4_*`.

*Remark (why the decode kernel is usable here).* Adversarial pass 3 warned
that equality of decoded values alone is too coarse: it identifies a secure
sharing `(x0, x1)` with the insecure `(x, 0)`. That objection applies to a
relation over *all* share pairs. The value layer is the decode kernel
restricted to a masking-closed term language — inputs, share-wise XOR,
refresh, register, gadgets — in which `(x, 0)` has no term, and whose
lowerings are well-formed sharings by C4(b). Security is not encoded in the
equality at all; it is enforced at extraction. C5 is exactly the price of that
choice (`docs/adversarial-search-4.md`, T1).

### C5 — With a VPLC operator, safety is not class-local, and DAG extraction is incomplete

*Claim.* (a) In the value-layer e-graph with R3, `isw(z, z)` and
`isw(z, refresh(z))` are in the same class, yet the first leaks and the second
is secure. (b) For that fixture, every one-node-per-class extraction leaks,
while a secure term exists.

*Proof.* (a) `refresh(z) ≡ z` under R3, so both gadget terms are congruent.
`isw(z, z)` has the internal wire `z0 ∧ z1 = z0 ∧ (z0 ⊕ z)`, whose
distribution depends on `z`; with `refresh(z)` that operand becomes
`z1 ⊕ r`, independent of `z0`. (b) In a DAG extraction both operands of the
gadget are the same class, hence the same wire: either `z` (leaks, as above)
or `refresh(z)`, which is a self-loop in class `z` and therefore cyclic.
The term `isw(z, refresh(z))` chooses differently per occurrence. ∎

*Remark.* With R2 also on, `hpc1(z, z)` is secure and DAG-extractable, because
HPC1 contains its refresh internally. (b) is a statement about the rule set,
not about every rule set.

In the glitch-extended model the same holds for `reg` (registered vs
unregistered DOM, `experiments/glitch_probe`). *Witness:* `test_c5_*` (the
only acyclic DAG extraction is `isw(z, z)`, and it leaks).

### C6 — Glitch-extended safety is not a function of the wire

*Claim.* There are wires with equal functions and different glitch-extended
verdicts. So C1 fails in the glitch model, even with registers opaque:
per-class labelling is unsound there and extraction must be term-based at the
wire level too.

*Proof.* DOM's first output with the cross term registered,
`a0b0 ⊕ reg(a0b1 ⊕ z)`, and without, `a0b0 ⊕ (a0b1 ⊕ z)`, compute the same
function. The stable sets are `{a0, b0, reg(…)}` and `{a0, b0, b1, z}`; the
second contains `b0` and `b1`, whose joint distribution depends on `b`. ∎
*Witness:* `test_c6_*`.

### C7 — A leaking subterm leaks in every context (the extraction cut)

*Claim.* In both models, if the lowering of a subterm has a leaking wire, so
does the lowering of every term containing it.

*Proof.* Lowering is compositional and memoised, so the subterm's circuit
appears unchanged inside the context's circuit, up to a bijective renaming of
fresh randoms. A wire's observation depends only on its own cone (glitch-free:
its function; glitch-extended: its stable set, determined by the cone). The
context adds only variables that are uniform and independent of that
observation, or secrets that it does not depend on, so its distribution per
secret assignment is unchanged. ∎

*Consequence.* Constrained extraction may discard leaking terms for good; its
results are `L`-secure by construction, and it is exact on its k-best
frontier. *Witness:* `test_c7_*` (random contexts, both models).

### C8 — At first order, outputs can be extracted separately

*Claim.* A circuit is `L`-secure iff the cone of each output is.

*Proof.* Every wire lies in the cone of at least one output, and its
observation depends only on its own cone, which is the same in the whole
circuit and in that output's cone. ∎ This fails at higher orders, where a
probe *tuple* can span cones. *Witness:* `test_c8_*`.

### C9 — For PINI-built terms, safety is class-local again

*Claim.* Call an e-class *composable* if it holds a node whose operator is
1-PINI and whose children are composable (inputs are composable). For a term
built only from 1-PINI operators over independent input sharings, the lowered
circuit is first-order probing secure (glitch-free model), whatever its
fan-out. Hence on composable classes safety is a class label, and
one-node-per-class extraction restricted to PINI nodes is sound.

*Proof.* Each operator's lowering is checked 1-PINI exhaustively
(`experiments/composition/pini.py`; share-wise XOR, NOT, refresh and HPC1 pass,
ISW and DOM do not; cross-checked with VerifMSI's PINI mode). A composite of
d-PINI gadgets is d-PINI (Cassiers & Standaert, *Trivially and Efficiently
Composing Masked Gadgets with Probe Isolating Non-Interference*, IEEE TIFS
2020, ePrint 2018/438, Property 12); a d-PINI gadget is d-probing secure when
its input encodings are independent (Property 11). Our primary inputs are
independent sharings; lowering gives each gadget instance fresh randoms; the
terms are acyclic (the paper's backward-induction proof assumes this); and
composition allows a gadget output to feed several later gadgets, so shared
subterms are covered. ∎

*Relation to C5.* C5's obstruction remains for ISW/DOM: a class can hold both
a leaking and a secure term. C9 restores class-locality on the PINI fragment
only, at a cost premium (e.g. ISW chain 18 → 24, `experiments/composition`).
With R2, `square` extracts as `hpc1(z, z)` — the same sharing on both operands
— and is secure. *Witness:* `test_c9_*`.

*Scope.* Glitch-free model only; the glitch-robust variant needs registered
gadgets, which are not modelled. *Author to verify:* the exact statements of
Properties 11 and 12 and their preconditions, against the paper's text.

---

## 3. The result, stated once

**Theorem (informal).** Fix a first-order, 2-share model
`L ∈ {glitch-free, glitch-extended}`.

1. Function-preserving equality saturation with cost-minimal extraction does
   not preserve `L`-security (C2).
2. In the glitch-free model only, safety is a class label and per-class
   constrained extraction is a sound repair (C1).
3. Masking's useful equivalences — refresh, gadget substitution, and in the
   glitch model register placement — are not equalities of wire terms (C3);
   identifying sharings by value makes them a congruence (C4).
4. Any VPLC operator — `refresh`, and `reg` under glitches — places a term and
   its leakage-different variant in one class, so safety is not class-local and
   one-node-per-class extraction can miss every secure circuit (C5, C6).
5. Occurrence-aware term extraction with the monotone leak cut (C7), per output
   (C8), is sound in both models and recovers secure circuits where DAG
   extraction cannot.
6. On the fragment built from PINI gadgets, safety is a class label again
   (C9): ordinary one-node-per-class extraction is sound there, with no
   enumeration, at any circuit size, at the price of costlier gadgets.

## 4. What the paper must not claim

- Gains: there are none over tight constructions (chain, Keccak chi, DOM).
- Novelty of the optimizations (refresh removal, factoring, gadget choice,
  register placement) — known in masking compilers; only the representation and
  the obstruction may be claimed, and only at the confidence in
  `docs/adversarial-search-4.md`.
- That optimizers breaking (glitch-robust) masking is new — known for
  re-timing and LLVM reassociation (pass 3, pass 4).
- That context-dependence in e-graphs is new — contextual equality saturation
  exists (Hou, Laddad, Hellerstein, arXiv 2507.11897).
- Anything about higher orders, more shares, PINI/SNI, transitions, timing, or
  real synthesis tools treating registers as transparent.
- Optimality of extraction: exact only on its k-best frontier.

## 5. Open items before submission

- [ ] Author checks every proof; in particular C4(b) base cases and C7's
      "unchanged up to renaming" step.
- [x] Citation check — `docs/adversarial-search-4.md` (2026-10-18). Outcome:
      PCR citation verified; the glitch *phenomenon* (optimizers moving
      registers break masking) and register placement are **not** claimable;
      T1–T3 survive narrowly at medium confidence. Still open: read eVer's PDF
      directly, AGEMA's register handling, and the extraction papers.
- [ ] Decide whether C5(b) should be stated for all rule sets without
      self-refreshing gadgets, with a proof, or kept as a witnessed instance.
