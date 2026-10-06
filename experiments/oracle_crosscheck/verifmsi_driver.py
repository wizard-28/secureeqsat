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
"""

import json
import sys

from verif_msi import checkTpsVal, constant, getDistribWithExev, symbol


def main():
    data = json.load(sys.stdin)
    env = {}

    for secret, shares in data["shares"].items():
        if len(shares) != 2:
            raise SystemExit(
                f"driver only models 2-share maskings; got {len(shares)} shares "
                f"for {secret!r}"
            )
        s = symbol(secret, "S", 1)
        m0 = symbol(f"{secret}__m0", "M", 1)
        env[shares[0]] = m0
        env[shares[1]] = s ^ m0

    for r in data["randoms"]:
        env[r] = symbol(r, "M", 1)

    out = {}
    for w in data["wires"]:
        op = w["op"]
        if op == "input":
            e = env[w["args"]]
        elif op == "const":
            e = constant(int(w["args"]), 1)
        elif op == "xor":
            a, b = w["args"]
            e = env[a] ^ env[b]
        elif op == "and":
            a, b = w["args"]
            e = env[a] & env[b]
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
