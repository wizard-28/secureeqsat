"""VerifMSI symbolic certificate driver -- oracle venv only (GPL, external process).

Same stdin contract as experiments/oracle_crosscheck/verifmsi_driver.py, but
runs only VerifMSI's symbolic `checkTpsVal` per wire: a SOUND, incomplete
certificate that a wire is independent of the secrets. It needs no
enumeration, so it works on circuits far beyond the exhaustive checkers'
range. stdout: RESULT_JSON:{"certified": n, "not_certified": [wire, ...]}

Purpose
-------
The checkers in this repo enumerate every input, which is impossible for the huge
circuits the PINI analysis handles (for example a 32-bit Keccak chi row has about 2**128
input combinations). VerifMSI's symbolic check (`checkTpsVal`) reasons about each wire's
expression without enumeration. It is SOUND (a "certified" wire really is safe) but
incomplete (a wire may fail to be certified without leaking). This driver gives the
independent confirmation for those large circuits: "N of N wires certified".
"""

import json
import sys

from verif_msi import checkTpsVal, constant, symbol


def main():
    """Read a circuit as JSON on stdin; print how many wires VerifMSI certifies safe.

    Algorithm, step by step:
      1. For each secret, create a secret symbol `s` and a mask symbol `m0`; share 0 is
         `m0` and share 1 is `s ^ m0` (they XOR to the secret; share 0 is uniform).
      2. Give every fresh random its own uniform 1-bit symbol.
      3. Walk the wires in order, building each wire's SYMBOLIC EXPRESSION from its
         operands' expressions (`^` and `&` on VerifMSI symbols build expressions).
      4. Ask `checkTpsVal` whether the wire's expression is certified independent of the
         secret. Count certified wires (constants always count) and list the others.
      5. Print `{"certified": n, "not_certified": [...]}`.
    """
    data = json.load(sys.stdin)
    env = {}  # wire name -> its symbolic expression
    for secret, (s0, s1) in data["shares"].items():
        s = symbol(secret, "S", 1)  # the secret, a 1-bit "S" (secret) symbol
        m0 = symbol(f"{secret}__m0", "M", 1)  # a uniform 1-bit "M" (mask) symbol
        env[s0], env[s1] = m0, s ^ m0  # share 0 = mask, share 1 = secret ^ mask
    for r in data["randoms"]:
        env[r] = symbol(r, "M", 1)
    certified, missing = 0, []  # wires certified safe / names of the rest
    for w in data["wires"]:
        op, args = w["op"], w["args"]
        if op == "input":
            e = env[args]
        elif op == "const":
            e = constant(int(args), 1)  # a 1-bit constant
        elif op == "xor":
            e = env[args[0]] ^ env[args[1]]  # symbolic XOR of two expressions
        elif op == "and":
            e = env[args[0]] & env[args[1]]  # symbolic AND
        else:
            raise SystemExit(f"unsupported op {op!r}")
        env[w["name"]] = e
        # `checkTpsVal(e)[0]` is True when the wire is certified independent
        if op == "const" or checkTpsVal(e)[0]:
            certified += 1
        else:
            missing.append(w["name"])
    print(
        "RESULT_JSON:" + json.dumps({"certified": certified, "not_certified": missing})
    )


if __name__ == "__main__":
    main()
