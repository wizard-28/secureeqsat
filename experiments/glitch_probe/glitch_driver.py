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

Purpose
-------
The independent referee for the glitch model. `probe.py` sends a circuit here as
JSON; this script rebuilds it using VerifMSI's own classes (so VerifMSI, not our code,
decides what each probe can see) and prints one verdict per wire. It runs as a
SEPARATE PROCESS inside VerifMSI's virtual environment because VerifMSI is GPL and
must never be imported into our own code.
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
    """True iff the joint distribution of these expressions is independent of secrets.

    `exprs` are VerifMSI symbolic expressions. They are concatenated into one vector
    and checked EXACTLY (`getDistribWithExev` returns `(uniform, independent)`; the
    second flag is what we want). An empty list leaks nothing, so it is independent.
    """
    exprs = list(exprs)
    if not exprs:
        return True
    return bool(getDistribWithExev(Concat(*exprs))[1])


def main():
    """Read a circuit as JSON on stdin, print per-wire verdicts as `RESULT_JSON:...`.

    Algorithm, step by step:
      1. For each secret, make a secret symbol `s` and a mask symbol `m0` (both 1 bit).
         Share 0 is an input gate for `m0` and share 1 an input gate for `s ^ m0`, so
         the two shares XOR to the secret and share 0 is uniform.
      2. Make an input gate (a 1-bit uniform symbol) for every fresh random.
      3. Walk the wires in order and build the matching VerifMSI element: input,
         constant, XOR gate, AND gate or Register.
      4. For each wire record two verdicts: `glitch` (is the joint distribution of its
         leakage set, `leakageOut`, independent of the secret?) and `glitch_free` (is
         the wire's own value, `symbExp`, independent?).
      5. Run VerifMSI's own end-to-end `checkSecurity` at order 1 with glitches on the
         outputs, with its printing silenced, and report the leak count.
    """
    data = json.load(sys.stdin)  # the circuit description sent by probe.py
    hw = {}  # wire name -> VerifMSI hardware element
    for secret, (sh0, sh1) in data["shares"].items():
        s = symbol(secret, "S", 1)  # the secret itself, a 1-bit "S" (secret) symbol
        m0 = symbol(f"{secret}__m0", "M", 1)  # a 1-bit "M" (mask) symbol: uniform
        hw[sh0] = inputGate(m0)  # share 0 = the mask
        hw[sh1] = inputGate(s ^ m0)  # share 1 = secret XOR mask, so shares XOR to s
    for r in data["randoms"]:
        hw[r] = inputGate(symbol(r, "M", 1))  # each fresh random is a uniform bit

    out = {}  # wire name -> {"glitch": bool, "glitch_free": bool} or an error
    for w in data["wires"]:
        op, args = w["op"], w["args"]
        if op == "input":
            h = hw[args]
        elif op == "const":
            h = constantGate(int(args), 1)  # a 1-bit constant
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
                # what a glitch-extended probe sees: VerifMSI's own leakage set
                "glitch": independent(h.leakageOut),
                # what an ordinary probe sees: just this wire's value
                "glitch_free": independent([h.symbExp]),
            }
        except Exception as exc:  # noqa: BLE001 - reported to the caller
            out[w["name"]] = {"error": repr(exc)}

    buf = io.StringIO()  # a text buffer that swallows everything printed into it
    with contextlib.redirect_stdout(buf):  # silence checkSecurity's own printing
        nb_leak, nb_check = checkSecurity(
            1,
            True,
            "tps",
            *[hw[o] for o in data["outputs"]],  # order 1, glitches on
        )
    print(
        "RESULT_JSON:"  # the tag the parent process searches for
        + json.dumps(
            {
                "wires": out,
                "check_security": {"nb_leak": nb_leak, "nb_check": nb_check},
            }
        )
    )


if __name__ == "__main__":
    main()
