# 0020 — A small language front end for the compiler pipeline

- **Status:** accepted
- **Date:** 2026-10-26
- **Deciders:** Sourajyoti Basak (requested the front end); implemented with Claude

## Context

Everything built so far starts from hand-written shared-value terms (`("isw", ("in", "a"), …)`).
That is accurate, but it is not a compiler: nothing reads a program, and nothing is emitted.
The weakest point of the project's "compiler design" framing is exactly that missing front end
and back end. The core results (unsoundness, constrained extraction, the value layer) do not
depend on how a term is produced, so a front end changes no claim.

## Decision

Add `experiments/frontend/`, a thin source-to-netlist driver over the existing pipeline:

1. a hand-written recursive-descent **parser** for a Boolean language
   (`input`, `name = expr`, `out name = expr`; operators `~ & ^ |`);
2. a **masking pass** that turns the AST into a shared-value term, with a policy:
   `refresh` (default; the ISW gadget's second operand is refreshed, which makes the two operand
   sharings independent, so the start is secure by construction) or `naive` (no refresh, which
   can leak and is there to show the constraint working);
3. the existing back half, unchanged: egglog saturation (R1–R3), then unconstrained and
   security-constrained extraction;
4. **verification**: functional equivalence against the source over all inputs, the exact
   first-order check, and optionally the VerifMSI cross-check (`--crosscheck`);
5. an **emitter** for a plain netlist and for Verilog.

Scope is unchanged: first order, 2 shares, straight-line Boolean programs, glitch-free model.
The emitted Verilog carries a header saying so; it is combinational logic and is **not**
glitch-extended secure (`design/0017`, `0018`).

No new dependency: standard library plus the `egglog` already in the dev group.

## Consequences

- The project can be demonstrated end to end on source programs, and each stage's output is
  printed. This is the missing "compiler" half.
- The front end inherits the engine's limits: term-based extraction is slow beyond a few AND
  gadgets (`design/0016`, about 144 s at chain depth 5), so examples are small. The CLI reports
  the frontier size and warns on large programs.
- Constants are not supported (a share-wise constant has no sharing); `~x` is.
- A policy that produced an insecure start is reported honestly; the constrained stage then
  searches for a secure realisation, and says so if none exists in the frontier.
- No security claim rests on the in-house checker alone: `--crosscheck` runs VerifMSI, and the
  test suite cross-checks the compiled circuits when the oracle is present.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| An LLVM or MLIR front end | Far larger; the e-graph and the checker work on Boolean circuits, and the project's own history shows the cost of general compiler IR (`design/0001`) |
| A web interface | Adds no compiler substance and costs time before the review |
| Parser-generator dependency (Lark, ply) | Needs an ADR for a runtime dependency and buys nothing for a 4-operator grammar |

## Evidence

Judgement, plus the tests in `experiments/frontend/test_frontend.py` and the run recorded in
`experiments/frontend/RESULTS.md`.
