"""VerifMSI glitch driver -- runs in the oracle venv (GPL: external process only).

stdin : JSON {"shares": {secret: [s0, s1]}, "randoms": [...],
              "wires": [{"name", "op": input|const|xor|and|reg, "args"}],
              "outputs": [wire, ...]}   (topological order)
stdout: RESULT_JSON:{"wires": {name: {"glitch": bool, "glitch_free": bool}},
                     "check_security": {"nb_leak": int, "nb_check": int}}

The circuit is rebuilt from VerifMSI's own hardware elements (inputGate,
xorGate, andGate, Register), so each probe's glitch-extended leakage set is
VerifMSI's `leakageOut`, not ours. Each set is checked EXACTLY with
`getDistribWithExev(Concat(...))` (secret independence of the joint
distribution); `checkSecurity(1, True, 'tps', outputs)` is run as well, as
VerifMSI's own end-to-end verdict (sound but incomplete).
"""

import contextlib
import io
import json
import sys

from verif_msi import (
    Concat,
    Register,
    andGate,
    checkSecurity,
    constantGate,
    getDistribWithExev,
    inputGate,
    symbol,
    xorGate,
)


def independent(exprs):
    exprs = list(exprs)
    if not exprs:
        return True
    return bool(getDistribWithExev(Concat(*exprs))[1])


def main():
    data = json.load(sys.stdin)
    hw = {}
    for secret, (sh0, sh1) in data["shares"].items():
        s = symbol(secret, "S", 1)
        m0 = symbol(f"{secret}__m0", "M", 1)
        hw[sh0] = inputGate(m0)
        hw[sh1] = inputGate(s ^ m0)
    for r in data["randoms"]:
        hw[r] = inputGate(symbol(r, "M", 1))

    out = {}
    for w in data["wires"]:
        op, args = w["op"], w["args"]
        if op == "input":
            h = hw[args]
        elif op == "const":
            h = constantGate(int(args), 1)
        elif op == "xor":
            h = xorGate(hw[args[0]], hw[args[1]])
        elif op == "and":
            h = andGate(hw[args[0]], hw[args[1]])
        elif op == "reg":
            h = Register(hw[args[0]])
        else:
            raise SystemExit(f"unsupported op {op!r}")
        hw[w["name"]] = h
        try:
            out[w["name"]] = {
                "glitch": independent(h.leakageOut),
                "glitch_free": independent([h.symbExp]),
            }
        except Exception as exc:  # noqa: BLE001 - reported to the caller
            out[w["name"]] = {"error": repr(exc)}

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        nb_leak, nb_check = checkSecurity(
            1, True, "tps", *[hw[o] for o in data["outputs"]]
        )
    print(
        "RESULT_JSON:"
        + json.dumps(
            {
                "wires": out,
                "check_security": {"nb_leak": nb_leak, "nb_check": nb_check},
            }
        )
    )


if __name__ == "__main__":
    main()
