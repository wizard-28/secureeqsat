"""VerifMSI oracle driver — runs in the oracle venv, imports GPL VerifMSI there.

Contract:
    stdin  : JSON {"shares": {secret: [share0, share1]},
                   "randoms": [name, ...],
                   "wires": [{"name":..., "op": "input"|"const"|"xor"|"and",
                              "args": name | int | [a, b]}, ...]
              wires are in topological order.
    stdout : JSON {wire_name: bool}   (True == first-order probing secure)

Translation of our circuits into VerifMSI's symbolic model (2 shares):
    share0  ->  mask  m0          (type 'M', uniform)
    share1  ->  secret ^ m0       (so share0 ^ share1 == secret)
    random  ->  mask              (type 'M', uniform)

IMPORTANT: checkTpsVal returns the 3-tuple (res, usedBitExp, time) — the README's
`if res:` idiom is wrong because a non-empty tuple is always truthy. Use res[0].

Purpose
-------
The bridge to the independent referee. `crosscheck.py` sends a circuit here as JSON;
this script rebuilds every wire as a VerifMSI symbolic expression and returns two
verdicts per wire: the EXACT independence check (`getDistribWithExev`) and VerifMSI's
sound-but-incomplete symbolic certificate (`checkTpsVal`). It runs as a SEPARATE PROCESS
inside VerifMSI's virtual environment because VerifMSI is GPL and must never be linked
into our own code.
"""

import json
import sys

from verif_msi import checkTpsVal, constant, getDistribWithExev, symbol


def main():
    """Read a circuit as JSON on stdin; print `RESULT_JSON:{wire: verdicts}`.

    Algorithm, step by step:
      1. For each secret (only 2-share maskings are supported), create a secret symbol
         `s` and a mask symbol `m0`. Share 0 is `m0` and share 1 is `s ^ m0`, so the
         shares XOR to the secret and share 0 is uniform.
      2. Give each fresh random its own uniform 1-bit symbol.
      3. Walk the wires in order, building each wire's symbolic expression from its
         operands' expressions (`^` and `&` on symbols build expressions).
      4. For each wire run both checks: the certificate (`tps`) and the exact check
         (`uniform`, `independent`). A failure to evaluate is recorded as an error.
      5. Print the results on one line tagged `RESULT_JSON:` so the caller can find it
         even if VerifMSI prints diagnostics.
    """
    data = json.load(sys.stdin)  # the circuit description sent by crosscheck.py
    env = {}  # wire name -> its symbolic expression

    for secret, shares in data["shares"].items():
        if len(shares) != 2:
            raise SystemExit(
                f"driver only models 2-share maskings; got {len(shares)} shares "
                f"for {secret!r}"
            )
        s = symbol(secret, "S", 1)  # the secret: a 1-bit "S" (secret) symbol
        m0 = symbol(f"{secret}__m0", "M", 1)  # a uniform 1-bit "M" (mask) symbol
        env[shares[0]] = m0  # share 0 = the mask
        env[shares[1]] = s ^ m0  # share 1 = secret XOR mask

    for r in data["randoms"]:
        env[r] = symbol(r, "M", 1)  # each fresh random is a uniform 1-bit mask

    out = {}  # wire name -> {"tps": bool, "uniform": bool, "independent": bool}
    for w in data["wires"]:
        op = w["op"]
        if op == "input":
            e = env[w["args"]]
        elif op == "const":
            e = constant(int(w["args"]), 1)  # a 1-bit constant
        elif op == "xor":
            a, b = w["args"]  # the two operand wire names
            e = env[a] ^ env[b]  # symbolic XOR
        elif op == "and":
            a, b = w["args"]
            e = env[a] & env[b]  # symbolic AND
        else:
            raise SystemExit(f"unsupported op {op!r}")
        env[w["name"]] = e
        try:
            # checkTpsVal returns (res, usedBitExp, time) — tuple truthiness is
            # always True, so res[0] is mandatory.  It is a SOUND but INCOMPLETE
            # certificate of independence (verified empirically: tps=True never
            # contradicted exhaustive independence in 400 random expressions).
            tps = bool(checkTpsVal(e)[0])
            # getDistribWithExev returns (uniform, independent) and is the EXACT
            # per-wire property our checker implements.
            uniform, independent = getDistribWithExev(e)
            out[w["name"]] = {
                "tps": tps,
                "uniform": bool(uniform),
                "independent": bool(independent),
            }
        except Exception as exc:  # noqa: BLE001 - reported to the caller
            out[w["name"]] = {"error": repr(exc)}

    # Sentinel line: VerifMSI may print diagnostics, so the caller must be able
    # to find our payload unambiguously.
    print("RESULT_JSON:" + json.dumps(out))


if __name__ == "__main__":
    main()
