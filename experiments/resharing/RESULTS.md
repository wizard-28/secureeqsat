# Shared-value layer: re-sharing rules and gadget equivalences — results

**Date:** 2026-10-11 · **ADR:** `design/0016`

## Questions

Refresh insertion/removal (R3) and gadget substitution (R2) are equivalences
*up to re-sharing*: they keep the reconstructed value and change the shares, so
the wire-level e-graph cannot express them (`design/0010`, `0011`). If the
e-graph works one layer up, on sharings identified by their value, (1) do R2
and R3 become ordinary rules, (2) does the security constraint still matter,
and (3) do any of the rule classes give a secure circuit cheaper than the
hand-written one? (4) *Follow-up, same day:* does anything improve when the
start is a **tight** construction rather than one with deliberate slack?

## Method

- `gadgets.py` — shared-value terms and their **lowering** to 2-share wire
  circuits: share-wise XOR, `refresh` (`x_i ^ r`), ISW and DOM (transcribed
  from `masked.py`, already cross-checked) and HPC1 (DOM with the second
  operand refreshed). A fresh random per gadget instance; identical subterms
  are lowered once.
- `layer.py` — egglog sort `S`; rule classes R1 (XOR comm/assoc; per gadget
  comm, assoc, distributivity over XOR and factoring), R2
  (`isw = dom = hpc1`), R3 (`refresh(x) = x`, seeded at gadget inputs).
  Saturated for 6 iterations, then read back with `_serialize`.
- `extract.py` — term-based, occurrence-aware k-best extraction (k = 8). A
  term's cost is that of its lowered circuit: **gates + randoms**, one each.
  *Constrained* admits a term only if no wire of its lowered circuit leaks
  (bitsliced labeller, `design/0015`); leaking subterms are cut, which is sound
  because a leaking wire leaks in any context. *Unconstrained* admits all.
- Fixtures (`fixtures.py`): the two-gadget ISW **chain** (control); the same
  chain **over-refreshed** on every gadget input; **square** `isw(z, refresh(z))`
  with `z = a ^ b`; **factor** `a&b ^ a&d`; the chain built from **HPC1**.
- Tight starts (`fixtures.TIGHT`): Keccak's **chi** on a 3-bit and a 5-bit
  row (FIPS 202 sec. 3.2.4: `A'[x] = A[x] ^ ((A[x+1] ^ 1) & A[x+2])`, fetched
  2026-10-11), masked directly — share-wise NOT (`x0 ^ 1`), one ISW gadget per
  output bit, share-wise XOR. R1 additionally has NOT involution and
  `g(~x, y) = y ^ g(x, y)`. Several outputs are bundled into one root with a
  gate-free `out` node.
- Every fixture and every circuit reported below was lowered and cross-checked
  against VerifMSI's exact independence check (RULE 1/1b of
  `oracle_crosscheck`).

## Results

### Ablation — cheapest term, cost = gates + randoms

`U` unconstrained, `C` constrained; **L** = the lowered circuit leaks. Where U
and C agree one number is shown.

| Fixture (start) | none | R1 | R2 | R3 | R1+R2 | R1+R3 | R2+R3 | all |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| chain (18) | 18 | 18 | 18 | 18 | 18 | 18 | 18 | 18 |
| overrefreshed (30) | 30 | 30 | 30 | **18** | 30 | **18** | **18** | **18** |
| square (14) | 14 | 14 | 14 | U 11 **L** / C 14 | 14 | U 11 **L** / C 14 | U 11 **L** / C 14 | U 11 **L** / C 14 |
| factor (20) | 20 | **11** | 20 | 20 | **11** | **11** | 20 | **11** |
| hpc_chain (24) | 24 | 24 | **18** | 24 | **18** | 24 | **18** | **18** |

Gate/random split of the results: 18 = 16 gates + 2 randoms; 30 = 24 + 6;
14 = 12 + 2; 11 = 10 + 1; 20 = 18 + 2; 24 = 20 + 4.

- **chain:** no gain under any rule class. Gadget swaps cost the same, and the
  only other saving, reusing one random across both gadgets, leaks (measured
  earlier on all four ISW/DOM combinations).
- **overrefreshed:** R3 removes all four refreshes (30 → 18), and every removal
  is secure. R1 and R2 alone do nothing.
- **square:** whenever R3 is on, unconstrained extraction drops the refresh and
  lowers `isw(z, z)` — cheaper (11) and **leaking** (the cross products `z0 & z1`).
  Constrained extraction keeps the refresh (14). This is the premise result again,
  one layer up: the cost-optimal choice is the insecure one.
- **factor:** value-level factoring turns two gadgets into one (20 → 11) and
  the result is **secure**. The same rule leaks at the wire level (premise test),
  because there it refolds shares; here it only rewrites values.
- **hpc_chain:** R2 swaps HPC1 for ISW/DOM (24 → 18). **Model artefact:** HPC1
  exists for glitch robustness, which this glitch-free model cannot see, so
  this saving would not be a real one in hardware.

### Tight starts — Keccak chi

| Fixture (start) | none | R1 | R2 | R3 | R1+R2 | R1+R3 | R2+R3 | all |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| chi3 (36 = 33g + 3r) | 36 | 36 | 36 | 36 | 36 | 36 | 36 | 36 |
| chi5 (60 = 55g + 5r) | 60 | 60 | 60 | 60 | 60 | 60 | 60 | 60 |

Unconstrained and constrained agree everywhere, and every result is secure.
**No rule class improves a tight start.** chi5 saturates in 0.01 s and
extracts in about 0.5 s (39 classes).

This is what the cost model predicts. The layer can change only three things:
the number and kind of AND gadgets (R1, R2), the number of refreshes (R3), and
the linear gates around them (R1). A start that already uses the cheapest
gadget, has no redundant refresh, and has no AND gadget that R1 can factor
away has nothing left for these rules to remove. Every gain in the table above
came from one of those three kinds of slack.

**Why not VerifMSI's gadget set.** Its 2-share first-order benchmarks
(ISW, DOM, Trichina, …) are single AND gadgets. This layer treats a gadget as
an atom, so on one gadget it can only swap it for another (R2) — the
gadget-scale question was already answered at the wire level (constrained
optimum = ISW, `docs/feasibility-report.md`). Its larger benchmarks (masked AES
in `aes_herbst`) are word-level, not Boolean circuits, and multi-share
benchmarks are out of scope (`design/0002`). Using them would need lifting a
wire circuit back to gadget terms, which does not exist.

### Frontier stability (constrained, all rules)

The constrained cost is the same at k = 2, 8 and 32 on every fixture, the chi
starts included.

### Trust boundary

VerifMSI cross-check of every fixture and reported circuit: **27 distinct
lowered circuits, 914 wires, 0 violations** (19 circuits / 458 wires before
the chi starts were added). `test_resharing.py` repeats the
cross-check over the rule sets {none, R3, all} whenever the oracle is installed.

### Scale — ISW chain of depth n, all rules, constrained, k = 8

| Depth | Classes | Nodes | Saturate | Extract | Terms evaluated | Cost |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 7 | 45 | 0.01 s | 0.0 s | 51 | 18 |
| 3 | 15 | 168 | 0.01 s | 0.3 s | 1,303 | 27 |
| 4 | 31 | 575 | 0.01 s | 5.2 s | 9,927 | 36 |
| 5 | 63 | 1,824 | 0.02 s | 143.6 s | 48,268 | 45 |

Cost is 9 per gadget at every depth: no gain on chains.

## What this does and does not show

**Shows:**

- At the shared-value layer, R2 and R3 are **ordinary rewrite rules**: the
  re-sharing equivalences become a congruence once the e-graph identifies
  sharings by value. This is a representation answer to the question in
  `design/0011`.
- The security constraint is still needed there: refresh removal is cheaper
  and leaks on `square`, and constrained extraction blocks it.
- Gains exist where the start circuit has slack: redundant refreshes (−12),
  value-level factoring (−9) and, in this model only, HPC1 → DOM/ISW (−6).
- Standard one-node-per-class extraction is not enough: `z` and `refresh(z)` are
  one class, so keeping the refresh requires choosing per occurrence.

**Does not show:**

- **That any of these optimizations is new.** Removing redundant refreshes,
  minimising AND gadgets by factoring before masking, and choosing gadgets are
  all established masking-compiler practice (Tornado, AGEMA, COMPRESS, eVer).
  The contribution claimed here is the representation, not the optimizations;
  any novelty claim needs the citation-check skill first.
- **A gain over a tight construction.** Every gain is relative to a start
  with deliberate slack; the tight chain and both chi starts gain nothing. For
  R2 and R3 that is expected (the starts already use the cheapest gadget and no
  refresh); for R1 it holds only up to R1's incompleteness (see Exactness). The
  lever this layer does not model is randomness — reusing randoms across
  gadgets (every gadget gets a fresh random) — which leaked on the chain when
  done naively.
- **Anything beyond first order, 2 shares, glitch-free.** In particular nothing
  about glitches, PINI/SNI composition, or higher orders — and HPC results are
  only meaningful relative to that caveat.
- **Exactness.** Extraction is a k-best frontier, stable across k = 2…32 on
  these fixtures but not proven optimal. R1 is not complete either: a form with
  fewer AND gadgets that needs idempotence or constants is unreachable, so "no
  gain on chi" is a statement about these rules, not about chi's multiplicative
  complexity.
- **Scale.** Term-based extraction is now the bottleneck: ~144 s at chain
  depth 5, growing roughly 10–30× per level.

## Known limitations

- R1 has no idempotence (`x & x = x`), absorption or constants. With
  idempotence, `square` collapses to `z` and the refresh question disappears;
  it was left out so the refresh behaviour stays visible. Majority-style
  rewrites that need `b & b = b` are unreachable.
- Randomness reuse across gadgets is not explored. Every gadget gets a fresh
  random.
- HPC2 is not modelled: its share equations were not fetched (UNVERIFIED).
- `layer.export` uses egglog's private `_serialize`; `test_export_format_guard`
  fails loudly if a version change alters it.
- Saturation runs a fixed 6 iterations; it is not checked to have reached a
  fixed point on the scale sweep.

## Reproduce

```bash
uv run pytest -q experiments/resharing
uv run python experiments/resharing/run.py --crosscheck   # ~20 s with the oracle
uv run python experiments/resharing/run.py --scale        # adds ~2.5 min
```

The tests were mutation-checked: DOM without its random (12 failures),
safety filter disabled (1), an unsound R2 rule `dom → xor` (4), HPC1 without
its refresh (2), NOT that does not negate (3).

## Raw output

`PYTHONHASHSEED=0 uv run python experiments/resharing/run.py --crosscheck`:

```

== chain:  18 = 16g + 2r  secure           isw(isw(a, b), d)
  none      unconstrained  18 = 16g + 2r  secure           isw(isw(a, b), d)
  none      constrained    18 = 16g + 2r  secure           isw(isw(a, b), d)
            [5 classes, saturate 0.00s, 5 terms evaluated, converged=True]
  R1        unconstrained  18 = 16g + 2r  secure           isw(a, isw(b, d))
  R1        constrained    18 = 16g + 2r  secure           isw(a, isw(b, d))
            [7 classes, saturate 0.01s, 17 terms evaluated, converged=True]
  R2        unconstrained  18 = 16g + 2r  secure           dom(dom(a, b), d)
  R2        constrained    18 = 16g + 2r  secure           dom(dom(a, b), d)
            [5 classes, saturate 0.00s, 14 terms evaluated, converged=True]
  R3        unconstrained  18 = 16g + 2r  secure           isw(isw(a, b), d)
  R3        constrained    18 = 16g + 2r  secure           isw(isw(a, b), d)
            [5 classes, saturate 0.00s, 22 terms evaluated, converged=True]
  R1+R2     unconstrained  18 = 16g + 2r  secure           isw(dom(a, b), d)
  R1+R2     constrained    18 = 16g + 2r  secure           isw(dom(a, b), d)
            [7 classes, saturate 0.01s, 31 terms evaluated, converged=True]
  R1+R3     unconstrained  18 = 16g + 2r  secure           isw(a, isw(b, d))
  R1+R3     constrained    18 = 16g + 2r  secure           isw(a, isw(b, d))
            [7 classes, saturate 0.01s, 58 terms evaluated, converged=True]
  R2+R3     unconstrained  18 = 16g + 2r  secure           dom(dom(a, b), d)
  R2+R3     constrained    18 = 16g + 2r  secure           dom(dom(a, b), d)
            [5 classes, saturate 0.00s, 31 terms evaluated, converged=True]
  R1+R2+R3  unconstrained  18 = 16g + 2r  secure           isw(dom(a, b), d)
  R1+R2+R3  constrained    18 = 16g + 2r  secure           isw(dom(a, b), d)
            [7 classes, saturate 0.01s, 51 terms evaluated, converged=True]

== overrefreshed:  30 = 24g + 6r  secure           isw(refresh(isw(refresh(a), refresh(b))), refresh(d))
  none      unconstrained  30 = 24g + 6r  secure           isw(refresh(isw(refresh(a), refresh(b))), refresh(d))
  none      constrained    30 = 24g + 6r  secure           isw(refresh(isw(refresh(a), refresh(b))), refresh(d))
            [9 classes, saturate 0.00s, 9 terms evaluated, converged=True]
  R1        unconstrained  30 = 24g + 6r  secure           isw(refresh(d), refresh(isw(refresh(a), refresh(b))))
  R1        constrained    30 = 24g + 6r  secure           isw(refresh(d), refresh(isw(refresh(a), refresh(b))))
            [9 classes, saturate 0.01s, 14 terms evaluated, converged=True]
  R2        unconstrained  30 = 24g + 6r  secure           dom(refresh(dom(refresh(a), refresh(b))), refresh(d))
  R2        constrained    30 = 24g + 6r  secure           dom(refresh(dom(refresh(a), refresh(b))), refresh(d))
            [9 classes, saturate 0.00s, 20 terms evaluated, converged=True]
  R3        unconstrained  18 = 16g + 2r  secure           isw(isw(a, b), d)
  R3        constrained    18 = 16g + 2r  secure           isw(isw(a, b), d)
            [5 classes, saturate 0.00s, 22 terms evaluated, converged=True]
  R1+R2     unconstrained  30 = 24g + 6r  secure           isw(refresh(dom(refresh(a), refresh(b))), refresh(d))
  R1+R2     constrained    30 = 24g + 6r  secure           isw(refresh(dom(refresh(a), refresh(b))), refresh(d))
            [9 classes, saturate 0.01s, 36 terms evaluated, converged=True]
  R1+R3     unconstrained  18 = 16g + 2r  secure           isw(a, isw(b, d))
  R1+R3     constrained    18 = 16g + 2r  secure           isw(a, isw(b, d))
            [7 classes, saturate 0.01s, 51 terms evaluated, converged=True]
  R2+R3     unconstrained  18 = 16g + 2r  secure           dom(dom(a, b), d)
  R2+R3     constrained    18 = 16g + 2r  secure           dom(dom(a, b), d)
            [5 classes, saturate 0.01s, 27 terms evaluated, converged=True]
  R1+R2+R3  unconstrained  18 = 16g + 2r  secure           isw(dom(a, b), d)
  R1+R2+R3  constrained    18 = 16g + 2r  secure           isw(dom(a, b), d)
            [7 classes, saturate 0.01s, 42 terms evaluated, converged=True]

== square:  14 = 12g + 2r  secure           isw(xor(a, b), refresh(xor(a, b)))
  none      unconstrained  14 = 12g + 2r  secure           isw(xor(a, b), refresh(xor(a, b)))
  none      constrained    14 = 12g + 2r  secure           isw(xor(a, b), refresh(xor(a, b)))
            [5 classes, saturate 0.00s, 5 terms evaluated, converged=True]
  R1        unconstrained  14 = 12g + 2r  secure           isw(refresh(xor(a, b)), xor(a, b))
  R1        constrained    14 = 12g + 2r  secure           isw(refresh(xor(a, b)), xor(a, b))
            [7 classes, saturate 0.01s, 22 terms evaluated, converged=True]
  R2        unconstrained  14 = 12g + 2r  secure           dom(xor(a, b), refresh(xor(a, b)))
  R2        constrained    14 = 12g + 2r  secure           dom(xor(a, b), refresh(xor(a, b)))
            [5 classes, saturate 0.00s, 7 terms evaluated, converged=True]
  R3        unconstrained  11 = 10g + 1r  LEAKS (2 wires)  isw(xor(a, b), xor(a, b))
  R3        constrained    14 = 12g + 2r  secure           isw(refresh(xor(a, b)), xor(a, b))
            [4 classes, saturate 0.01s, 8 terms evaluated, converged=True]
  R1+R2     unconstrained  14 = 12g + 2r  secure           dom(refresh(xor(a, b)), xor(a, b))
  R1+R2     constrained    14 = 12g + 2r  secure           dom(refresh(xor(a, b)), xor(a, b))
            [7 classes, saturate 0.01s, 38 terms evaluated, converged=True]
  R1+R3     unconstrained  11 = 10g + 1r  LEAKS (2 wires)  isw(xor(a, b), xor(a, b))
  R1+R3     constrained    14 = 12g + 2r  secure           isw(refresh(xor(a, b)), xor(a, b))
            [19 classes, saturate 0.01s, 960 terms evaluated, converged=True]
  R2+R3     unconstrained  11 = 10g + 1r  LEAKS (2 wires)  dom(xor(a, b), xor(a, b))
  R2+R3     constrained    14 = 12g + 2r  secure           dom(refresh(xor(a, b)), xor(a, b))
            [4 classes, saturate 0.00s, 16 terms evaluated, converged=True]
  R1+R2+R3  unconstrained  11 = 10g + 1r  LEAKS (2 wires)  dom(xor(a, b), xor(a, b))
  R1+R2+R3  constrained    14 = 12g + 2r  secure           dom(refresh(xor(a, b)), xor(a, b))
            [19 classes, saturate 0.01s, 2089 terms evaluated, converged=True]

== factor:  20 = 18g + 2r  secure           xor(isw(a, b), isw(a, d))
  none      unconstrained  20 = 18g + 2r  secure           xor(isw(a, b), isw(a, d))
  none      constrained    20 = 18g + 2r  secure           xor(isw(a, b), isw(a, d))
            [6 classes, saturate 0.00s, 6 terms evaluated, converged=True]
  R1        unconstrained  11 = 10g + 1r  secure           isw(a, xor(b, d))
  R1        constrained    11 = 10g + 1r  secure           isw(a, xor(b, d))
            [7 classes, saturate 0.01s, 21 terms evaluated, converged=True]
  R2        unconstrained  20 = 18g + 2r  secure           xor(dom(a, b), dom(a, d))
  R2        constrained    20 = 18g + 2r  secure           xor(dom(a, b), dom(a, d))
            [6 classes, saturate 0.00s, 18 terms evaluated, converged=True]
  R3        unconstrained  20 = 18g + 2r  secure           xor(isw(a, b), isw(a, d))
  R3        constrained    20 = 18g + 2r  secure           xor(isw(a, b), isw(a, d))
            [6 classes, saturate 0.00s, 30 terms evaluated, converged=True]
  R1+R2     unconstrained  11 = 10g + 1r  secure           dom(a, xor(b, d))
  R1+R2     constrained    11 = 10g + 1r  secure           dom(a, xor(b, d))
            [7 classes, saturate 0.01s, 97 terms evaluated, converged=True]
  R1+R3     unconstrained  11 = 10g + 1r  secure           isw(a, xor(b, d))
  R1+R3     constrained    11 = 10g + 1r  secure           isw(a, xor(b, d))
            [7 classes, saturate 0.01s, 174 terms evaluated, converged=True]
  R2+R3     unconstrained  20 = 18g + 2r  secure           xor(dom(a, b), dom(a, d))
  R2+R3     constrained    20 = 18g + 2r  secure           xor(dom(a, b), dom(a, d))
            [6 classes, saturate 0.00s, 88 terms evaluated, converged=True]
  R1+R2+R3  unconstrained  11 = 10g + 1r  secure           dom(a, xor(b, d))
  R1+R2+R3  constrained    11 = 10g + 1r  secure           dom(a, xor(b, d))
            [7 classes, saturate 0.01s, 187 terms evaluated, converged=True]

== hpc_chain:  24 = 20g + 4r  secure           hpc1(hpc1(a, b), d)
  none      unconstrained  24 = 20g + 4r  secure           hpc1(hpc1(a, b), d)
  none      constrained    24 = 20g + 4r  secure           hpc1(hpc1(a, b), d)
            [5 classes, saturate 0.00s, 5 terms evaluated, converged=True]
  R1        unconstrained  24 = 20g + 4r  secure           hpc1(hpc1(a, b), d)
  R1        constrained    24 = 20g + 4r  secure           hpc1(hpc1(a, b), d)
            [7 classes, saturate 0.01s, 17 terms evaluated, converged=True]
  R2        unconstrained  18 = 16g + 2r  secure           dom(dom(a, b), d)
  R2        constrained    18 = 16g + 2r  secure           dom(dom(a, b), d)
            [5 classes, saturate 0.00s, 15 terms evaluated, converged=True]
  R3        unconstrained  24 = 20g + 4r  secure           hpc1(hpc1(a, b), d)
  R3        constrained    24 = 20g + 4r  secure           hpc1(hpc1(a, b), d)
            [5 classes, saturate 0.00s, 22 terms evaluated, converged=True]
  R1+R2     unconstrained  18 = 16g + 2r  secure           isw(dom(a, b), d)
  R1+R2     constrained    18 = 16g + 2r  secure           isw(dom(a, b), d)
            [7 classes, saturate 0.01s, 39 terms evaluated, converged=True]
  R1+R3     unconstrained  24 = 20g + 4r  secure           hpc1(hpc1(a, b), d)
  R1+R3     constrained    24 = 20g + 4r  secure           hpc1(hpc1(a, b), d)
            [7 classes, saturate 0.01s, 58 terms evaluated, converged=True]
  R2+R3     unconstrained  18 = 16g + 2r  secure           dom(dom(a, b), d)
  R2+R3     constrained    18 = 16g + 2r  secure           dom(dom(a, b), d)
            [5 classes, saturate 0.00s, 41 terms evaluated, converged=True]
  R1+R2+R3  unconstrained  18 = 16g + 2r  secure           isw(dom(a, b), d)
  R1+R2+R3  constrained    18 = 16g + 2r  secure           isw(dom(a, b), d)
            [7 classes, saturate 0.01s, 81 terms evaluated, converged=True]

== chi3:  36 = 33g + 3r  secure           out(xor(x0, isw(not(x1), x2)), out(xor(x1, isw(not(x2), x0)), xor(x2, isw(not(x0), x1))))
  none      unconstrained  36 = 33g + 3r  secure           out(xor(x0, isw(not(x1), x2)), out(xor(x1, isw(not(x2), x0)), xor(x2, isw(not(x0), x1))))
  none      constrained    36 = 33g + 3r  secure           out(xor(x0, isw(not(x1), x2)), out(xor(x1, isw(not(x2), x0)), xor(x2, isw(not(x0), x1))))
            [14 classes, saturate 0.00s, 14 terms evaluated, converged=True]
  R1        unconstrained  36 = 33g + 3r  secure           out(xor(x0, isw(x2, not(x1))), out(xor(x1, isw(x0, not(x2))), xor(x2, isw(x1, not(x0)))))
  R1        constrained    36 = 33g + 3r  secure           out(xor(x0, isw(x2, not(x1))), out(xor(x1, isw(x0, not(x2))), xor(x2, isw(x1, not(x0)))))
            [23 classes, saturate 0.01s, 324 terms evaluated, converged=True]
  R2        unconstrained  36 = 33g + 3r  secure           out(xor(x0, dom(not(x1), x2)), out(xor(x1, dom(not(x2), x0)), xor(x2, dom(not(x0), x1))))
  R2        constrained    36 = 33g + 3r  secure           out(xor(x0, dom(not(x1), x2)), out(xor(x1, dom(not(x2), x0)), xor(x2, dom(not(x0), x1))))
            [14 classes, saturate 0.00s, 57 terms evaluated, converged=True]
  R3        unconstrained  36 = 33g + 3r  secure           out(xor(x0, isw(not(x1), x2)), out(xor(x1, isw(not(x2), x0)), xor(x2, isw(not(x0), x1))))
  R3        constrained    36 = 33g + 3r  secure           out(xor(x0, isw(not(x1), x2)), out(xor(x1, isw(not(x2), x0)), xor(x2, isw(not(x0), x1))))
            [14 classes, saturate 0.00s, 206 terms evaluated, converged=True]
  R1+R2     unconstrained  36 = 33g + 3r  secure           out(xor(dom(x2, not(x1)), x0), out(xor(dom(x0, not(x2)), x1), xor(dom(x1, not(x0)), x2)))
  R1+R2     constrained    36 = 33g + 3r  secure           out(xor(dom(x2, not(x1)), x0), out(xor(dom(x0, not(x2)), x1), xor(dom(x1, not(x0)), x2)))
            [23 classes, saturate 0.01s, 436 terms evaluated, converged=True]
  R1+R3     unconstrained  36 = 33g + 3r  secure           out(xor(x0, isw(x2, not(x1))), out(xor(x1, isw(x0, not(x2))), xor(x2, isw(x1, not(x0)))))
  R1+R3     constrained    36 = 33g + 3r  secure           out(xor(x0, isw(x2, not(x1))), out(xor(x1, isw(x0, not(x2))), xor(x2, isw(x1, not(x0)))))
            [23 classes, saturate 0.01s, 636 terms evaluated, converged=True]
  R2+R3     unconstrained  36 = 33g + 3r  secure           out(xor(x0, dom(not(x1), x2)), out(xor(x1, dom(not(x2), x0)), xor(x2, dom(not(x0), x1))))
  R2+R3     constrained    36 = 33g + 3r  secure           out(xor(x0, dom(not(x1), x2)), out(xor(x1, dom(not(x2), x0)), xor(x2, dom(not(x0), x1))))
            [14 classes, saturate 0.00s, 215 terms evaluated, converged=True]
  R1+R2+R3  unconstrained  36 = 33g + 3r  secure           out(xor(dom(x2, not(x1)), x0), out(xor(dom(x0, not(x2)), x1), xor(dom(x1, not(x0)), x2)))
  R1+R2+R3  constrained    36 = 33g + 3r  secure           out(xor(dom(x2, not(x1)), x0), out(xor(dom(x0, not(x2)), x1), xor(dom(x1, not(x0)), x2)))
            [23 classes, saturate 0.01s, 685 terms evaluated, converged=True]

== chi5:  60 = 55g + 5r  secure           out(xor(x0, isw(not(x1), x2)), out(xor(x1, isw(not(x2), x3)), out(xor(x2, isw(not(x3), x4)), out(xor(x3, isw(not(x4), x0)), xor(x4, isw(not(x0), x1))))))
  none      unconstrained  60 = 55g + 5r  secure           out(xor(x0, isw(not(x1), x2)), out(xor(x1, isw(not(x2), x3)), out(xor(x2, isw(not(x3), x4)), out(xor(x3, isw(not(x4), x0)), xor(x4, isw(not(x0), x1))))))
  none      constrained    60 = 55g + 5r  secure           out(xor(x0, isw(not(x1), x2)), out(xor(x1, isw(not(x2), x3)), out(xor(x2, isw(not(x3), x4)), out(xor(x3, isw(not(x4), x0)), xor(x4, isw(not(x0), x1))))))
            [24 classes, saturate 0.00s, 24 terms evaluated, converged=True]
  R1        unconstrained  60 = 55g + 5r  secure           out(xor(x0, isw(x2, not(x1))), out(xor(x1, isw(x3, not(x2))), out(xor(x2, isw(x4, not(x3))), out(xor(x3, isw(x0, not(x4))), xor(x4, isw(x1, not(x0)))))))
  R1        constrained    60 = 55g + 5r  secure           out(xor(x0, isw(x2, not(x1))), out(xor(x1, isw(x3, not(x2))), out(xor(x2, isw(x4, not(x3))), out(xor(x3, isw(x0, not(x4))), xor(x4, isw(x1, not(x0)))))))
            [39 classes, saturate 0.01s, 636 terms evaluated, converged=True]
  R2        unconstrained  60 = 55g + 5r  secure           out(xor(x0, dom(not(x1), x2)), out(xor(x1, dom(not(x2), x3)), out(xor(x2, dom(not(x3), x4)), out(xor(x3, dom(not(x4), x0)), xor(x4, dom(not(x0), x1))))))
  R2        constrained    60 = 55g + 5r  secure           out(xor(x0, dom(not(x1), x2)), out(xor(x1, dom(not(x2), x3)), out(xor(x2, dom(not(x3), x4)), out(xor(x3, dom(not(x4), x0)), xor(x4, dom(not(x0), x1))))))
            [24 classes, saturate 0.01s, 121 terms evaluated, converged=True]
  R3        unconstrained  60 = 55g + 5r  secure           out(xor(x0, isw(not(x1), x2)), out(xor(x1, isw(not(x2), x3)), out(xor(x2, isw(not(x3), x4)), out(xor(x3, isw(not(x4), x0)), xor(x4, isw(not(x0), x1))))))
  R3        constrained    60 = 55g + 5r  secure           out(xor(x0, isw(not(x1), x2)), out(xor(x1, isw(not(x2), x3)), out(xor(x2, isw(not(x3), x4)), out(xor(x3, isw(not(x4), x0)), xor(x4, isw(not(x0), x1))))))
            [24 classes, saturate 0.01s, 386 terms evaluated, converged=True]
  R1+R2     unconstrained  60 = 55g + 5r  secure           out(xor(dom(x2, not(x1)), x0), out(xor(dom(x3, not(x2)), x1), out(xor(dom(x4, not(x3)), x2), out(xor(dom(x0, not(x4)), x3), xor(dom(x1, not(x0)), x4)))))
  R1+R2     constrained    60 = 55g + 5r  secure           out(xor(dom(x2, not(x1)), x0), out(xor(dom(x3, not(x2)), x1), out(xor(dom(x4, not(x3)), x2), out(xor(dom(x0, not(x4)), x3), xor(dom(x1, not(x0)), x4)))))
            [39 classes, saturate 0.01s, 812 terms evaluated, converged=True]
  R1+R3     unconstrained  60 = 55g + 5r  secure           out(xor(x0, isw(x2, not(x1))), out(xor(x1, isw(x3, not(x2))), out(xor(x2, isw(x4, not(x3))), out(xor(x3, isw(x0, not(x4))), xor(x4, isw(x1, not(x0)))))))
  R1+R3     constrained    60 = 55g + 5r  secure           out(xor(x0, isw(x2, not(x1))), out(xor(x1, isw(x3, not(x2))), out(xor(x2, isw(x4, not(x3))), out(xor(x3, isw(x0, not(x4))), xor(x4, isw(x1, not(x0)))))))
            [39 classes, saturate 0.01s, 1156 terms evaluated, converged=True]
  R2+R3     unconstrained  60 = 55g + 5r  secure           out(xor(x0, dom(not(x1), x2)), out(xor(x1, dom(not(x2), x3)), out(xor(x2, dom(not(x3), x4)), out(xor(x3, dom(not(x4), x0)), xor(x4, dom(not(x0), x1))))))
  R2+R3     constrained    60 = 55g + 5r  secure           out(xor(x0, dom(not(x1), x2)), out(xor(x1, dom(not(x2), x3)), out(xor(x2, dom(not(x3), x4)), out(xor(x3, dom(not(x4), x0)), xor(x4, dom(not(x0), x1))))))
            [24 classes, saturate 0.01s, 401 terms evaluated, converged=True]
  R1+R2+R3  unconstrained  60 = 55g + 5r  secure           out(xor(dom(x2, not(x1)), x0), out(xor(dom(x3, not(x2)), x1), out(xor(dom(x4, not(x3)), x2), out(xor(dom(x0, not(x4)), x3), xor(dom(x1, not(x0)), x4)))))
  R1+R2+R3  constrained    60 = 55g + 5r  secure           out(xor(dom(x2, not(x1)), x0), out(xor(dom(x3, not(x2)), x1), out(xor(dom(x4, not(x3)), x2), out(xor(dom(x0, not(x4)), x3), xor(dom(x1, not(x0)), x4)))))
            [39 classes, saturate 0.01s, 1227 terms evaluated, converged=True]

== frontier stability: constrained cost, all rules, by k
  chain          k=2: 18  k=8: 18  k=32: 18
  overrefreshed  k=2: 18  k=8: 18  k=32: 18
  square         k=2: 14  k=8: 14  k=32: 14
  factor         k=2: 11  k=8: 11  k=32: 11
  hpc_chain      k=2: 18  k=8: 18  k=32: 18
  chi3           k=2: 36  k=8: 36  k=32: 36
  chi5           k=2: 60  k=8: 60  k=32: 60

== VerifMSI cross-check: 27 distinct lowered circuits, 914 wires, 0 violations
```

Scale sweep (`run.scale(6, 8)`):

```
== scale: ISW chain of depth n, all rules
  depth 2:    7 classes,    45 nodes, saturate 0.01s, constrained extract 0.0s (51 terms), cost 18
  depth 3:   15 classes,   168 nodes, saturate 0.01s, constrained extract 0.3s (1303 terms), cost 27
  depth 4:   31 classes,   575 nodes, saturate 0.01s, constrained extract 5.2s (9927 terms), cost 36
  depth 5:   63 classes,  1824 nodes, saturate 0.02s, constrained extract 143.6s (48268 terms), cost 45
```
