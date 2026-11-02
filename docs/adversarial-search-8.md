# Adversarial search 8: independent re-check of the congruence claim and the 338/16 count

Date: 2026-11-02. Trigger: the team asked for the two items to be re-verified from scratch, not from
the earlier records.

## 338 / 16 recount (own code, `experiments/bench_extra/dag_extractions.py`)

Enumeration of every acyclic one-node-per-class extraction of `square`, then the in-house checker:

| Rule set | Extractions | Secure |
|---|---:|---:|
| R3 | 1 | 0 |
| R1 + R3 | 338 | 16 |
| R2 + R3 | 3 | 1 (`hpc1(a^b, a^b)`) |
| R1 + R2 + R3 | 8,502 | 2,226 |

`design/0021` is confirmed (338 / 16 under R1 + R3). The paper's earlier sentence ("with all three rule
groups, 16 of the 338") was wrong. Not cross-checked against VerifMSI here (the earlier cross-check in
`design/0021` covers the 16).

## Congruence claim: fresh queries (web search, US index, snippet-based)

1. `e-graph equality saturation masked circuits refresh re-sharing not a congruence probing security`
2. `superVer verifying probabilistic independence of systems of expressions using equality saturation EGRAPHS 2024`
3. `equality saturation rewrite rules that are not congruences unsound e-graph "randomness" OR "probabilistic" OR "shares" masked implementation`
4. `"equality saturation" OR "e-graph" "side-channel" masking countermeasure rewrite security-preserving optimization compiler 2025 2026`

Result: no source combines e-graphs with the argument that re-sharing is not a congruence. Only
superVer (EGRAPHS 2024 work in progress; page read, abstract only) uses e-graphs for a masking-related
property (probabilistic independence); its page does not mention refreshing, rewrites that change
randomness, or congruence. Other hits: Eldib and Wang (SMT-based masking synthesis, 2014), an e-graph
paper on Boolean FHE circuits (no masking), refresh-gadget papers (no e-graphs). **Not read:** the
superVer full text, which may say more. Confidence: medium-high, as in `docs/adversarial-search-6.md`.
