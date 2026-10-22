# Composition analysis (PINI) — results

**Date:** 2026-10-22 · **ADR:** `design/0019` · **Theory:** claim C9

## Question

Exact checking enumerates every input, so it refuses circuits past `2**26`
points, and claim C5 showed that safety is not a class label once refreshes
share classes with what they refresh. Can a **composition notion** make safety
a class label again, so ordinary one-node-per-class extraction is sound
without enumeration — and how far does that scale, at what cost?

## Method

- `pini.py` — exhaustive first-order PINI check of each operator's lowering
  (Cassiers & Standaert, Def. 12): every internal probe must be simulatable
  from the input shares of at most one index, and output share *i* from
  index *i* only.
- `pini_driver.py` — the same question to VerifMSI's own PINI mode
  (`checkSecurity(1, False, 'pini')`, real shares), as an independent check.
- `analysis.py` — a class is *composable* if it holds a node whose operator
  passed the PINI check and whose children are composable; computed as a least
  fixed point on the saturated, exported e-graph. Extraction then picks one
  node per class among PINI nodes. Security of the result follows from PINI
  composition (Property 12) and PINI + independent inputs ⇒ probing security
  (Property 11), verified in `docs/adversarial-search-5.md`.
- `tps_driver.py` — VerifMSI's symbolic `checkTpsVal` per wire: a sound,
  enumeration-free certificate used to check large circuits independently.
- `run_composition.py` — four sections: gadget verdicts, fixtures, random
  soundness, scale. Cost = gates + random bits.

## Results

### Which gadgets are 1-PINI

| Operator | Ours | VerifMSI |
|---|---|---|
| share-wise XOR, NOT, refresh | PINI | PINI |
| HPC1 (DOM with a refreshed operand) | PINI | PINI |
| ISW, DOM | **not** PINI (`x0 ∧ y1` needs both share indices) | not PINI |

### Composable vs exact extraction on the fixtures

| Fixture | Rules | Composable | Exact optimum |
|---|---|---:|---:|
| ISW chain | R2 / all | 24 | 18 |
| over-refreshed chain | R2 / all | 36 / 24 | 30 / 18 |
| `isw(z, refresh(z))` | R2 / all | 17 / **14** | 14 |
| `a∧b ⊕ a∧d` | R2 / all | 26 / 14 | 20 / 11 |
| HPC1 chain | R2 / all | 24 | 18 |
| Keccak χ 3-bit / 5-bit | R2 / all | 45 / 75 | 36 / 60 |

Every composable result is secure under the exact checker. The price of
composability is the costlier gadget (HPC1 12 vs ISW 9): up to +33 % here, and
nothing on `square` with all rules.
With all rules, `square` extracts as `hpc1(z, z)` — the same sharing on both
operands — and is secure at the exact optimum (14).

Composable extraction takes under 1 ms on every fixture; exact term extraction
takes up to 0.5 s (χ 5-bit, all rules).

### Soundness

234 random terms built only from PINI operators (with fan-out), checked by the
exact checker: **0 leaking**.

### Scale

Start: ISW gadgets, rewritten with R2 only, composable extraction.

| Circuit | Cost | Space | Exact checker | Composition | VerifMSI (symbolic) |
|---|---:|---:|---|---|---|
| Keccak χ, 3-bit row | 45 | 2^12 | secure | secure | 52/52 wires certified |
| Keccak χ, 6-bit row | 90 | 2^24 | secure | secure | 103/103 |
| Keccak χ, 8-bit row | 120 | 2^32 | **refused** | secure | 137/137 |
| Keccak χ, 16-bit row | 240 | 2^64 | refused | secure | 273/273 |
| Keccak χ, 32-bit row | 480 | 2^128 | refused | secure | 545/545 |
| ISW chain, depth 10 | 120 | 2^42 | refused | secure | 142/142 |
| ISW chain, depth 15 | 180 | 2^62 | refused | secure | 212/212 |

Composition decides each in ≤ 0.03 s. The VerifMSI certificate is not
vacuous: it fails to certify the leaking `isw(z, z)` (test).

## What this does and does not show

**Shows:**

- On the PINI fragment, safety is a class label again and plain DAG
  extraction is sound, with no enumeration (claim C9) — at sizes the exact
  checkers cannot touch, independently certified by VerifMSI.
- The gadget verdicts the analysis relies on are checked, not assumed, and
  agree with VerifMSI.

**Does not show:**

- **Gains.** Composable circuits cost more than exact optima; nothing here
  beats a tight construction.
- **The glitch-extended model.** PINI in the glitch model needs registered
  gadgets (glitch-robust PINI); not modelled.
- **Novelty of PINI or of composition-aware masking compilation**
  (`docs/adversarial-search-5.md`).
- **Completeness.** ISW/DOM circuits that are secure are not composable; the
  analysis needs R2 to swap them for HPC1.

## Known limitations

- The analysis runs in Python on the exported e-graph, not as an egglog
  analysis inside saturation.
- Scale stops at chain depth 15 and χ on 32 bits because the test-harness
  `Circuit` names wires by their full expression, and those names grow too
  fast — a harness limit, not one of the analysis.
- On these fixtures every class is composable after R2, so the analysis is not
  yet tested on e-graphs where it must reject classes, beyond `square` without
  R2 (test).
- One exact soundness check per random term; the theorem's preconditions
  (independent inputs, acyclic terms, fresh randoms per gadget) hold by
  construction of the lowering.

## Reproduce

```bash
uv run pytest -q experiments/composition
uv run python experiments/composition/run_composition.py   # ~10 s with VerifMSI
```

Mutation checks: allowing an internal probe both share indices (7 failures),
trusting ISW as PINI in the analysis (3), dropping the output-share condition
(1).

## Raw output

`PYTHONHASHSEED=0 uv run python experiments/composition/run_composition.py`:

```
== 1. which gadgets are 1-PINI
  xor      ours: PINI      VerifMSI: PINI      agree
  not      ours: PINI      VerifMSI: PINI      agree
  refresh  ours: PINI      VerifMSI: PINI      agree
  isw      ours: not PINI  VerifMSI: not PINI  agree
  dom      ours: not PINI  VerifMSI: not PINI  agree
  hpc1     ours: PINI      VerifMSI: PINI      agree
  operators used by the analysis: ['hpc1', 'not', 'out', 'refresh', 'xor']

== 2. composable vs exact term extraction (cost = gates + randoms)
  chain          R2        composable:  24 secure (0.0 ms)  exact:  18 (0.00 s)  composable classes 100%
  chain          R1+R2+R3  composable:  24 secure (0.1 ms)  exact:  18 (0.00 s)  composable classes 100%
  overrefreshed  R2        composable:  36 secure (0.0 ms)  exact:  30 (0.00 s)  composable classes 100%
  overrefreshed  R1+R2+R3  composable:  24 secure (0.0 ms)  exact:  18 (0.00 s)  composable classes 100%
  square         R2        composable:  17 secure (0.0 ms)  exact:  14 (0.00 s)  composable classes 100%
  square         R1+R2+R3  composable:  14 secure (0.2 ms)  exact:  14 (0.11 s)  composable classes 100%
  factor         R2        composable:  26 secure (0.0 ms)  exact:  20 (0.00 s)  composable classes 100%
  factor         R1+R2+R3  composable:  14 secure (0.1 ms)  exact:  11 (0.02 s)  composable classes 100%
  hpc_chain      R2        composable:  24 secure (0.0 ms)  exact:  18 (0.00 s)  composable classes 100%
  hpc_chain      R1+R2+R3  composable:  24 secure (0.0 ms)  exact:  18 (0.01 s)  composable classes 100%
  chi3           R2        composable:  45 secure (0.1 ms)  exact:  36 (0.01 s)  composable classes 100%
  chi3           R1+R2+R3  composable:  45 secure (0.2 ms)  exact:  36 (0.06 s)  composable classes 100%
  chi5           R2        composable:  75 secure (0.1 ms)  exact:  60 (0.11 s)  composable classes 100%
  chi5           R1+R2+R3  composable:  75 secure (0.3 ms)  exact:  60 (0.54 s)  composable classes 100%

== 3. soundness: random PINI-only terms, exact checker verdict
  234 terms checked exactly, 0 leaking (must be 0)

== 4. scale: composable extraction where the exact checkers refuse
  start (ISW gadgets), rewritten with R2; exact range is 2**26 points
  Keccak chi, 3-bit row    cost    45  space 2**12   exact: secure   composition: secure (0.00 s)  VerifMSI certifies 52/52 wires
  Keccak chi, 5-bit row    cost    75  space 2**20   exact: secure   composition: secure (0.01 s)  VerifMSI certifies 86/86 wires
  Keccak chi, 6-bit row    cost    90  space 2**24   exact: secure   composition: secure (0.01 s)  VerifMSI certifies 103/103 wires
  Keccak chi, 8-bit row    cost   120  space 2**32   exact: refused  composition: secure (0.01 s)  VerifMSI certifies 137/137 wires
  Keccak chi, 12-bit row   cost   180  space 2**48   exact: refused  composition: secure (0.01 s)  VerifMSI certifies 205/205 wires
  Keccak chi, 16-bit row   cost   240  space 2**64   exact: refused  composition: secure (0.01 s)  VerifMSI certifies 273/273 wires
  Keccak chi, 24-bit row   cost   360  space 2**96   exact: refused  composition: secure (0.02 s)  VerifMSI certifies 409/409 wires
  Keccak chi, 32-bit row   cost   480  space 2**128  exact: refused  composition: secure (0.03 s)  VerifMSI certifies 545/545 wires
  ISW chain, depth 2       cost    24  space 2**10   exact: secure   composition: secure (0.00 s)  VerifMSI certifies 30/30 wires
  ISW chain, depth 5       cost    60  space 2**22   exact: secure   composition: secure (0.00 s)  VerifMSI certifies 72/72 wires
  ISW chain, depth 10      cost   120  space 2**42   exact: refused  composition: secure (0.00 s)  VerifMSI certifies 142/142 wires
  ISW chain, depth 15      cost   180  space 2**62   exact: refused  composition: secure (0.01 s)  VerifMSI certifies 212/212 wires
```
