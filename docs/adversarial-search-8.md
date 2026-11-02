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

## Reference check, 2026-11-02 (afternoon)

Each bibliography entry was compared with a primary or index page where one could be fetched.
Confirmed (title, authors, venue, pages as in the paper): egg (POPL 2021, article 23), egglog
(PLDI 2023, article 125), Tornado (EUROCRYPT 2020, pp. 311-341), VerifMSI (SECRYPT 2023, pp. 520-527),
Feldtkeller et al. (TCHES 2022(4), 188-227), AGEMA (TCHES 2022(1), 589-629), DOM (ePrint 2016/486),
Mangard et al. (CT-RSA 2005, pp. 351-365), Suciu et al. (ICDT 2025, LIPIcs 328, 11:1-11:18), maskVerif
(ESORICS 2019, pp. 300-318; six authors per ePrint 2018/562 and HAL), SNI (CCS 2016), SILVER (ASIACRYPT
2020), E-Syn (DAC 2024), eVer, TETRIS, ePrint 2025/2102, Koblah et al. (full text), Singher and
Itzhaky (arXiv 2305.19203), Eldib and Wang (title and authors from the paper's first page).
Page numbers for ISW, HPC, PINI and COMPRESS were checked only against another paper's reference list.

Not confirmed, and marked UNVERIFIED in the bibliography: the venue of Courtois et al.; the venue of
Eldib and Wang; the journal version of MaskedHLS (only arXiv:2407.11806 was read); the exact title,
authors and date of the Fraunhofer AISEC/BSI synthesis study (the Fraunhofer blog returned HTTP 503
and the study was not read; the BSI page summary was).

## Further novelty queries (web search, US index)

- `Usuba bitslice compiler masking probing security optimization scheduling rewrite masked implementations compiler`
- `POMMES OR CoMEMS masked implementation compiler optimization probing security gadget scheduling rewriting circuit equivalent cheaper`
- `tightPROVE IronMask probing security verification masked circuit optimization rewriting equivalent circuits minimize cost automatically 2025`

Results: Usuba and Tornado (compiler plus tightPROVE+ inserting refreshes), tightPROVE, IronMask
(verifiers), PoMMES and CoMEMS (software, micro-architectural register allocation). None rewrites
equivalent masked circuits to minimise cost. Not read in full: any of these papers.
