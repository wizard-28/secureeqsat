# Bitsliced exact labeller — results

**Date:** 2026-10-07 · **ADR:** `design/0015`

## Question

Safety labelling was the measured scalability bottleneck
(`docs/adversarial-search-3.md` §D2): the reference checker enumerates every
assignment through a per-assignment `evaluate()` call, and `class_safety`
materialised a fresh circuit and ran that checker once per e-class. Can the
labelling be made fast **without changing the security semantics** — same
model, same verdict on every wire and every class?

## Method

Safety (first order, 2 shares, glitch-free) is a property of the Boolean
function a wire or e-class computes. `labeller.py` therefore holds each function
as one truth table over the whole (secret, free-variable) space, packed into a
Python int:

- bit index `sbits * 2**F + fbits`, the enumeration order of
  `check_first_order`, so each secret assignment is a contiguous block;
- AND/XOR of two wires are single bitwise operations;
- a wire is safe iff its count of 1s is equal in every secret block
  (`int.bit_count()` per block) — the same distribution test as the reference.

On an e-graph, each class's table is computed once, bottom-up, in a fixed
point. With `check=True` (the default) every node in a class must produce the
class's table, so an unsound merge raises `InconsistentClassError`.

`constrained.class_safety` now delegates to this labeller; the original is
kept as `class_safety_reference`.

Stdlib only. Memory per table is `2**(secrets + free variables)` bits; spaces
above `2**26` (8 MiB per table) are refused with a `ValueError`.

## Results

### Agreement

| Against | Set | Disagreements |
|---|---|---:|
| `check_first_order` | 5 hand fixtures | 0 |
| `check_first_order` | 300 seeded random circuits, 1–3 secrets, 0–3 randoms, constants | 0 |
| `class_safety_reference` | saturated ISW e-graph, core and full rules | 0 |
| `class_safety_reference` | 2-gadget chain e-graph, core rules (test); chain e-graphs up to 4,353 classes (`measure.py`) | 0 |
| **VerifMSI exact independence** (RULE 1b) | the full cross-check: 1,265 circuits / 22,463 wires | **0** |

The VerifMSI cross-check is direct, not by transitivity: RULE 1b in
`experiments/oracle_crosscheck/crosscheck.py` compares the bitsliced verdict
with the oracle on every wire, in the same pass as the original checker. A
deliberately wrong labeller was confirmed to trip it.

The tests were also mutation-checked: a wrong secret-block layout, comparing
only two secret blocks, AND computed as OR, and a disabled consistency check
each make the suite fail.

### Speed — single circuit (mirrors §D2: 12 gates, 2 secrets, k randoms)

| Randoms | Reference | Bitsliced |
|---:|---:|---:|
| 2 | 0.000 s | 0.0001 s |
| 6 | 0.004 s | 0.0000 s |
| 10 | 0.072 s | 0.0002 s |
| 12 | 0.308 s | 0.0003 s |
| 14 | 1.302 s | 0.0013 s |
| 16 | (6.7 s in §D2) | 0.0040 s |
| 20 | — | 0.091 s |
| 22 | — | 0.464 s |

22 randoms is the `2**26` cap with 2 secrets.

### Speed — labelling every class of a chain e-graph

Chain of `depth` ISW ANDs: `depth + 1` secrets, `depth` randoms. In-house
e-graph saturated up to a class cap (the cap is checked between rules, so it
can overshoot).

| Depth | Rules | Bits | Classes | Saturate | Reference | Bitsliced | Speedup |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | full | 5 | 25 | 0.0 s | 0.00 s | 0.000 s | — |
| 2 | core | 8 | 42 | 0.0 s | 0.02 s | 0.000 s | ~95× |
| 3 | full | 11 | 1,039 | 1.1 s | 7.35 s | 0.006 s | ~1,300× |
| 2 | full | 8 | 4,353 | 52.3 s | 4.12 s | 0.023 s | ~180× |
| 5 | full | 17 | 4,315 | 16.8 s | **~50–55 min (est.)** | 0.405 s | ~8,000× (est.) |

The depth-5 reference figure is **extrapolated** from 5 timed classes
(2,992 s and 3,370 s on two runs); it is an order-of-magnitude estimate, not a
measurement. All other reference figures are measured, and the labels were
identical wherever the reference ran in full.

## What this does and does not show

**Shows:**

- Labelling is no longer the bottleneck at chain scale: a depth-5 chain is
  labelled in under half a second, and in-house **saturation** (16–52 s) now
  dominates. The real engine for saturation is `egglog` (`design/0009`).
- The speedup costs nothing in trust: identical verdicts against the reference
  checker, the reference labeller, and VerifMSI's exact function.
- A free soundness check on rewrite rules: an unsound merge is detected.

**Does not show:**

- **Scalability past ~26 bits.** It is still exact and exponential. A masked
  S-box with dozens of randoms exceeds the cap; that needs the deferred
  symbolic route (ANF/BDD, VerifMSI as an oracle, structural pre-filters).
- **Any new security property.** Same model and verdicts as `check_first_order`
  — first order, 2 shares, glitch-free — and nothing about higher orders,
  glitches or PINI.
- **egglog e-graphs.** The labeller runs on the in-house e-graph. Labelling an
  `egglog` e-graph needs an export of its classes, which does not exist yet.

## Known limitations

- `run_chain.py` still saturates up to 40,000 classes in the in-house engine
  and takes several minutes for that reason, not for labelling.
- `class_tables` keeps every class's table in memory at once:
  `classes × 2**bits / 8` bytes (4,315 classes at 17 bits ≈ 70 MB).
- Callers must pass the randoms only to `class_safety`; duplicate free
  variables are now rejected. `run_chain.py` passed `FREE` (which contained the
  first shares a second time); the reference tolerated it at an 8× cost, and it
  is fixed.

## Reproduce

```bash
uv run pytest -q experiments/labeller
uv run python experiments/labeller/measure.py          # ~1.5 min
bash experiments/oracle_crosscheck/setup_oracles.sh    # one-off, outside the repo
uv run python experiments/oracle_crosscheck/crosscheck.py --seed 1 --random 300
```

## Raw output

`PYTHONHASHSEED=0 uv run python experiments/labeller/measure.py`:

```
== single circuit: 12 gates, 2 secrets, k randoms ==
randoms  reference  bitsliced
      2     0.000s    0.0001s
      6     0.004s    0.0000s
     10     0.072s    0.0002s
     12     0.308s    0.0003s
     14     1.302s    0.0013s
     16          -    0.0040s
     20          -    0.0906s
     22          -    0.4636s
== chain e-graphs: label every class ==
depth rules bits classes  saturate    reference  bitsliced   speedup
    1  full    5      25      0.0s        0.00s     0.000s       11x
    2  core    8      42      0.0s        0.02s     0.000s       95x
    3  full   11    1039      1.1s        7.35s     0.006s    1,265x
    2  full    8    4353     52.3s        4.12s     0.023s      183x
    5  full   17    4315     16.8s   ~3370s est     0.405s    8,311x
labels identical wherever the reference labeller ran in full
```

Cross-check with RULE 1b (`--quiet`, summary lines):

```
### --random 20
cases=49  wires=703  safe_wires=649  conservative_tps_alarms=0  (2.6s)
RESULT: no violations.
### --seed 1 --random 300 --random-randoms 3 --random-gates 10
cases=329  wires=5429  safe_wires=5044  conservative_tps_alarms=7  (16.3s)
RESULT: no violations.
### --seed 2 --random 300 --random-randoms 1 --random-gates 6
cases=329  wires=3630  safe_wires=3232  conservative_tps_alarms=5  (15.1s)
RESULT: no violations.
### --seed 3 --random 300 --random-randoms 5 --random-gates 14
cases=329  wires=7221  safe_wires=6880  conservative_tps_alarms=6  (15.6s)
RESULT: no violations.
### --seed 4 --random 200 --random-randoms 2 --random-gates 20
cases=229  wires=5480  safe_wires=4648  conservative_tps_alarms=54  (10.9s)
RESULT: no violations.
```
