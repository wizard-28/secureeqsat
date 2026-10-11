# Shared-value layer: re-sharing rules and gadget equivalences — results

**Date:** 2026-10-11 · **ADR:** `design/0016`

## Question

Refresh insertion/removal (R3) and gadget substitution (R2) are equivalences
*up to re-sharing*: they keep the reconstructed value and change the shares, so
the wire-level e-graph cannot express them (`design/0010`, `0011`). If the
e-graph works one layer up, on sharings identified by their value, (1) do R2
and R3 become ordinary rules, (2) does the security constraint still matter,
and (3) do any of the rule classes give a secure circuit cheaper than the
hand-written one?

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

### Frontier stability (constrained, all rules)

The constrained cost is the same at k = 2, 8 and 32 on every fixture.

### Trust boundary

VerifMSI cross-check of every fixture and reported circuit: **19 distinct
lowered circuits, 458 wires, 0 violations**. `test_resharing.py` repeats the
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
- **A gain over a good hand-written circuit.** Every gain above is relative to
  a start circuit with deliberate slack; the tight chain gains nothing.
- **Anything beyond first order, 2 shares, glitch-free.** In particular nothing
  about glitches, PINI/SNI composition, or higher orders — and HPC results are
  only meaningful relative to that caveat.
- **Exactness.** Extraction is a k-best frontier, stable across k = 2…32 on
  these fixtures but not proven optimal.
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
uv run python experiments/resharing/run.py --crosscheck   # ~10 s with the oracle
uv run python experiments/resharing/run.py --scale        # adds ~2.5 min
```

The tests were mutation-checked: DOM without its random (12 failures),
safety filter disabled (1), an unsound R2 rule `dom → xor` (4), HPC1 without
its refresh (2).

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
            [7 classes, saturate 0.00s, 58 terms evaluated, converged=True]
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
            [9 classes, saturate 0.00s, 14 terms evaluated, converged=True]
  R2        unconstrained  30 = 24g + 6r  secure           dom(refresh(dom(refresh(a), refresh(b))), refresh(d))
  R2        constrained    30 = 24g + 6r  secure           dom(refresh(dom(refresh(a), refresh(b))), refresh(d))
            [9 classes, saturate 0.00s, 20 terms evaluated, converged=True]
  R3        unconstrained  18 = 16g + 2r  secure           isw(isw(a, b), d)
  R3        constrained    18 = 16g + 2r  secure           isw(isw(a, b), d)
            [5 classes, saturate 0.00s, 22 terms evaluated, converged=True]
  R1+R2     unconstrained  30 = 24g + 6r  secure           isw(refresh(dom(refresh(a), refresh(b))), refresh(d))
  R1+R2     constrained    30 = 24g + 6r  secure           isw(refresh(dom(refresh(a), refresh(b))), refresh(d))
            [9 classes, saturate 0.00s, 36 terms evaluated, converged=True]
  R1+R3     unconstrained  18 = 16g + 2r  secure           isw(a, isw(b, d))
  R1+R3     constrained    18 = 16g + 2r  secure           isw(a, isw(b, d))
            [7 classes, saturate 0.00s, 51 terms evaluated, converged=True]
  R2+R3     unconstrained  18 = 16g + 2r  secure           dom(dom(a, b), d)
  R2+R3     constrained    18 = 16g + 2r  secure           dom(dom(a, b), d)
            [5 classes, saturate 0.00s, 27 terms evaluated, converged=True]
  R1+R2+R3  unconstrained  18 = 16g + 2r  secure           isw(dom(a, b), d)
  R1+R2+R3  constrained    18 = 16g + 2r  secure           isw(dom(a, b), d)
            [7 classes, saturate 0.01s, 42 terms evaluated, converged=True]

== square:  14 = 12g + 2r  secure           isw(xor(a, b), refresh(xor(a, b)))
  none      unconstrained  14 = 12g + 2r  secure           isw(xor(a, b), refresh(xor(a, b)))
  none      constrained    14 = 12g + 2r  secure           isw(xor(a, b), refresh(xor(a, b)))
            [5 classes, saturate 0.00s, 5 terms evaluated, converged=True]
  R1        unconstrained  14 = 12g + 2r  secure           isw(refresh(xor(a, b)), xor(a, b))
  R1        constrained    14 = 12g + 2r  secure           isw(refresh(xor(a, b)), xor(a, b))
            [7 classes, saturate 0.00s, 22 terms evaluated, converged=True]
  R2        unconstrained  14 = 12g + 2r  secure           dom(xor(a, b), refresh(xor(a, b)))
  R2        constrained    14 = 12g + 2r  secure           dom(xor(a, b), refresh(xor(a, b)))
            [5 classes, saturate 0.00s, 7 terms evaluated, converged=True]
  R3        unconstrained  11 = 10g + 1r  LEAKS (2 wires)  isw(xor(a, b), xor(a, b))
  R3        constrained    14 = 12g + 2r  secure           isw(refresh(xor(a, b)), xor(a, b))
            [4 classes, saturate 0.00s, 8 terms evaluated, converged=True]
  R1+R2     unconstrained  14 = 12g + 2r  secure           dom(refresh(xor(a, b)), xor(a, b))
  R1+R2     constrained    14 = 12g + 2r  secure           dom(refresh(xor(a, b)), xor(a, b))
            [7 classes, saturate 0.00s, 38 terms evaluated, converged=True]
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
            [7 classes, saturate 0.00s, 21 terms evaluated, converged=True]
  R2        unconstrained  20 = 18g + 2r  secure           xor(dom(a, b), dom(a, d))
  R2        constrained    20 = 18g + 2r  secure           xor(dom(a, b), dom(a, d))
            [6 classes, saturate 0.00s, 18 terms evaluated, converged=True]
  R3        unconstrained  20 = 18g + 2r  secure           xor(isw(a, b), isw(a, d))
  R3        constrained    20 = 18g + 2r  secure           xor(isw(a, b), isw(a, d))
            [6 classes, saturate 0.00s, 30 terms evaluated, converged=True]
  R1+R2     unconstrained  11 = 10g + 1r  secure           dom(a, xor(b, d))
  R1+R2     constrained    11 = 10g + 1r  secure           dom(a, xor(b, d))
            [7 classes, saturate 0.00s, 97 terms evaluated, converged=True]
  R1+R3     unconstrained  11 = 10g + 1r  secure           isw(a, xor(b, d))
  R1+R3     constrained    11 = 10g + 1r  secure           isw(a, xor(b, d))
            [7 classes, saturate 0.00s, 174 terms evaluated, converged=True]
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
            [7 classes, saturate 0.00s, 17 terms evaluated, converged=True]
  R2        unconstrained  18 = 16g + 2r  secure           dom(dom(a, b), d)
  R2        constrained    18 = 16g + 2r  secure           dom(dom(a, b), d)
            [5 classes, saturate 0.00s, 15 terms evaluated, converged=True]
  R3        unconstrained  24 = 20g + 4r  secure           hpc1(hpc1(a, b), d)
  R3        constrained    24 = 20g + 4r  secure           hpc1(hpc1(a, b), d)
            [5 classes, saturate 0.00s, 22 terms evaluated, converged=True]
  R1+R2     unconstrained  18 = 16g + 2r  secure           isw(dom(a, b), d)
  R1+R2     constrained    18 = 16g + 2r  secure           isw(dom(a, b), d)
            [7 classes, saturate 0.00s, 39 terms evaluated, converged=True]
  R1+R3     unconstrained  24 = 20g + 4r  secure           hpc1(hpc1(a, b), d)
  R1+R3     constrained    24 = 20g + 4r  secure           hpc1(hpc1(a, b), d)
            [7 classes, saturate 0.00s, 58 terms evaluated, converged=True]
  R2+R3     unconstrained  18 = 16g + 2r  secure           dom(dom(a, b), d)
  R2+R3     constrained    18 = 16g + 2r  secure           dom(dom(a, b), d)
            [5 classes, saturate 0.00s, 41 terms evaluated, converged=True]
  R1+R2+R3  unconstrained  18 = 16g + 2r  secure           isw(dom(a, b), d)
  R1+R2+R3  constrained    18 = 16g + 2r  secure           isw(dom(a, b), d)
            [7 classes, saturate 0.01s, 81 terms evaluated, converged=True]

== frontier stability: constrained cost, all rules, by k
  chain          k=2: 18  k=8: 18  k=32: 18
  overrefreshed  k=2: 18  k=8: 18  k=32: 18
  square         k=2: 14  k=8: 14  k=32: 14
  factor         k=2: 11  k=8: 11  k=32: 11
  hpc_chain      k=2: 18  k=8: 18  k=32: 18

== VerifMSI cross-check: 19 distinct lowered circuits, 458 wires, 0 violations
```

Scale sweep (`run.scale(6, 8)`):

```
== scale: ISW chain of depth n, all rules
  depth 2:    7 classes,    45 nodes, saturate 0.01s, constrained extract 0.0s (51 terms), cost 18
  depth 3:   15 classes,   168 nodes, saturate 0.01s, constrained extract 0.3s (1303 terms), cost 27
  depth 4:   31 classes,   575 nodes, saturate 0.01s, constrained extract 5.2s (9927 terms), cost 36
  depth 5:   63 classes,  1824 nodes, saturate 0.02s, constrained extract 143.6s (48268 terms), cost 45
```
