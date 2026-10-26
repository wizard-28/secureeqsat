# Getting up to speed — SecureEqSat

**Last updated:** 2026-10-11. A 15-minute orientation for anyone joining or
reviewing the project. For the live status, read
[`project_context.md`](../project_context.md); for working rules,
[`AGENTS.md`](../AGENTS.md). If this page and those disagree, they win.

---

## 1. The project in one paragraph

Masked cryptographic circuits hide every secret bit by splitting it into random
**shares**, so that no single wire reveals anything about the secret. Equality
saturation (e-graphs) is a compiler technique that explores many equivalent
versions of a program at once and then picks the cheapest. We asked what
happens when you point equality saturation at masked circuits. **Answer:** done
naively it breaks the masking, and the cheapest result is exactly the broken
one. We built the repair (an exact security checker, a cross-check against an
independent tool, and security-constrained extraction), and then showed *why*
the optimizations that matter in masking can't be expressed as ordinary
e-graph rewrites — and how they can be, one level up.

## 2. Background in five minutes

**Masking (2 shares, first order).** A secret bit `a` is stored as `(a0, a1)`
with `a0` uniformly random and `a1 = a0 ^ a`. An attacker who can **probe** (read)
any *one* wire must learn nothing about `a`. A circuit is *first-order probing
secure* if every wire's value distribution is independent of the secrets. XOR
can be done share by share. AND cannot: it needs a **gadget** — ISW, DOM, HPC1 —
that mixes in a fresh random bit `r` in the right places.

**Refresh.** `refresh(x) = (x0 ^ r, x1 ^ r)` gives the same value with
different shares. It's needed when the same sharing would otherwise meet itself
inside one gadget (e.g. `isw(z, z)` leaks; `isw(z, refresh(z))` doesn't).

**Equality saturation.** Put a program into an *e-graph*, apply rewrite rules
(e.g. `x & (y ^ z) = x&y ^ x&z`) until nothing new appears, then **extract** the
cheapest equivalent program. Each *e-class* is a set of terms proven equal.

**Why they collide.** Rewrites preserve *what a circuit computes*, but probing
security depends on *how* — which intermediate wires exist. Two circuits with
the same function can differ in security.

## 3. What we found (with numbers)

| # | Result | Evidence |
|---|---|---|
| 1 | **Naive EqSat is unsound.** On a secure 8-gate ISW AND, ordinary Boolean rules (distributivity run backwards) give a 7-gate circuit that leaks `b0 ^ b1` — the unmasked secret. Cheapest = insecure. Same leak on two engines (in-house + egglog). | `experiments/premise_test/`, `experiments/egglog_port/` |
| 2 | **The checker is trustworthy.** Our exact checker agrees with VerifMSI on 1,216 circuits / 21,760 wires (0 disagreements); the fast checker on 1,265 / 22,463 (0). | `experiments/oracle_crosscheck/`, `design/0005`, `0015` |
| 3 | **The repair works.** Security-constrained extraction recovers the secure 8-gate circuit. Price of security: 1 gate. | `experiments/constrained_extraction/`, `design/0006` |
| 4 | **No payoff from plain rewriting.** Two-gadget chain: hand-written 16 gates secure; unconstrained optimum 14 gates, insecure; 240 sampled cheaper pairs, none secure. | `docs/feasibility-report.md` §4 |
| 5 | **Scaling was engineering.** egglog saturates the chain in < 0.01 s; the bitsliced labeller labels a depth-5 chain in ~0.4 s (vs ~50 min estimated before). | `design/0009`, `design/0015` |
| 6 | **Re-sharing is expressible one level up.** In an e-graph whose classes identify *sharings by value*, refresh removal and ISW = DOM = HPC1 become ordinary rules. Over-refreshed chain 30 → 18; `a&b ^ a&d` 20 → 11 (secure). Refresh removal on `isw(z, refresh(z))` is cheaper and leaks — constrained extraction blocks it. | `experiments/resharing/`, `design/0016` |
| 7 | **Tight starts gain nothing.** The hand-written chain and Keccak chi (3- and 5-bit rows) are unchanged under every rule class. Gains only came from deliberate slack. | `experiments/resharing/RESULTS.md` |

Costs in results 6–7 count **gates + random bits** (one each).

**The story in one line:** EqSat on masked circuits is unsound as-is; we can
repair it; and the optimizations worth having live at the level of sharings, not
wires — where so far they only remove slack.

## 4. What we do *not* claim

- Anything beyond **first order, 2 shares, straight-line** circuits in the
  glitch-free and glitch-extended models (`design/0018`). PINI composition
  in the glitch-free model only (C9); nothing on SNI, higher orders or
  glitch-robust composition; no register timing.
- That refresh removal, factoring before masking, or gadget choice are new —
  masking compilers already do these. Our contribution is the soundness finding,
  the repair, and the representation.
- A win over any published tight construction (result 7 says the opposite).
- Novelty of anything without the citation check (`.claude/skills/secureeqsat-citation-check`).
  Neighbouring work: superVer (verification with e-graphs) and eVer
  (ePrint 2026/208, optimizes refreshes and gadgets with re-verification).

## 5. Repository tour

| Path | What it is | Read it when |
|---|---|---|
| `project_context.md` | Live status, decision log, risks, next actions, change log | Always first |
| `findings/` | Every finding, its numbers, and a script that re-runs and checks all of them | You want to verify the results |
| `AGENTS.md` | Working rules for humans and agents | Before your first commit |
| `docs/probing-secure-eqsat-proposal.md` | The proposal (revision 3) | You need the full argument |
| `docs/feasibility-report.md` | Results 1–5 with confidence levels | You need the evidence |
| `docs/adversarial-search-*.md` | Novelty searches and corrected claims | Before saying "first" or "new" |
| `design/` | ADRs 0001–0016, one per decision | You wonder why something is the way it is |
| `experiments/premise_test/` | Minimal e-graph harness, exact checker, ISW/DOM fixtures | Result 1 |
| `experiments/oracle_crosscheck/` | VerifMSI driver and cross-check | Result 2 |
| `experiments/constrained_extraction/` | Security-constrained extraction | Results 3–4 |
| `experiments/egglog_port/` | Same premise on the real engine; k-best frontier | Results 1, 4, 5 |
| `experiments/labeller/` | Bitsliced exact labeller | Result 5 |
| `experiments/composition/` | PINI composition analysis: class-level extraction that scales past exact checking | Theory claim C9 |
| `experiments/resharing/` | Shared-value layer: lowering, egglog rules, extraction, fixtures | Results 6–7 |
| `docs/original/` | Historical first direction — **do not edit** | Only for history |

Every experiment folder has a `RESULTS.md`: question, method, results, what it
does and does **not** show, and raw output.

## 6. Run it

```bash
uv sync                      # builds .venv from uv.lock (needs uv)
uv run pytest -q             # 173 tests; 19 skip without the VerifMSI oracle
uv run python experiments/premise_test/run.py      # result 1, narrated
uv run python experiments/resharing/run.py         # results 6-7 ablation
```

The dev container (see `README.md`) also installs the VerifMSI oracle. Without it,
the 13 cross-check tests **skip**, and a skip is not a pass:
`bash experiments/oracle_crosscheck/setup_oracles.sh` installs it outside the repo.

## 7. Reading order

- **15 minutes:** this page, then `project_context.md` §2–3.
- **1 hour:** `experiments/premise_test/RESULTS.md`, `docs/feasibility-report.md`
  §1–6, `experiments/resharing/RESULTS.md`.
- **Half a day:** the proposal, `design/0005`, `0006`, `0010`, `0011`, `0015`,
  `0016`, and `docs/adversarial-search-3.md`.

## 8. Rules of the road (from `AGENTS.md`)

- Run Python only through `uv run`. No `pip`, `apt` or `curl | sh`.
- Reproduce before extending: `uv run pytest -q` and the premise test first.
- **No security claim on our checker alone** — it must be cross-checked against
  VerifMSI. VerifMSI is GPLv3: call it as an external process, never vendor it.
- New dependency, scope change, security-model change or architecture decision →
  write an ADR in `design/` first.
- Every change lands with its bookkeeping in the same commit: tests,
  `RESULTS.md`, ADR if any, and a dated line in `project_context.md`.
- Ask the team before making a novelty claim, a security claim, or changing
  the dev container.

## 9. Open questions and next work

1. **Randomness reuse** — the only lever left against tight constructions.
   Naive reuse leaked on the chain; modelling it needs a new ADR.
2. **Extraction speed** — term-based extraction at the value level takes ~144 s
   at chain depth 5.
3. **Bigger benchmarks** — partly answered by F11: on the PINI fragment,
   composition decides Keccak χ on a 32-bit row (a 2^128-point space) in
   ≤ 0.03 s, certified by VerifMSI, at a cost premium of up to +33 %. Outside
   that fragment, S-box scale still exceeds the exact labeller's `2**26` cap
   and needs the deferred symbolic labeller.
4. **Citation check** — done for the representation and composition claims
   (`docs/adversarial-search-4.md`, `-5.md`; medium confidence). A sixth pass
   remains: eVer's PDF, AGEMA's register handling, e-boost and SmoothE, the
   Fraunhofer AISEC/BSI study itself, maskComp and Tornado.

## 10. Glossary

| Term | Meaning |
|---|---|
| Share | One of the random-looking pieces a secret is split into |
| Probe | An attacker reading one wire |
| First-order probing security | No single wire's distribution depends on a secret |
| Gadget | A masked AND: ISW, DOM, HPC1 (DOM with one input refreshed) |
| Refresh | Re-randomise a sharing without changing its value |
| Re-sharing | Same value, different shares — what refresh and gadget swaps do |
| E-graph / e-class | Data structure holding many equivalent terms; a class of equal terms |
| Equality saturation | Apply rewrites until nothing changes, then extract |
| Extraction | Picking one cheapest term from the e-graph |
| Constrained extraction | Extraction that rejects leaking choices |
| Lowering | Turning a shared-value term into actual share-level gates |
| VerifMSI | Independent verification tool we cross-check against |
| Congruence | An equality that is preserved under every context — what an e-graph assumes |
