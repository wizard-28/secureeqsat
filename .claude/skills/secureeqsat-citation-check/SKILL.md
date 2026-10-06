---
name: secureeqsat-citation-check
description: Verify prior-art claims and citations for SecureEqSat with auditable queries, calibrated confidence and explicit non-claims. Use before any citation, novelty claim or "nobody has done X" statement enters a document, and when asked to check novelty or prior art.
---

# Citation and novelty checking

Implements `AGENTS.md` §5. Each rule below exists because of a specific incident —
treat them as load-bearing, not ceremony.

## Rules

1. **Never cite what you have not fetched.** Before a citation enters any
   document, fetch the primary source (arXiv abstract page, venue listing, DOI,
   repo). If you cannot fetch it, write `UNVERIFIED` next to it in the text. No
   exceptions — the risk runs in both directions.
2. **Verify the conclusion, not just the citation.** Every citation can check out
   while the *recommended direction is already occupied*. Check that the direction
   is actually available, not merely that the paper exists.
3. **Read the full paper for any load-bearing claim.** Abstracts hide the details
   that decide novelty. If a claim rests on an abstract alone, say so.
4. **Negative results need a query log.** "Nobody has done X" is an opinion unless
   the document itself records the exact queries that produced it.
5. **State confidence, never certainty.** Novelty is a negative claim and cannot be
   proven. Use `high` / `medium-high` / `medium` / `speculative`, and name the
   residual risk. Anyone claiming certainty about novelty is wrong.
6. **Always state what we do not claim.** Every novelty section needs an explicit
   disclaimer list naming the adjacent work that partially anticipates it.

## Output shape

Append a **new dated pass** to `docs/adversarial-search-N.md`. Do not rewrite an
earlier pass — the record is the point. A pass contains:

- the claim under attack, stated precisely;
- the exact queries run;
- each hit: title, authors, venue, URL, and **precisely what it shows**;
- for each hit, the verdict: *defeats the claim* / *partially overlaps* / *context only*;
- the residual gap, if the claim survives;
- honest confidence, and what could not be verified.

## Stop and ask

Making or changing a **novelty claim**, or citing anything as **prior art**, is a
stop-and-ask-the-human action (`AGENTS.md` §11). Present the evidence and let the
human decide; do not publish the claim yourself.
