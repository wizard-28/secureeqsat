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

**E-graphs.** An e-graph over wire terms holds a congruence `≡`; it is *sound*
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

## 4. What the paper must not claim

- Gains: there are none over tight constructions (chain, Keccak chi, DOM).
- Novelty of the optimizations (refresh removal, factoring, gadget choice,
  register placement) — known in masking compilers; only the representation and
  the obstruction are claimed, after the citation check.
- Anything about higher orders, more shares, PINI/SNI, transitions, timing, or
  real synthesis tools treating registers as transparent.
- Optimality of extraction: exact only on its k-best frontier.

## 5. Open items before submission

- [ ] Author checks every proof; in particular C4(b) base cases and C7's
      "unchanged up to renaming" step.
- [ ] Citation check (`.claude/skills/secureeqsat-citation-check`) on: e-graph
      semantics as partial congruence; eVer; register placement in AGEMA-class
      generators; any prior "refresh breaks congruence" statement.
- [ ] Decide whether C5(b) should be stated for all rule sets without
      self-refreshing gadgets, with a proof, or kept as a witnessed instance.
