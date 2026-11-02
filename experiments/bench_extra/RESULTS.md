# bench_extra: head-to-head with AGEMA and COMPRESS, no-e-graph baseline, seqc area

## Questions

1. Does seqc need fewer masked AND gadgets (and less area) than AGEMA and COMPRESS on
   programs larger than the first six?
2. Do seqc's savings need equality saturation, or does a plain logic minimiser give the same
   AND count?
3. What is the Nangate45 area of seqc's own Verilog?

## Method

Twelve programs: the six of the paper's first table (`frontend/examples/*.sec`,
`large/majority_or.sec`) and six larger ones (`frontend/complex/*.sec`). Two shares, first
order. **Every number here, including every timing, was produced on one machine**: Linux
7.3 (CachyOS) x86_64, AMD Ryzen 5 5500U, 12 threads, 5.6 GB RAM.

| Tool | Version | How it was run |
|---|---|---|
| Yosys | 0.70+290 (oss-cad-suite 2026-11-02), GHDL 7.0.0-dev, Icarus 14.0 | Nangate45 library from the COMPRESS repository, 1 GE = 0.798 um^2 |
| COMPRESS | `cassiersg/compress` commit `26ccd9c`, Python 3.13 venv, ortools 9.14 | `make CIRCUIT=<c> LATS="2 3 4" DS=2 area`, default gadget library (`gadgets_opt.toml`); behavioural simulation on (cocotb 2.0.1 + Icarus) |
| AGEMA | `Chair-for-Security-Engineering/AGEMA` commit `3de80c1`, built from source (gcc 16, Boost 1.73 headers, ABC `77875a3`, CUDD `f54f533`, Sylvan `5e9da97`) | Yosys front end (`Yosys/sythesize.ys`), then `AGEMA -mt naive -sc HPC2|HPC3 -so 1`, default options |
| seqc | this repository | `seqc_gadgets.py` (default `k = 8`; `mux4` and `ascon_sbox` with `--k 2 --iters 4`) |

- **COMPRESS input:** `sec2compress.py` writes the logic as written (shared subterms once, `|` as
  `x ^ y ^ (x & y)`). **"On seqc's logic":** `seqc2compress.py` writes seqc's security-enforced
  term, each gadget as an AND and `refresh` as the identity.
- **AGEMA input:** `sec2agema.py` writes an annotated Verilog module (`din` secure bus, `dout`
  bus). **AGEMA area:** `agema_area.py` reads AGEMA's own VHDL gadgets with the GHDL plugin of
  Yosys, flattens, maps to Nangate45 and reports the area of the whole generated design,
  registers included. This replaces the earlier estimate that summed COMPRESS's gadget areas.
- **seqc area:** `synth_area.py` (the COMPRESS flow, same result as COMPRESS's own `synth.tcl`)
  on `seqc --emit verilog`. The Verilog is glitch-free combinational logic, no registers, no
  random-number generator.
- **No-e-graph baseline:** `baseline_noegraph.py`, Yosys `synth` + `abc -g AND,XOR`.
- **Gadgets:** COMPRESS: `MSKand*` + `MSKg4mul*` instances in `stats.json`; AGEMA: HPC2 fresh
  masks (one per gadget; HPC3 uses two); seqc: distinct `isw`/`dom`/`hpc1` subterms.

## Sanity check against the earlier table

The six old programs reproduce **exactly** the COMPRESS rows of the earlier head-to-head (gadgets,
random bits, area at the best latency): 148.0, 70.3, 148.7, 167.3, 152.0, 282.3 GE, and the
"COMPRESS on seqc's logic" cells 81.7, 108.3 and 290.7. The earlier AGEMA estimates (73.3, 4.0,
208.7, 238.7, 300.0, 300.0) are within 5% of the measured values below (73.0, 4.0, 207.0, 237.3,
285.0, 285.0). The earlier seqc area column
(17.3, 21.3, 21.3, 38.7, 34.7, 64.7 GE) is **not** reproduced: this flow, and COMPRESS's own
`synth.tcl`, give 12.0, 16.7, 16.0, 32.0, 22.0, 59.7. The seqc column is replaced; I could not
identify what the earlier flow did differently.

## Results (gadgets / fresh random bits; area in GE)

| Program | seqc | seqc area | AGEMA (HPC2) | AGEMA area (best of HPC2, HPC3) | COMPRESS (best latency) | COMPRESS area | COMPRESS on seqc's logic |
|---|---|---:|---|---:|---|---:|---|
| a&b ^ a&c | 1 / 1 | 12.0 | 1 / 1 | 73.0 | 2 / 2 (l2) | 148.0 | 81.7 (-45%) |
| z&z, z=a^b | 1 / 2 | 16.7 | 0 / 0 | 4.0 | 1 / 1 (l2) | 70.3 | 70.3 |
| multiplexer | 1 / 1 | 16.0 | 3 / 3 | 207.0 | 2 / 2 (l2) | 148.7 | 108.3 (-27%) |
| full adder | 2 / 2 | 32.0 | 3 / 3 | 237.3 | 2 / 2 (l2) | 167.3 | 167.3 |
| majority, 2 AND | 2 / 2 | 22.0 | 4 / 4 | 285.0 | 2 / 2 (l2) | 152.0 | 152.0 |
| majority, OR form | 4 / 4 | 59.7 | 4 / 4 | 285.0 | 5 / 9 (l3) | 282.3 | 290.7 (+3%), rnd 6 |
| 2-bit comparator | 4 / 4 | 66.3 | 8 / 8 | 517.7 | 4 / 5 (l2) | 275.0 | 279.0 (+1%) |
| 2-bit adder | 4 / 4 | 73.0 | 6 / 6 | 543.7 | 4 / 6 (l2) | 302.0 | 302.0 |
| 2x2 multiplier | 7 / 8 | 58.7 | 6 / 6 | 421.7 | 6 / 10 (l3) | 374.7 | 420.0 (+12%) |
| 4:1 multiplexer (k=2) | 3 / 3 | 53.3 | 9 / 9 | 641.3 | 3 / 5 (l2) | 213.0 | 213.0 |
| Ascon S-box (k=2) | 5 / 5 | 98.0 | 11 / 11 | 937.0 | 5 / 5 (l2) | 440.3 | 411.7 (-6%) |
| PRESENT S-box | 8 / 8 | 133.7 | 24 / 24 | 1753.7 | 9 / 11 (l2) | 627.0 | 555.7 (-11%) |

AGEMA HPC2 area (not the best): 103.7, 4.0, 299.0, 352.7, 425.3, 425.3, 767.0, 840.3, 629.7,
954.0, 1459.7, 2716.0. Raw: `h2h/raw/`. Latency 2 has no schedule for the multiplier and the
OR-form majority (COMPRESS reports UNSAT), so those two ran with latencies 3 and 4.

- **Gadgets:** seqc needs no more than both tools on 10 of 12 programs; strictly fewer than
  AGEMA on 8 (ties on 2: `a&b ^ a&c`, OR-form majority) and strictly fewer than COMPRESS on 4
  (ties on 7). Exceptions: `z & z` (AGEMA's synthesis applies `x & x = x`, 0 gadgets) and the
  multiplier (seqc 7, AGEMA 6, COMPRESS 6).
- **COMPRESS on seqc's logic:** smaller on 4 programs, equal on 5, larger on 3 (multiplier +12%,
  OR-form majority +3% with random bits 9 -> 6, comparator +1%).

### No-e-graph baseline (AND count)

| Program | AND as written | after Yosys/ABC | seqc |
|---|---:|---:|---:|
| a&b ^ a&c | 2 | 1 | 1 |
| z&z | 1 | 0 | 1 |
| multiplexer | 2 | 3 | 1 |
| full adder | 2 | 3 | 2 |
| majority, 2 AND | 2 | 4 | 2 |
| majority, OR form | 5 | 4 | 4 |
| 2-bit comparator | 4 | 8 | 4 |
| 2-bit adder | 4 | 6 | 4 |
| 2x2 multiplier | 6 | 6 | 7 |
| 4:1 multiplexer | 3 | 9 | 3 |
| Ascon S-box | 5 | 13 | 5 |
| PRESENT S-box | 9 | 26 | 8 |

seqc needs strictly fewer ANDs than ABC on 8 programs, ties on 2, and ABC needs fewer on 2
(`z & z` and the multiplier). ABC goes above the as-written count on 8 of 12 because it maps for
area, not for the number of ANDs.

### Timings (this machine, one run at a time)

| What | Time |
|---|---|
| AGEMA, one run | 8-17 ms |
| COMPRESS solver, all latencies tried | 0.04-0.68 s |
| seqc, factor / square / mux / adder / majority | 0.0 / 0.2 / 0.1 / 0.1 / 0.1 s |
| seqc, OR majority / cmp2 / add2 / mul2 / mux4 (k=2) / Ascon (k=2) / PRESENT | 83 / 27 / 75 / 6 / 8 / 14 / 132 s |
| ISW chain depth 3 / 4 / 5, per-term extraction | 0.3 / 5.4 / 133 s |
| Labeller depth 5: bit-parallel / reference | 0.409 s / ~3686 s (estimated) |
| PINI composition, chi 32-bit / ISW chain depth 15 | 0.05 s / 0.01 s |
| Full verification, 16 steps (`findings/verify.py --full`) | see `timing/verify_full.txt` |

Raw: `timing/`. Each was run alone; load before and after is in `timing/machine.txt`.

## What this does and does not show

- seqc's gadget counts beat AGEMA's and match or beat COMPRESS's on most programs, but the
  comparison is **not like for like in security**: seqc outputs first-order, glitch-free logic
  (no registers), AGEMA and COMPRESS output glitch-robust pipelined designs. The gadget count
  is the cost metric all three share; the areas are not directly comparable.
- The areas of AGEMA and COMPRESS include registers and (COMPRESS: `area_ge`, excluding its
  random-number generator) differ in what they include; `area_ge_wrng` is in the raw CSVs.
- The no-e-graph baseline is weak (ABC is not a multiplicative-complexity minimiser). A
  dedicated minimiser could do better than ABC and might match seqc on some programs.
- Twelve small programs, two shares, first order. The Ascon and 4:1 mux seqc rows use `k = 2`
  (the default `k = 8` did not finish in 40 minutes); stability across `k` was not re-checked.
- Behavioural simulation only (COMPRESS's structural simulation is not run by its Makefile).

## Deviations and workarounds (so the run can be repeated)

- **COMPRESS testbench:** `scripts/sim_tb.py` crashed on one-bit ports under cocotb 2.0.1
  (`'LogicObject' object has no attribute 'left'`); the one-line fix is `h2h/sim_tb.patch`.
  The oss-cad-suite simulator needs its own Python 3.11 cocotb (`pip install --target`), run
  with `PYTHONPATH`; the COMPRESS script itself runs in a 3.13 venv (`h2h/scripts/`).
- **AGEMA front end:** Yosys re-declares ports as `wire clk;` etc., which makes AGEMA treat the
  clock as an ordinary signal and abort its depth check; those lines, and Yosys's `keep_hierarchy`
  and `src` attributes, are stripped (`run_agema.sh`). AGEMA's parser also finds nothing behind a
  one-bit output bus, so a lone output is duplicated onto a second bit (`sec2agema.py`); this
  adds one buffer and no gadgets.
- **AGEMA build:** needed `-Wno-error`, `-include cstdint`, `-fopenmp`, the CUDD C++ interface
  (`--enable-obj`) and Sylvan headers copied to `inc/sylvan` (`h2h/scripts/build_agema_deps.sh`).
- **Area synthesis of AGEMA's output:** each VHDL gadget is imported with the GHDL plugin,
  flattened and stashed separately (the plugin keeps `-g` settings between calls, so entities
  without generics are imported first).
- The first parallel COMPRESS runs shared one working directory and a loaded machine; all
  numbers above come from those runs' outputs (areas, gadgets, random bits are deterministic) and
  all timings from the one-at-a-time pass (`timing/`, `h2h/raw/compress_quiet/`).

## Where the timings live

`findings/outputs/` still holds the committed outputs of an earlier machine (Windows 11), with
its own timings. The outputs of this machine's full verification run (14 of 16 steps pass; G1
and G2 fail only because ruff also scans the untracked `.agents/` and `.claude/skills/kaggle`
folders; they pass with those excluded) are in `timing/verify_outputs/`. The paper reports this
machine's timings only.
