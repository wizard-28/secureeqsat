"""VerifMSI PINI driver -- runs in the oracle venv (GPL: external process only).

stdin : JSON {"sharings": {name: [share0, share1]}, "randoms": [...],
              "wires": [{"name", "op": input|const|xor|and, "args"}],
              "outputs": [[share0, share1], ...]}
stdout: RESULT_JSON:{"nb_leak": int, "nb_check": int}

Inputs are VerifMSI *real* shares (getRealShares), as its PINI check needs
share indices; the gadget is checked with checkSecurity(1, False, 'pini').
VerifMSI's symbolic PINI check is sound for "no leak" and may raise
conservative alarms, so a leak report is not proof of a violation.
"""

import contextlib
import io
import json
import sys

from verif_msi import (
    andGate,
    checkSecurity,
    constantGate,
    getRealShares,
    inputGate,
    symbol,
    xorGate,
)


def main():
    data = json.load(sys.stdin)
    hw = {}
    for name, (s0, s1) in data["sharings"].items():
        r0, r1 = getRealShares(symbol(name, "S", 1), 2)
        hw[s0], hw[s1] = inputGate(r0), inputGate(r1)
    for r in data["randoms"]:
        hw[r] = inputGate(symbol(r, "M", 1))
    for w in data["wires"]:
        op, args = w["op"], w["args"]
        if op == "input":
            continue
        if op == "const":
            hw[w["name"]] = constantGate(int(args), 1)
        elif op == "xor":
            hw[w["name"]] = xorGate(hw[args[0]], hw[args[1]])
        elif op == "and":
            hw[w["name"]] = andGate(hw[args[0]], hw[args[1]])
        else:
            raise SystemExit(f"unsupported op {op!r}")
    outs = [[hw[s] for s in pair] for pair in data["outputs"]]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        nb_leak, nb_check = checkSecurity(1, False, "pini", *outs)
    print("RESULT_JSON:" + json.dumps({"nb_leak": nb_leak, "nb_check": nb_check}))


if __name__ == "__main__":
    main()
