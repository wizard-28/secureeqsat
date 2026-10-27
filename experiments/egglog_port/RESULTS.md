# egglog port results

Two questions:

- `design/0004` — re-confirm the premise on a **real** e-graph engine, not only
  the minimal in-house harness.
- `design/0009` — is the two-gadget chain blowup an unoptimised-engine artifact
  or a property of the rule set?

Reproduce:

```bash
uv run python experiments/egglog_port/port.py --circuit isw   --rules full --iters 3
uv run python experiments/egglog_port/port.py --circuit chain --rules core --iters 5
uv run python experiments/egglog_port/port.py --circuit chain --rules full --iters 4
uv run python experiments/egglog_port/kbest.py --rules full --k 40
```

## 1. Premise re-confirmed on egglog (`design/0004` satisfied)

| Circuit | Rules | In-house harness | egglog | Agreement |
|---|---|---|---|---|
| ISW AND | core | 8 gates, SECURE | 8 gates, SECURE | ✅ |
| ISW AND | full | 7 gates, INSECURE | 7 gates, INSECURE | ✅ |
| Chain (2 gadgets) | core | 16 gates, SECURE | 16 gates, SECURE | ✅ |

For the full-rules ISW case both engines leak on the **same wires**:
`xor(b0,b1)` — the unmasked secret `b` — and `and(a1, xor(b0,b1))`.
egglog's extracted `c1` is literally
`r ^ (a0 & b1) ^ (a1 & (b0 ^ b1))`, i.e. it refolds `a1&b0 ^ a1&b1` into
`a1 & (b0 ^ b1)`, materialising the secret in place of two gates.

## 2. Chain blowup was an engine artifact (`design/0009` answered)

| Engine | Rule set | Chain result |
|---|---|---|
| in-house minimal | full | **3,000-class cap hit in 2 iterations, 62.5 s**, still growing |
| egglog 14.0.0 | full | `run(4)` in **< 0.01 s**; 90 AND nodes, 666 XOR nodes |

So the search space is entirely tractable with a real engine, and the
scalability path is **engineering, not research**. `design/0004`'s plan to move
to `egglog` is validated. (egglog also needed care: the printed extraction
hoists shared subterms into `_B_n = ...` bindings and can span multiple lines,
so the parser splits statements with `ast`, not by newline. Structural
hash-consing in our `Circuit` turns the sharing into correct DAG gate counts.)

## 3. The payoff question — negative at both scales

**Chain, full rules:** unconstrained optimum is **14 gates, INSECURE**
(4 leaking wires), versus the hand-written composition at **16 gates, SECURE**.

**Does any extraction secure the chain for fewer than 16 gates?**
`extract_multiple` was used to enumerate the k-best extraction frontier
(k = 40; 6 variants for `u0`, 40 for `u1`; 240 pairs tested):

```
cheapest extraction overall : 14 gates, INSECURE
cheapest SECURE extraction  : none found in the k-best frontier
```

**Every** sampled extraction is insecure (cost distribution: 28 pairs below 16 gates, 58 at 16, 154 above; 0 secure). The secure circuits do exist —
the hand-written chain is one, and the core-rules run extracts a secure 16-gate
form — but they lie outside the cheap frontier.

Caveat: this is a *sampled* frontier, not an exact constrained optimum (see
`results` §4). It bounds what enumeration finds, not what exists.

## 4. Why this matters for `design/0006`

The design proposed a lazy verify-and-refine (CEGIS) loop with the checker as a
separation oracle. This run shows why **enumeration cannot substitute for it**:
the secure extractions sit far down the cost ranking, so a k-best frontier is
almost entirely insecure. Constrained extraction must be *search-directed*
(safety-aware extraction or blocking constraints), exactly as `design/0006`
specifies — cheap-and-insecure is a deep basin, not a marginal edge case.

## What this establishes

- ✅ Real engine reproduces the in-house result exactly (`design/0004` closed).
- ✅ Scalability is an engineering problem, solved by using `egglog`
  (`design/0009` closed).
- ⚠️ **No evidence of payoff**: at gadget scale the safe optimum equals the known
  construction; at chain scale the cheap frontier is entirely insecure.
- ⚠️ The cheap directions are the *insecure* directions. The gate savings come
  from refolding shares, which is precisely what probing security forbids.

## Limitations

- Chain scale is still small (2 gadgets, 2 shares, first order, glitch-free).
- The k-best frontier is sampled, not exhaustive; no claim is made that no
  secure < 16 circuit exists.
- egglog extraction is tree-cost by default, while gate counts here are DAG
  counts via structural hash-consing; the two cost models differ, which is a
  known caveat for comparing extraction quality across engines.
- Rule set is limited to Boolean identities plus distributivity/factoring.
  Gadget-level rewrites (`design/0006` classes R2/R3) are **not** implemented.
