# Glitch feasibility probe — results

**Date:** 2026-10-18 · **ADR:** `design/0017` · **Status:** probe, not a claim

## Question

Does the project's story — unconstrained equality saturation is unsound;
security-constrained extraction repairs it — survive the **glitch-extended**
probing model, where a probe on a wire sees every stable signal (input or
register output) in its combinational cone? Go/no-go for extending the paper.

## Method

- `glitch.py` — in-house glitch-extended first-order checker. A wire's stable
  set is the inputs and registers in its cone; it is safe iff the joint
  distribution of that set is independent of the secrets, checked through
  all subset parities on bitsliced truth tables. Also gives the glitch-free
  per-wire verdict.
- `glitch_driver.py` — independent oracle: circuits rebuilt from VerifMSI's own
  `inputGate` / `xorGate` / `andGate` / `Register`, so the leakage sets are
  VerifMSI's `leakageOut`; each checked exactly with `getDistribWithExev`, plus
  VerifMSI's own `checkSecurity(1, withGlitches=True, 'tps')` per circuit.
- `probe.py` — fixtures: ISW and DOM without registers, DOM with its cross
  terms registered (VerifMSI `benchmarks/dom_and`), and a two-gadget registered
  DOM chain. egglog saturation (4 iterations) with the full Boolean rule set
  (comm, assoc, `x^x=0`, `x^0=x`, distributivity, factoring), registers either
  **opaque** (uninterpreted) or **transparent** (`reg(x) = x`, plus a register
  seeded on every gate operand). Cost = gates + registers.
- Extraction: egglog's own `extract` (U), egglog's `extract_multiple` k-best
  frontier (k = 30), and `gextract.py` — the occurrence-aware, term-based
  extractor of `design/0016` with the glitch checker as constraint (C, k = 8).

## Results

| Fixture (start) | Glitch-free | Glitch | Opaque: U | Transparent: U | Transparent: C |
|---|---|---|---|---|---|
| ISW, no registers (8) | secure | **leaks** | 7, leaks both | 7, leaks both | **10 = 8g + 2 reg, secure** |
| DOM, no registers (8) | secure | **leaks** | 5, leaks both | 5, leaks both | **10 = 8g + 2 reg, secure** |
| DOM, registered (10) | secure | secure | 10, unchanged | **5, leaks both** | 10, secure |
| DOM chain, registered (20) | secure | secure | 20, unchanged | **10, leaks both** | 20, secure |

With transparent registers, egglog's own k-best frontier (k = 30 per output)
held a glitch-secure circuit for the two single DOM gadgets (1 of 64 each) and
none for ISW (0 of 34) or the chain (0 of 784). With opaque registers the
frontier never contains a register it was not given.

**Trust boundary:** 10 distinct circuits, **167 probes, 0 disagreements** with
VerifMSI's exact check; VerifMSI's `checkSecurity` verdict agreed with ours on
all 10 circuits. The checker also matches a brute-force joint-distribution
reference on 150 random register circuits (`test_glitch.py`).

## Verdict: go — for the theory, not for gains

1. **The checker is trustworthy** in the glitch model at this scale.
2. **Opaque registers act as rewrite barriers.** Boolean rewriting cannot reach
   across them, so on registered gadgets it finds nothing cheaper and breaks
   nothing. Glitch-unregistered gadgets still leak, and rewriting makes them
   worse (DOM 8 → 5 gates, now leaking glitch-free too).
3. **Transparent registers reproduce the premise.** A register-oblivious
   optimizer drops every register because registers only add cost: registered
   DOM 10 → 5, chain 20 → 10, both leaking in both models.
4. **The repair is the refresh machinery.** With `reg(x) = x`, `reg(X)` is a
   self-loop in class X, exactly like `refresh` in `design/0016`, so
   one-node-per-class extraction (egglog's included) cannot place a register.
   The occurrence-aware term extractor can: it repairs unregistered ISW and DOM
   into glitch-secure circuits with two registers, and recovers the registered
   chain. Registers and refreshes are both value-preserving,
   leakage-changing operators handled by the same extraction.
5. **No gains.** Every glitch-secure result costs what the registered DOM
   construction costs (10 per gadget).

## What this does and does not show

**Shows:** the glitch model fits the shared-value / occurrence-aware framework
with only the checker swapped, and the soundness story reappears under the
(realistic) assumption that an optimizer treats registers as transparent.

**Does not show:**

- That any real synthesis or retiming tool treats registers as transparent;
  "transparent" is a modelling assumption standing in for a
  register-oblivious optimizer.
- Anything about pipelining or latency: registers here are only glitch
  barriers, with no timing semantics, and a repaired circuit's register
  placement is not checked for latency balance.
- Optimal or novel register placement: automatic register placement for
  glitch security exists in masking generators; run the citation check before
  claiming anything about it.
- Higher orders, PINI/composition, transitions or coupling: first order,
  2 shares, glitch-extended probes only.
- Scale: four small fixtures; the check costs `2**|stable set|` parity tests
  per probe.

## Known limitations

- The repaired ISW is a restructured circuit (`o1 = reg(reg(a1&b0 ^ r) ^
  a1&b1) ^ a0&b1`), not textbook ISW; it is correct by construction (each
  root is function-equal to the original output share) and verified.
- Roots are extracted separately (sound at first order: a probe lies in one
  cone), so subterms shared between outputs are not optimised jointly.
- Saturation is a fixed 4 iterations, not checked for a fixed point.
- The exported e-graph again uses egglog's private `_serialize`.

## Reproduce

```bash
uv run pytest -q experiments/glitch_probe
uv run python experiments/glitch_probe/probe.py            # ~15 s with the oracle
```

Mutation checks: checking only single-bit marginals instead of the joint
distribution (9 failures), disabling the extraction constraint (2).

## Raw output

`PYTHONHASHSEED=0 uv run python experiments/glitch_probe/probe.py`:

```

== isw (no registers)
   start            8 =  8g + 0reg  glitch-free: secure  glitch: LEAKS
   opaque      U    7 =  7g + 0reg  glitch-free: LEAKS   glitch: LEAKS
   opaque      egglog k-best: 28 circuits, 0 with a register, 0 glitch-secure
   opaque      C  no glitch-secure term (k=8)
   transparent U    7 =  7g + 0reg  glitch-free: LEAKS   glitch: LEAKS
   transparent egglog k-best: 34 circuits, 6 with a register, 0 glitch-secure
   transparent C   10 =  8g + 2reg  glitch-free: secure  glitch: secure
                  o0 = ((a0 & b0) ^ r)
                  o1 = (reg((reg(((a1 & b0) ^ r)) ^ (a1 & b1))) ^ (a0 & b1))

== dom (no registers)
   start            8 =  8g + 0reg  glitch-free: secure  glitch: LEAKS
   opaque      U    5 =  5g + 0reg  glitch-free: LEAKS   glitch: LEAKS
   opaque      egglog k-best: 36 circuits, 0 with a register, 0 glitch-secure
   opaque      C  no glitch-secure term (k=8)
   transparent U    5 =  5g + 0reg  glitch-free: LEAKS   glitch: LEAKS
   transparent egglog k-best: 64 circuits, 28 with a register, 1 glitch-secure
   transparent C   10 =  8g + 2reg  glitch-free: secure  glitch: secure
                  o0 = (reg(((a0 & b0) ^ z1)) ^ (a0 & b1))
                  o1 = (reg(((a1 & b1) ^ z1)) ^ (a1 & b0))

== dom (registered)
   start           10 =  8g + 2reg  glitch-free: secure  glitch: secure
   opaque      U   10 =  8g + 2reg  glitch-free: secure  glitch: secure
   opaque      egglog k-best: 4 circuits, 4 with a register, 4 glitch-secure
   opaque      C   10 =  8g + 2reg  glitch-free: secure  glitch: secure
                  o0 = ((a0 & b0) ^ reg(((a0 & b1) ^ z1)))
                  o1 = ((a1 & b1) ^ reg(((a1 & b0) ^ z1)))
   transparent U    5 =  5g + 0reg  glitch-free: LEAKS   glitch: LEAKS
   transparent egglog k-best: 64 circuits, 28 with a register, 1 glitch-secure
   transparent C   10 =  8g + 2reg  glitch-free: secure  glitch: secure
                  o0 = (reg(((a0 & b0) ^ z1)) ^ (a0 & b1))
                  o1 = (reg(((a1 & b1) ^ z1)) ^ (a1 & b0))

== dom chain (registered)
   start           20 = 16g + 4reg  glitch-free: secure  glitch: secure
   opaque      U   20 = 16g + 4reg  glitch-free: secure  glitch: secure
   opaque      egglog k-best: 36 circuits, 36 with a register, 36 glitch-secure
   opaque      C   20 = 16g + 4reg  glitch-free: secure  glitch: secure
                  o0 = ((((a0 & b0) ^ reg(((a0 & b1) ^ z1))) & d0) ^ reg(((((a0 & b0) ^ reg(((a0 & b1) ^ z1))) & d1) ^ z2)))
                  o1 = ((((a1 & b1) ^ reg(((a1 & b0) ^ z1))) & d1) ^ reg(((((a1 & b1) ^ reg(((a1 & b0) ^ z1))) & d0) ^ z2)))
   transparent U   10 = 10g + 0reg  glitch-free: LEAKS   glitch: LEAKS
   transparent egglog k-best: 784 circuits, 108 with a register, 0 glitch-secure
   transparent C   20 = 16g + 4reg  glitch-free: secure  glitch: secure
                  o0 = (reg((z2 ^ ((reg(((a0 & b0) ^ z1)) ^ (a0 & b1)) & d0))) ^ ((reg(((a0 & b0) ^ z1)) ^ (a0 & b1)) & d1))
                  o1 = (reg((z2 ^ ((reg(((a1 & b1) ^ z1)) ^ (a1 & b0)) & d1))) ^ ((reg(((a1 & b1) ^ z1)) ^ (a1 & b0)) & d0))

== VerifMSI cross-check (exact, per probe) and checkSecurity(glitches)
   isw (no registers)                           checkSecurity leaks=1   agrees
   isw (no registers) / opaque / U              checkSecurity leaks=1   agrees
   isw (no registers) / transparent / C         checkSecurity leaks=0   agrees
   dom (no registers)                           checkSecurity leaks=2   agrees
   dom (no registers) / opaque / U              checkSecurity leaks=2   agrees
   dom (no registers) / transparent / C         checkSecurity leaks=0   agrees
   dom (registered)                             checkSecurity leaks=0   agrees
   dom chain (registered)                       checkSecurity leaks=0   agrees
   dom chain (registered) / transparent / U     checkSecurity leaks=2   agrees
   dom chain (registered) / transparent / C     checkSecurity leaks=0   agrees
   10 circuits, 167 probes, 0 disagreements
```
