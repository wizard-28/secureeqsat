# Front end: source programs to masked netlists

**Question.** Can the pipeline be driven from a source program, end to end, and still
produce circuits that are functionally correct and first-order secure? (`design/0020`.)

**Why this exists.** Every earlier experiment started from a hand-written shared-value
term. A compiler needs a front end that reads a program and a back end that emits code. This
adds both, around the pipeline unchanged: egglog saturation (R1 to R3), then unconstrained
and security-constrained extraction (`design/0016`), then the exact checker and VerifMSI.

## Method

A program is a few lines of Boolean code (`lang.py`):

```
input a, b, c
out y = (a & b) ^ (a & c)
```

`seqc.py` runs these stages and prints each one:

1. **parse**: hand-written recursive descent; errors carry a line and column.
2. **mask**: `&` becomes an ISW gadget, `^` a share-wise XOR, `~` a share-wise NOT, `|`
   is `x ^ y ^ (x & y)`. Policy `refresh` (default) refreshes the gadget's second operand,
   which makes the two operand sharings independent; policy `naive` does not.
3. **optimise**: saturate, then extract twice, with security ignored and with security
   enforced, so the cost of the constraint is visible.
4. **verify**: the term equals the source on all inputs; the lowered circuit reconstructs the
   outputs over every secret and every free assignment; the exact first-order check; and
   `--crosscheck` runs VerifMSI on every wire.
5. **emit**: `--emit netlist` or `--emit verilog`. The Verilog header states that the logic is
   glitch-free-model only and is not glitch-extended secure.

Programs: `examples/*.sec`. Run: `uv run python experiments/frontend/seqc.py <file>`.

## Results

Costs are gates plus random bits (`design/0016`).

| Program | Policy | Start | Security ignored | Security enforced | VerifMSI |
|---|---|---|---|---|---|
| `factor`: `a&b ^ a&c` | refresh | 26 | 11, secure | 11, secure | 17 wires, 0 disagreements |
| `square`: `z & z`, `z = a^b` | refresh | 14 | **11, LEAKS** | 14, secure | 18 wires, 0 disagreements |
| `square` | naive | **11, LEAKS** | **11, LEAKS** | 14, secure | 18 wires, 0 disagreements |
| `mux`: `s ? a : b` | refresh | 27 | 13, secure | 13, secure | 19 wires, 0 disagreements |
| `adder`: full adder, 2 outputs | refresh | 30 | 24, secure | 24, secure | 30 wires, 0 disagreements |
| `majority`: `(a&b) ^ (c&(a^b))` | refresh | 28 | 22, secure | 22, secure | 28 wires, 0 disagreements |

Every compiled circuit is functionally equal to its source on all inputs, and has 0 leaking
wires under the in-house exact checker. The test suite (`test_frontend.py`, 54 tests, about
1.6 s) checks this, the parser, the emitted netlist and Verilog (evaluated against the
program), and the VerifMSI agreement.

The larger form `(a&b) | (b&c) | (a&c)` desugars to five AND gadgets: start cost 65, optimised
to 41, and **about 78 s to compile**. That is the term-based extraction limit of
`design/0016`, not a front-end cost.

## What this shows

- The project runs from source to emitted netlist on real programs, with every stage visible.
- On the one program where the optimiser is tempted (`square`), the headline result holds on
  a compiled program: the cheapest equivalent circuit (11) leaks, and the constrained one (14)
  keeps the refresh.
- The `naive` policy produces a leaking start on `square`; the constrained stage repairs it.
- Starting from a conservatively refreshed program, the optimiser removes substantial slack
  (26 to 11 on `factor`).

## What this does not show

- **No new research claim.** The front end changes no result; it makes the pipeline usable.
- **No claim that the `refresh` policy is secure in general.** Refreshing the second operand
  makes the two operand encodings independent, and every program above was checked exactly,
  but this is argued, not proved, and should not be extended to larger programs unchecked.
- **Not glitch-secure.** The gadget choice (the optimiser picks DOM or ISW freely, which the
  glitch-free model treats as equal) elides DOM's registers. The emitted Verilog is
  combinational logic that is secure only in the glitch-free model (`design/0017`, `0018`).
- Only the constrained stage mattered for security in these examples; in the other five the
  unconstrained optimum was already secure, because a secure start plus value-sound rules
  tends to stay secure unless a refresh can be dropped.

## Known limitations

- Term-based extraction is slow beyond a few gadgets (`design/0016`); the CLI warns above four
  AND-class operations.
- No constants (a share-wise constant has no sharing); `~x` is supported.
- First order, 2 shares, straight-line, single-bit values; no loops or word-level operators.
- Names `r`, `r1`, ... and names starting with `_` are reserved for generated signals.
- Idempotence (`x & x = x`) is deliberately absent from the rules (`design/0016`), so `z & z` is
  compiled as a gadget, not simplified to `z`.

## Raw output

```
$ seqc.py examples/factor.sec --crosscheck
program  3 inputs, 1 outputs, 2 AND, 1 XOR in the source
mask     policy=refresh
  start                    cost  26 = 22g + 4r  secure           xor(isw(a, refresh(b)), isw(a, refresh(c)))
optimise 7 e-classes after saturation (0.02s)
  security ignored         cost  11 = 10g + 1r  secure           dom(a, xor(b, c))
  security enforced        cost  11 = 10g + 1r  secure           dom(a, xor(b, c))
verify
  function equals the source on all inputs   ok
  lowered circuit reconstructs the outputs   ok
  first-order check, in-house exact          0 leaking wires
  VerifMSI cross-check                       17 wires, 0 disagreements

$ seqc.py examples/square.sec --crosscheck
program  2 inputs, 1 outputs, 1 AND, 2 XOR in the source
mask     policy=refresh
  start                    cost  14 = 12g + 2r  secure           isw(xor(a, b), refresh(xor(a, b)))
optimise 19 e-classes after saturation (0.02s)
  security ignored         cost  11 = 10g + 1r  LEAKS (2 wires)  dom(xor(a, b), xor(a, b))
  security enforced        cost  14 = 12g + 2r  secure           dom(refresh(xor(a, b)), xor(a, b))
  -> the cheapest equivalent circuit leaks; security costs 3 here
verify
  function equals the source on all inputs   ok
  lowered circuit reconstructs the outputs   ok
  first-order check, in-house exact          0 leaking wires
  VerifMSI cross-check                       18 wires, 0 disagreements

$ seqc.py examples/mux.sec --crosscheck
program  3 inputs, 1 outputs, 2 AND, 1 XOR in the source
mask     policy=refresh
  start                    cost  27 = 23g + 4r  secure           xor(isw(s, refresh(a)), isw(not(s), refresh(b)))
optimise 11 e-classes after saturation (0.02s)
  security ignored         cost  13 = 12g + 1r  secure           xor(b, dom(s, xor(a, b)))
  security enforced        cost  13 = 12g + 1r  secure           xor(b, dom(s, xor(a, b)))
verify
  function equals the source on all inputs   ok
  lowered circuit reconstructs the outputs   ok
  first-order check, in-house exact          0 leaking wires
  VerifMSI cross-check                       19 wires, 0 disagreements

$ seqc.py examples/adder.sec --crosscheck
program  3 inputs, 2 outputs, 2 AND, 4 XOR in the source
mask     policy=refresh
  start                    cost  30 = 26g + 4r  secure           out(xor(xor(a, b), cin), xor(isw(a, refresh(b)), isw(cin, refresh(xor(a, b)))))
optimise 15 e-classes after saturation (0.02s)
  security ignored         cost  24 = 22g + 2r  secure           out(xor(cin, xor(a, b)), xor(dom(a, b), dom(cin, xor(a, b))))
  security enforced        cost  24 = 22g + 2r  secure           out(xor(cin, xor(a, b)), xor(dom(a, b), dom(cin, xor(a, b))))
verify
  function equals the source on all inputs   ok
  lowered circuit reconstructs the outputs   ok
  first-order check, in-house exact          0 leaking wires
  VerifMSI cross-check                       30 wires, 0 disagreements

$ seqc.py examples/majority.sec --crosscheck
program  3 inputs, 1 outputs, 2 AND, 2 XOR in the source
mask     policy=refresh
  start                    cost  28 = 24g + 4r  secure           xor(isw(a, refresh(b)), isw(c, refresh(xor(a, b))))
optimise 13 e-classes after saturation (0.02s)
  security ignored         cost  22 = 20g + 2r  secure           xor(dom(a, b), dom(c, xor(a, b)))
  security enforced        cost  22 = 20g + 2r  secure           xor(dom(a, b), dom(c, xor(a, b)))
verify
  function equals the source on all inputs   ok
  lowered circuit reconstructs the outputs   ok
  first-order check, in-house exact          0 leaking wires
  VerifMSI cross-check                       28 wires, 0 disagreements

$ seqc.py examples/square.sec --policy naive --crosscheck
program  2 inputs, 1 outputs, 1 AND, 2 XOR in the source
mask     policy=naive
  start                    cost  11 = 10g + 1r  LEAKS (2 wires)  isw(xor(a, b), xor(a, b))
optimise 20 e-classes after saturation (0.02s)
  security ignored         cost  11 = 10g + 1r  LEAKS (2 wires)  dom(xor(a, b), xor(a, b))
  security enforced        cost  14 = 12g + 2r  secure           dom(refresh(xor(a, b)), xor(a, b))
  -> the cheapest equivalent circuit leaks; security costs 3 here
verify
  function equals the source on all inputs   ok
  lowered circuit reconstructs the outputs   ok
  first-order check, in-house exact          0 leaking wires
  VerifMSI cross-check                       18 wires, 0 disagreements

$ seqc.py examples/mux.sec --emit verilog
// Generated by seqc (design/0020).
// Model: first-order probing security, 2 shares, GLITCH-FREE.
// This is plain combinational logic: it is NOT glitch-extended secure
// (design/0017, 0018). Input shares are <name>_s0, <name>_s1; the rnd<i>
// inputs must be fresh uniform random bits.
module masked (
    input  b_s0,
    input  b_s1,
    input  s_s0,
    input  s_s1,
    input  a_s0,
    input  a_s1,
    input  rnd1,
    output y_s0,
    output y_s1
);
  wire _w1 = a_s0 ^ b_s0;
  wire _w2 = a_s1 ^ b_s1;
  wire _w3 = s_s0 & _w2;
  wire _w4 = _w3 ^ rnd1;
  wire _w5 = s_s1 & _w1;
  wire _w6 = _w5 ^ rnd1;
  wire _w7 = s_s0 & _w1;
  wire _w8 = _w7 ^ _w4;
  wire _w9 = s_s1 & _w2;
  wire _w10 = _w9 ^ _w6;
  wire _w11 = b_s0 ^ _w8;
  wire _w12 = b_s1 ^ _w10;
  assign y_s0 = _w11;
  assign y_s1 = _w12;
endmodule
```
