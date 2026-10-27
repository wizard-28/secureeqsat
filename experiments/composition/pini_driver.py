"""VerifMSI PINI driver -- runs in the oracle venv (GPL: external process only).

stdin : JSON {"sharings": {name: [share0, share1]}, "randoms": [...],
              "wires": [{"name", "op": input|const|xor|and, "args"}],
              "outputs": [[share0, share1], ...]}
stdout: RESULT_JSON:{"nb_leak": int, "nb_check": int}

Inputs are VerifMSI *real* shares (getRealShares), as its PINI check needs
share indices; the gadget is checked with checkSecurity(1, False, 'pini').
VerifMSI's symbolic PINI check is sound for "no leak" and may raise
conservative alarms, so a leak report is not proof of a violation.

Purpose
-------
The independent referee for the PINI verdicts. `run_composition.py` sends a lowered
gadget here as JSON; this script rebuilds it with VerifMSI's own classes and asks
VerifMSI's PINI checker whether it leaks. It runs as a SEPARATE PROCESS in VerifMSI's
virtual environment because VerifMSI is GPL and must never be imported into our code.
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
    """Read a gadget as JSON on stdin, print `RESULT_JSON:{"nb_leak":..,"nb_check":..}`.

    Algorithm, step by step:
      1. For every input sharing, create a VerifMSI secret symbol and split it into 2
         "real" shares (`getRealShares`), which carry the share indices PINI needs.
         Wrap each as an input gate under the share names the circuit uses.
      2. Make an input gate (a uniform 1-bit symbol) for every fresh random.
      3. Walk the wires in order and build a constant, XOR or AND gate (inputs were
         already created above, so they are skipped).
      4. Collect the output share pairs, then run VerifMSI's own PINI check at order 1
         without glitches, with its printing silenced.
      5. Print the number of leaks and the number of checks performed.
    """
    data = json.load(sys.stdin)  # the gadget description sent by run_composition.py
    hw = {}  # wire name -> VerifMSI hardware element
    for name, (s0, s1) in data["sharings"].items():
        # split the secret `name` into 2 indexed shares; r0, r1 are symbolic shares
        r0, r1 = getRealShares(symbol(name, "S", 1), 2)
        hw[s0], hw[s1] = inputGate(r0), inputGate(r1)
    for r in data["randoms"]:
        hw[r] = inputGate(symbol(r, "M", 1))  # a uniform 1-bit random
    for w in data["wires"]:
        op, args = w["op"], w["args"]
        if op == "input":
            continue  # shares and randoms were created above
        if op == "const":
            hw[w["name"]] = constantGate(int(args), 1)
        elif op == "xor":
            hw[w["name"]] = xorGate(hw[args[0]], hw[args[1]])
        elif op == "and":
            hw[w["name"]] = andGate(hw[args[0]], hw[args[1]])
        else:
            raise SystemExit(f"unsupported op {op!r}")
    # each output is a pair of share wires -> a pair of hardware elements
    outs = [[hw[s] for s in pair] for pair in data["outputs"]]
    buf = io.StringIO()  # swallows everything checkSecurity prints
    with contextlib.redirect_stdout(buf):
        # order 1, no glitches, PINI mode
        nb_leak, nb_check = checkSecurity(1, False, "pini", *outs)
    print("RESULT_JSON:" + json.dumps({"nb_leak": nb_leak, "nb_check": nb_check}))


if __name__ == "__main__":
    main()
