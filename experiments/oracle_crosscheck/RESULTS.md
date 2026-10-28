# Oracle cross-check results

**Question:** is the in-house first-order probing checker trustworthy, or does
it agree only with itself?

**Answer: yes, and it now agrees per-wire with an independent implementation on
21,760 wires across 1,216 circuits, with zero violations.** This closes the
trust boundary required by `design/0005`.

Reproduce:

```bash
bash experiments/oracle_crosscheck/setup_oracles.sh      # clones VerifMSI outside the repo
uv run python experiments/oracle_crosscheck/crosscheck.py --random 20
uv run python experiments/oracle_crosscheck/crosscheck.py --seed 1 --random 300 --random-randoms 3 --random-gates 10
```

## The oracle, and two traps in it

[VerifMSI](https://github.com/quentin-meunier/VerifMSI) (SECRYPT 2023) is an
independent implementation of the same property: a wire's value distribution
is independent of the secrets, with masks uniform. It is pure Python, GPLv3,
and lives **outside this repository**; we invoke it as an external process
(`AGENTS.md` §6.4).

Two traps were found by probing it rather than trusting its README:

1. **`checkTpsVal` returns a 3-tuple** `(res, usedBitExp, time)`. The README's
   `if res:` idiom is silently always-true. The driver reads `res[0]`.
2. **`checkTpsVal` is a sound but incomplete certificate**, not the exact
   property. Over 400 random expressions: `tps=True` never contradicted
   exhaustive independence, but `tps=False` did sometimes (false alarms).
   The exact function is `getDistribWithExev(e)` → `(uniform, independent)`;
   its second component is the property our checker implements.

Had we compared only against `checkTpsVal`, we would have reported ~72
"disagreements" that were VerifMSI's conservatism, not our bugs — and, worse,
might have "resolved" them by weakening our checker. This is why the oracle had
to be characterised, not just invoked.

## Protocol

Per wire, three checks:

| Rule | Statement | On failure |
|---|---|---|
| 1 (two-sided) | our verdict == VerifMSI exact `independent` | **violation** |
| 2 (internal) | `tps=True` ⇒ exact `independent=True` | **violation** |
| 3 (one-sided) | `tps=True` ⇒ our verdict is safe | **violation** |
| info | `tps=False` while exact says independent | counted (conservatism) |

Rule 1 is the strong one: two independently written exhaustive decisions
agreeing on every wire. Rule 3 protects the dangerous direction — a symbolic
proof of independence must never contradict us.

## Results

| Seed | randoms | gates | circuits | wires | all-safe | tps conservatism | violations |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 (smoke) | 3 | 10 | 49 | 703 | 28 | 0 | 0 |
| 1 | 3 | 10 | 329 | 5,429 | 271 | 7 | 0 |
| 2 | 1 | 6 | 329 | 3,630 | 269 | 5 | 0 |
| 3 | 5 | 14 | 329 | 7,221 | 274 | 6 | 0 |
| 4 | 2 | 20 | 229 | 5,480 | 172 | 54 | 0 |
| **total** | | | **1,265** | **22,463** | | **72** | **0** |

(The 1,216 figure quoted at the top excludes the smoke run.)

**Families:**

1. **Hand fixtures** (5): masked buffer, ISW AND, DOM AND (transcribed from
   VerifMSI's own `generate_dom_and.py`), wrong-order ISW (insecure),
   naive unmasked intermediate (insecure). All agree; all match the expected
   verdicts. The DOM match independently validates the transcription.
2. **ISW reassociation variants** (24): the *same Boolean function* built by
   left-folding the four c1 summands in every permutation. Verdicts split
   **10 secure / 14 insecure** — the cross-check sits exactly on the
   secure/insecure boundary, where a checker bug would be most likely to hide.
   Both tools agree on every wire of all 24.
3. **Random circuits** (1,236): random XOR/AND DAGs over two 2-share secrets
   and 1–5 randoms, 6–20 gates. All agree.

Conservatism scales with expression depth (0 → 54 as gates go 10 → 20),
consistent with a symbolic analysis needing more algebraic simplification
power, not with any change in the exact verdicts.

## What this establishes

- The in-house checker is **independently corroborated** on the exact property
  it implements, in both directions, over a large and adversarially chosen set.
- The dangerous failure mode (our checker says safe where the wire leaks)
  is now guarded by two independent implementations plus a sound symbolic
  certificate.
- The original premise-test conclusions stand: secure fixtures are secure,
  leaking fixtures are caught, and the wrong-order ISW fixture is genuinely
  insecure rather than an artifact of our checker.

## Limitations

- First order, 2 shares, glitch-free only — matched by the oracle configuration
  used here. No claim about robust/glitch probing or higher orders.
- The oracle's exact function is exhaustive, so it is exact for 1-bit widths;
  this is the same regime as our circuits, but it would not scale unchanged to
  wide words.
- VerifMSI's models were exercised through our translation (shares →
  `mask`/`secret ^ mask`). The translation is faithful for 2 shares and was
  sanity-checked by the DOM fixture; it is not a general-purpose bridge.
- The conservatism count is a property of VerifMSI's simplifier, not a
  measure of our precision; no attempt was made to characterise it beyond the
  400-expression probe.

## Raw summary

```
cases=329  wires=5429  safe_wires=5044  conservative_tps_alarms=7   (10.7s)
RESULT: no violations.
cases=329  wires=3630  safe_wires=3232  conservative_tps_alarms=5   (10.0s)
RESULT: no violations.
cases=329  wires=7221  safe_wires=6880  conservative_tps_alarms=6   (12.0s)
RESULT: no violations.
cases=229  wires=5480  safe_wires=4648  conservative_tps_alarms=54  (8.1s)
RESULT: no violations.
```

## Update 2026-10-07 — RULE 1b: the bitsliced labeller

`compare()` now also checks the bitsliced labeller (`experiments/labeller/`,
`design/0015`) against VerifMSI's exact independence on every wire (RULE 1b).
All five configurations above were rerun: identical case, wire and
conservatism counts, and **0 violations** for both the original checker and the
bitsliced labeller (1,265 circuits / 22,463 wires). A deliberately wrong
labeller was confirmed to trip RULE 1b. Raw summary lines are in
`experiments/labeller/RESULTS.md`.

## Extended cross-check (`extended.py`, step `F13`)

Two circuit sets had been decided by the in-house exact checker alone. `extended.py`
regenerates both exactly (same rules, k and seed) and applies the protocol above to every
wire:

| Set | Circuits | Wires | Circuits with a leaking wire | Disagreements |
|---|---|---|---|---|
| k-best extractions of the two-gadget ISW chain (F4) | 240 | 6,054 | 240 | 0 |
| Random PINI-built terms (F11, section 3, seed 19) | 234 | 4,608 | 0 | 0 |

So VerifMSI confirms both headline facts independently: none of the 240 sampled chain
extractions is secure, and none of the 234 PINI-built terms leaks.
