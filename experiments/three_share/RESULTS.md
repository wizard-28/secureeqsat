# Does Finding 1 survive with more than two shares?

## Question

At two shares, the only gate-saving rewrite of the ISW gadget (factoring) puts a secret back
together: `b0 ^ b1 = b`. With `d >= 3` shares `b0 ^ b1` is no longer the secret. Does a
cost-only optimiser still return a leaking circuit, and are there now *secure* savings?

## Method

`shares.py` (stdlib only, no e-graph). The Boolean rewrites of Finding 1 (commute, associate,
factor) act on a flat XOR of leaves, so their closure is enumerated directly:

- The `d`-share ISW AND has output `c_i = a_i b_i ^ XOR_{j != i} z_ij`, with `z_ij = r_ij`
  (`i < j`) and `z_ji = (r_ij ^ a_i b_j) ^ a_j b_i`.
- A *plan* partitions one output's products into blocks: a lone product, or a set of >= 2
  products sharing an a-index or a b-index (the factoring rule).
- Cost = ANDs (blocks) + XORs inside blocks + (atoms - 1) combining XORs. Reassociation
  changes security, not cost.
- Glitch-free first-order security of a wire depends only on its function (design/0006), so
  each wire is checked once from its truth table over all secrets and free bits. A plan is
  secure iff every block-internal XOR, every atom and some XOR tree over the atoms has only
  safe nodes (subset DP).

Run: `uv run python experiments/three_share/shares.py 2 3 4`.

## Results (gates; per-output costs summed)

| shares d | plain ISW | cheapest, security ignored | cheapest secure | cheapest forced to leak? |
|---:|---:|---:|---:|---|
| 2 | 8 | 7 | 8 | yes (c1) |
| 3 | 21 | 17 | 18 | yes (c2) |
| 4 | 40 | 31 | 32 | yes (c3) |

At `d = 2` the numbers reproduce the paper's 8 / 7 / 8. At `d = 3, 4`:

- A cost-only optimiser still picks a leaking circuit (one gate cheaper than the best secure
  one), because the last output share has all `d` products with one a-index: factoring them
  gives `a_{d-1} (b_0 ^ ... ^ b_{d-1}) = a_{d-1} b`.
- Unlike `d = 2`, **secure savings now exist**: 21 -> 18 and 40 -> 32. Partial factorings
  such as `a_2 (b_0 ^ b_1)` are safe because `b_0 ^ b_1` is a uniform bit at `d = 3`.
- So the paper's sentence "every gate-saving factoring puts a secret back together" is a
  **two-share statement** and must stay scoped as such. The weaker statement "the cheapest
  cost-only circuit leaks" survives to `d = 4` in this model.

## Tests

`test_three_share.py` (4 tests): outputs reconstruct `a & b` for d = 2..4; d = 2 reproduces
8 / 7 / 8; `b0 ^ b1` leaks at d = 2 and is safe at d = 3 (`b0 ^ b1 ^ b2` leaks), checked
against an independent brute-force enumeration; the d = 3, 4 table above.

`experiments/resharing/test_leak_cut_exhaustive.py`: bounded exhaustive check of the
leak-cut proposition: 2,204 leaking terms (all terms over {a, b} with up to 3 operators,
unary `not`/`refresh`, binary `xor`/`isw`/`dom`/`hpc1`), each wrapped in 26 one-step
contexts (57,304 checks), zero counterexamples.

## What this does and does not prove

- It shows, **in our in-house checker**, that the *qualitative* finding (cost-only picks a
  leak) is not a two-share artefact for the ISW structure, and that the "always" claim is.
- **VerifMSI cross-check done (2026-11-02):** the cheapest-secure and a cost-only circuit were
  built as real netlists (`build_circuit`, with gates shared across outputs) for d = 2, 3, 4 and
  every wire checked by the in-house truth-table check and by VerifMSI's exact check (driver
  generalised to d shares, d = 2 unchanged): 0 disagreements, 0 certificate contradictions.
  Real gate counts (sharing across outputs counted once): d = 2: 8 secure / 7 cost-only;
  d = 3: 17 secure / 16 cost-only (plain ISW 21); d = 4: 28 secure / 27 cost-only (plain 40).
  The cost-only circuits each contain 3 leaking wires. The per-output table above is the
  pessimistic variant without cross-output sharing. Test:
  `test_built_circuits_agree_with_verifmsi` (skips if VerifMSI is absent).
- Still not covered: higher-order probing (d shares only against one probe), glitch-extended model,
  DOM/HPC structure, refresh insertion, and cross-output sharing is only in the built netlists, not in the search (the search is per output).
- The exhaustive leak-cut test is bounded (size <= 3), not a proof; a machine-checked proof
  needs a prover the dev container does not provide (would require editing
  `.devcontainer/devcontainer.json`, a human decision).

## Cross-check output

```
d=2 secure gates=8  wires=13 leaking=0 disagreements=0 cert-contradictions=0
d=2 any    gates=7  wires=12 leaking=3 disagreements=0 cert-contradictions=0
d=3 secure gates=17 wires=26 leaking=0 disagreements=0 cert-contradictions=0
d=3 any    gates=16 wires=25 leaking=3 disagreements=0 cert-contradictions=0
d=4 secure gates=28 wires=42 leaking=0 disagreements=0 cert-contradictions=0
d=4 any    gates=27 wires=41 leaking=3 disagreements=0 cert-contradictions=0
```

## Raw output

```
d  baseline  min(any)  min(secure)  outputs: [any/secure, plans, secure]
2         8         7            8  c0: 2/2 (1/1); c1: 5/6 (1/3) LEAK-forced
3        21        17           18  c0: 3/3 (1/1); c1: 6/6 (3/3); c2: 8/9 (12/16) LEAK-forced
4        40        31           32  c0: 4/4 (1/1); c1: 7/7 (3/3); c2: 9/9 (16/16); c3: 11/12 (115/125) LEAK-forced
```
