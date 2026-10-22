"""VerifMSI symbolic certificate driver -- oracle venv only (GPL, external process).

Same stdin contract as experiments/oracle_crosscheck/verifmsi_driver.py, but
runs only VerifMSI's symbolic `checkTpsVal` per wire: a SOUND, incomplete
certificate that a wire is independent of the secrets. It needs no
enumeration, so it works on circuits far beyond the exhaustive checkers'
range. stdout: RESULT_JSON:{"certified": n, "not_certified": [wire, ...]}
"""

import json
import sys

from verif_msi import checkTpsVal, constant, symbol


def main():
    data = json.load(sys.stdin)
    env = {}
    for secret, (s0, s1) in data["shares"].items():
        s = symbol(secret, "S", 1)
        m0 = symbol(f"{secret}__m0", "M", 1)
        env[s0], env[s1] = m0, s ^ m0
    for r in data["randoms"]:
        env[r] = symbol(r, "M", 1)
    certified, missing = 0, []
    for w in data["wires"]:
        op, args = w["op"], w["args"]
        if op == "input":
            e = env[args]
        elif op == "const":
            e = constant(int(args), 1)
        elif op == "xor":
            e = env[args[0]] ^ env[args[1]]
        elif op == "and":
            e = env[args[0]] & env[args[1]]
        else:
            raise SystemExit(f"unsupported op {op!r}")
        env[w["name"]] = e
        if op == "const" or checkTpsVal(e)[0]:
            certified += 1
        else:
            missing.append(w["name"])
    print(
        "RESULT_JSON:" + json.dumps({"certified": certified, "not_certified": missing})
    )


if __name__ == "__main__":
    main()
