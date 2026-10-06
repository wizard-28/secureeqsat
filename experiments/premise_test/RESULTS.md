# Premise Test Results

**Question:** does unrestricted Boolean equality saturation + cost-minimal
extraction actually turn a secure masked circuit into a functionally
equivalent but probing-insecure one?

**Answer: YES, and the insecure circuit is *cheaper* than the secure one —
so the failure is systematic, not a corner case.**

Reproduce under the project venv (uv-managed, Python 3.14):

```
uv run python experiments/premise_test/run.py   # full narrative run
uv run pytest -q                                # 7 regression tests
```

No third-party runtime dependencies; `pytest` and `ruff` are dev-only.

## Step 1 — checker validation

| Fixture | Expected | Checker verdict |
|---|---|---|
| Masked buffer `(a0^r, a1^r)` | secure | SECURE |
| ISW masked AND (correct construction) | secure | SECURE |
| Naive masking via unmasked intermediate `t=(a0^a1)&(b0^b1)` | insecure | INSECURE — flags `xor(a0,a1)`, `xor(b0,b1)`, `and(xor(a0,a1),xor(b0,b1))` |

The checker is a first-order probing checker for 2-share straight-line
circuits: it enumerates all free-uniform assignments for each secret
assignment and compares each wire's value **distribution** (number of 1s over
the sample space) across secrets. Validated against the known-secure ISW
construction and a deliberately broken circuit.

**The checker caught a genuine bug in a hand-written fixture.** The first
version of the "ISW" circuit built the c1 chain as
`(a0&b1 ^ a1&b0) ^ (a1&b1) ^ r` — the same final function, but the
intermediate `a0&b1 ^ a1&b0 = a0*b ^ a*b0` leaks (its distribution is
constant 0 when `a=b=0` and uniform otherwise). ISW is secure only because
`r` is folded into every c1-chain intermediate:
`(((r ^ a0&b1) ^ a1&b0) ^ a1&b1)`. This is direct evidence the security
property is structure- and order-sensitive, and that the checker is doing
real work rather than rubber-stamping.

## Step 2 — unconstrained equality saturation of secure ISW AND

| Ruleset | Result | AND | XOR | Gates | Functionally equiv. | Security |
|---|---|---:|---:|---:|---|---|
| Core only (comm/assoc/identity/involution/idempotence/annihilator) | 23 classes | 4 | 4 | 8 | yes | **SECURE** |
| Full (+ distributivity + factoring) | 25 classes | 3 | 4 | **7** | yes | **INSECURE** |

With the full ruleset, saturation derives the factored form and the
cost-minimal extraction picks it:

- extracted unsafe wires: `xor(b1,b0)` — this is the **unmasked secret b** —
  and `and(a1, xor(b1,b0))`, which depends on `b`.
- the extracted circuit is **1 gate cheaper** (7 vs 8) than the secure ISW
  circuit and functionally identical (verified exhaustively over all 32 input
  assignments).

The culprit is the factoring rule
`(x&y) ^ (x&z) -> x&(y^z)` (equivalently distributivity run backwards): it
refolds shares and materializes the unmasked secret, and because refolding
reduces gate count, a cost-only extractor prefers it.

## What this establishes

1. The premise of the SecureEqSat project is **valid**: equality saturation
   with ordinary Boolean identities does introduce probing-insecurity, and
   cost-minimal extraction selects it.
2. The failure is **systematic**: the insecure circuit is strictly cheaper,
   so the extractor is biased toward it whenever the rule set permits
   refactoring.
3. **Distributivity/factoring is the specific enabling rule**; core
   algebraic rules alone left the circuit secure on this fixture.
4. A first-order checker is implementable at gadget scale with no
   dependencies, and is sensitive enough to find real ordering bugs.

These claims are locked in as automated tests in `test_premise.py`:

| Test | What it pins down |
|---|---|
| `test_checker_accepts_secure_masked_buffer` | secure fixture classified correctly |
| `test_checker_treats_permuted_uniform_wire_as_safe` | distribution vs. sequence regression |
| `test_checker_accepts_isw_and` | ISW classified secure |
| `test_checker_rejects_unmasked_intermediate` | unmasked secret wire names flagged |
| `test_isw_security_depends_on_folding_random_early` | the ordering-sensitivity finding |
| `test_core_rules_keep_extraction_secure` | core rules alone do not break security |
| `test_unrestricted_rules_produce_cheaper_insecure_circuit` | **the premise** |

## Limitations / next steps

- The checker has so far been validated against **internal** fixtures only.
  The next required step is cross-validation against an independent tool
  (VerifMSI or tightPROVE) on the same fixtures — this is the project's
  trust boundary and must be closed before any security claim.
- The e-graph and extractor here are minimal (tree-cost fixed point, no
  scheduler, no limits beyond simple caps). Conclusion should be re-confirmed
  with `egglog`/`egg` before being treated as a systems result.
- First order, 2 shares, straight-line, glitch-free only. Higher-order and
  robust-probing behavior is untested.
- One gadget only (ISW AND). The result needs to be reproduced across the
  MaskedVerifBench gadget set.

## Raw output

```
STEP 1 - validate the first-order checker on known fixtures
  masked buffer (a0^r, a1^r):        SECURE
  ISW masked AND:                    SECURE
  naive unmasked-intermediate AND:   INSECURE (3 unsafe wires)
    unsafe: ['xor(a0,a1)', 'xor(b0,b1)', 'and(xor(a0,a1),xor(b0,b1))']

STEP 2 - unconstrained equality saturation of ISW AND
[core rules (no distributivity/factoring)]
  saturation: 3 iters, saturated=True, hit_limit=False, 0.00s
  e-graph: 23 classes, 67 nodes
  extracted: 4 AND, 4 XOR, 8 gates total
  functionally equivalent to ISW AND: True
  security: SECURE

[full rules (with distributivity/factoring)]
  saturation: 3 iters, saturated=True, hit_limit=False, 0.00s
  e-graph: 25 classes, 75 nodes
  extracted: 3 AND, 4 XOR, 7 gates total
  functionally equivalent to ISW AND: True
  security: INSECURE (2 unsafe wires)
    - xor(b1,b0)
    - and(a1,xor(b1,b0))

VERDICT
  PREMISE HOLDS: unconstrained rewriting produced a functionally equivalent
  but INSECURE circuit.
```
