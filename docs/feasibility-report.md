# Feasibility Report — SecureEqSat

**Date:** 2026-10-06
**Last revised:** 2026-10-07 — §6 and §7 corrected after adversarial pass 3. The
"cannot express" claim was too strong and partly a rediscovery, and the novelty
claims were narrowed. See `design/0011` and `docs/adversarial-search-3.md`.
**Scope:** every feasibility check we could run before Review 1, including the
trust boundary, the premise, the constrained-extraction mechanism, the payoff
hypothesis, and scalability.
**Status:** mechanically feasible and novel; **the optimization payoff is
currently unsupported**. Details and the proposed reframe below.

---

## Verdict in one table

| # | Check | Result | Confidence |
|---|---|---|---|
| 1 | **Trust boundary**: is the in-house checker independently corroborated? | ✅ **Closed.** Agrees with VerifMSI on every wire of 1,216 circuits / 21,760 wires, zero violations | **High** |
| 2 | **Premise**: does unconstrained EqSat yield cheaper-but-insecure circuits? | ✅ **Confirmed on two independent engines**, leaking on the *same* wires | **High** |
| 3 | **Mechanism**: can security-constrained extraction be implemented? | ✅ **Works.** Recovers a secure circuit from the insecure optimum | **High** |
| 4 | **Payoff**: does the constraint leave optimization room? | ⚠️ **Not demonstrated.** Gadget scale: no gain. Chain scale: the entire sampled cheap frontier is insecure | **Medium-high** (negative) |
| 5 | **Scalability**: does the search survive realistic circuits? | ✅ With `egglog`: instant. The in-house blowup was an engine artifact | **High** |
| 6 | **Abstraction level**: are the valuable optimizations expressible? | ⚠️ **Probably not as Boolean equalities.** See §6 | **Medium** |

**Bottom line:** the project can be done, and most of it already is. What is
*not* yet supported is the original headline — that this finds cheaper secure
circuits. The evidence points the other way at the scales we can currently
handle, and §6 explains why. `design/0010` reframes the project around what the
evidence actually supports.

---

## 1. Trust boundary — closed

The single largest scientific risk was an in-house checker that agrees only with
itself. It is now cross-validated against **VerifMSI** (SECRYPT 2023), an
independent implementation of the same property, run as an external process
outside this repo (GPLv3, per `AGENTS.md` §6.4).

Protocol, per wire, over *both* of VerifMSI's relevant functions:

| Rule | Statement | Result |
|---|---|---|
| 1 (two-sided) | our verdict == VerifMSI exact `independent` | **0 violations in 21,760 wires** |
| 2 (internal) | `tps=True` ⇒ exact `independent=True` | 0 violations |
| 3 (one-sided) | `tps=True` ⇒ our verdict is safe | 0 violations |
| info | `tps=False` while exact says independent | 72 counted (VerifMSI conservatism) |

Two traps were found by *characterising* the oracle rather than trusting it:

1. `checkTpsVal` returns a 3-tuple `(res, usedBitExp, time)`; the README's
   `if res:` idiom is silently always-true.
2. `checkTpsVal` is a **sound but incomplete certificate**, not the exact
   property. Comparing against it alone would have produced ~72 phantom
   "disagreements" — and the tempting "fix" would have been to weaken our
   checker. The exact function is `getDistribWithExev(e)[1]`.

The cross-check sits on the secure/insecure boundary by construction: 24 ISW
variants that compute the **same Boolean function** while left-folding the c1
summands in different orders split **10 secure / 14 insecure**, and both tools
agree on every wire of all 24.

Details: `experiments/oracle_crosscheck/RESULTS.md`.

## 2. Premise — confirmed on two engines

Unconstrained equality saturation plus cost-minimal extraction turns a secure
ISW masked AND into a functionally equivalent but probing-insecure circuit, and
the insecure circuit is **cheaper** — so the failure is systematic, not a corner
case. The enabling rule is distributivity run backwards, refolding shares:

```
a1&b0 ^ a1&b1   ->   a1 & (b0 ^ b1)
```

egglog's extracted `c1` is literally `r ^ a0&b1 ^ a1&(b0^b1)`: 7 gates instead
of 8, with the **unmasked secret `b`** materialised as an internal wire.

The minimal engine and egglog agree on the verdicts *and on the offending
wires*. Details: `experiments/premise_test/RESULTS.md`,
`experiments/egglog_port/RESULTS.md`.

## 3. Mechanism — security-constrained extraction works

Implemented per `design/0006`:

- **Safety labelling of e-classes.** First-order safety is a property of the
  Boolean function a class represents, so it is a per-class label. Computed by
  materialising a representative and asking the checker. On the ISW e-graph,
  19/25 classes are safe; the unsafe ones include `(b0 ^ b1)` and
  `(b1 and (a1 ^ a0))`.
- **Constrained extraction.** Cost fixed point in which a class may be
  materialised internally only if it is safe; roots (outputs) are exempt.
- **Result:** unconstrained 7 gates INSECURE → constrained **8 gates SECURE**,
  functionally equivalent to ISW. **Price of security: 1 gate.**

So the mechanism is implementable, fast at this scale, and correct.

## 4. Payoff — not demonstrated

**Gadget scale:** the constrained optimum is 8 gates, i.e. **exactly the known
ISW construction**. The constraint costs a gate and buys nothing.

**Chain scale (two ISW gadgets, 16 gates hand-written):**
- unconstrained optimum: **14 gates, INSECURE** (4 leaking wires);
- the k-best extraction frontier (k = 40, 240 pairs tested) contained
  **no secure extraction at all** (28 pairs cost fewer than 16 gates, 58 exactly 16, 154 more).

Every sampled cheap extraction is insecure. The secure circuits exist — the
hand-written chain is one, and core-rules extraction finds a secure 16-gate form
— but they sit far down the cost ranking.

**Interpretation.** Gate savings and probing security are *anti-correlated* in
the space this rule set explores. The cheap direction is the insecure direction.

**Caveat.** The k-best frontier is sampled, not an exact optimum. This bounds
what enumeration finds, not what exists. It is also, incidentally, a result
about `design/0006`: enumeration cannot substitute for the CEGIS/separation
loop, because the secure frontier is not near the cheap frontier.

## 5. Scalability — an engineering problem, and it is solved

| Engine | Chain + full rules |
|---|---|
| in-house minimal harness | 3,000-class cap in 2 iterations, 62.5 s, still growing |
| `egglog` 14.0.0 | `run(4)` in **< 0.01 s**, 90 AND / 666 XOR nodes |

The blowup that looked like a rule-set problem was an artifact of an
unoptimised harness with an O(n) rebuild. `design/0004`'s plan to move to
`egglog` is validated. (Engine plumbing needed care: egglog hoists shared
subterms into `_B_n = …` bindings and prints multi-line statements, so the
parser splits statements with `ast`.)

## 6. The finding that matters most: the abstraction level

The gate savings in the chain come from the **same refolding mechanism** as the
ISW attack. Refolding is a Boolean equality. But the optimizations the masking
literature actually exploits — **refresh insertion/removal, randomness reuse,
gadget substitution** (Tornado, AGEMA, COMPRESS, Feldtkeller et al.) — are *not*
Boolean equalities. They are **equivalences up to re-sharing**: the output
shares are re-randomised, so the function of each individual wire changes while
the shared value does not.

**An e-graph's equality is a congruence**: if `x = y`, then `f(x) = f(y)` for
every context (Suciu, Wang, Zhang, *Semantic Foundations of Equality
Saturation*, ICDT 2025). **Re-sharing is not a congruence** of the wire-term
algebra — `x0` and `x0 ^ r` are different functions, and that difference
survives ordinary contexts. A guard controls *when an equality fires*; it cannot
turn a non-equality into an equality. So re-sharing **cannot be the equality
relation** of a plain e-graph over wires. This is a representation problem, not
a missing feature.

Plain equality saturation therefore:

- cannot make the valuable transformations into equalities, and
- **actively prefers** the one refactoring it *can* express (refolding), which
  is exactly the insecure one.

This is a coherent explanation of the negative payoff results, and it is a
sharper research question than the original pitch:

> **What representation can carry re-sharing while keeping extraction
> security-aware?**

**Two corrections to this section, both load-bearing** (full record in
`docs/adversarial-search-3.md`, `design/0011`):

1. It originally said EqSat **cannot express** re-sharing rewrites. That is
   **false**: `egg` has conditional and dynamic appliers, and `egglog` rules
   carry `:when` guards — all verified in the APIs. The defensible claim is the
   congruence argument above.
2. "Equivalence up to re-sharing" is **standard masking semantics**, not our
   observation: ISW relies on it, SNI states refresh preserves functional
   behaviour, tightPROVE's `Flatten` replaces gadget outputs with fresh sharings
   as a reduction step, and RNI-f / COMAR are entire research lines. What is
   ours is only the consequence for e-graph search.

Also note the three optimizations are **not one relation** — refresh is about
shares, randomness reuse about the dependency structure, gadget substitution
about composability — and "same decoded value" is too coarse, since it would
identify a secure `(x0, x1)` with the insecure `(x, 0)`. A usable relation must
be **finer than the decode kernel** and security-aware.

## 7. What this means for the project

**Mechanically feasible: strongly yes.** The checker is trustworthy, the premise
is reproducible on two engines, constrained extraction works, and the search
scales on a real engine. Almost none of this needs to be built from scratch.

**Novelty: narrow but intact** (corrected 2026-10-07). *Constrained* e-graph
extraction already exists — acyclic constraints (EGRAPHS 2023), resource
constraints (SkeleShare, CGO 2026) — so our claim is narrower: the first
extraction constrained by a **semantic hyperproperty** (probing security).
Likewise **eVer** (2026) already optimizes refresh sequences, and **MaskedHLS**
(TCAD 2024) already showed a conventional optimizer producing an unmasked
circuit — so the soundness claim is the **EqSat instantiation plus the
systematicity argument** (the insecure representative wins *on cost*), not the
phenomenon itself. Neither the congruence obstruction nor a re-sharing-aware
formulation is claimed by anyone we found. `docs/adversarial-search-3.md`,
`design/0011`.

**The original headline — "we find cheaper secure masked circuits" — is not
supported** and, per §6, we now have a principled reason to expect it is hard at
this abstraction level. Continuing to pitch it would be a mistake.

`design/0010` reframes the project to lead with what the evidence supports:
**the soundness of equality-saturation-based optimization of masked circuits,
the exact checker and constrained extraction that repair it, and the
re-sharing gap that explains where the payoff must come from.**

## 8. Confidence

| Claim | Confidence | Basis |
|---|---|---|
| The in-house checker is correct on first-order, 2-share, glitch-free circuits | **high** | 21,760 wires, two independent implementations, boundary-straddling family |
| Unconstrained Boolean EqSat is unsound for masked-circuit optimization, with a concrete mechanism | **high** | Reproduced on two engines with identical leaking wires |
| Security-constrained extraction is implementable and correct | **high** | Working prototype, verified output |
| The constraint yields no gain at gadget scale | **high** | Constrained optimum == known construction |
| The cheap frontier is insecure at chain scale | **medium-high** | none of 240 sampled extractions secure (28 cheaper than 16 gates); sampled, not exhaustive |
| Re-sharing is **not a congruence**, so it cannot be an e-graph's equality relation | **high** | Follows from the definition of congruence plus PCR semantics (ICDT 2025); guarded/dynamic rewrites verified not to repair it |
| The abstraction-level explanation in §6 | **medium** | Coherent and consistent with the negative results; not yet demonstrated constructively |
| A re-sharing-aware formulation is achievable | **speculative** | Not attempted; it is the proposed next research step |

**No claim here is certain.** The negative results are negative results about
what the current rule set and abstraction level achieve — not proofs that no
useful optimization exists.

## 9. Reproduce everything

```bash
uv sync

# 1-2. premise, in-house
uv run python experiments/premise_test/run.py
uv run pytest -q

# 1. trust boundary (needs the external oracle)
bash experiments/oracle_crosscheck/setup_oracles.sh
uv run python experiments/oracle_crosscheck/crosscheck.py --random 20
uv run python experiments/oracle_crosscheck/crosscheck.py --seed 1 --random 300 \
    --random-randoms 3 --random-gates 10

# 3. constrained extraction
uv run python experiments/constrained_extraction/run_constrained.py

# 2, 4, 5. real engine
uv run python experiments/egglog_port/port.py --circuit isw   --rules full --iters 3
uv run python experiments/egglog_port/port.py --circuit chain --rules full --iters 4
uv run python experiments/egglog_port/kbest.py --rules full --k 40
```
