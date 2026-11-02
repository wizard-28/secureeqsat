"""Area (Nangate45, GE) of an AGEMA-generated masked netlist, with AGEMA's own gadgets.

    uv run python experiments/bench_extra/agema_area.py net_HPC2_Pipeline_d1.v HPC2

Purpose
-------
AGEMA's output is Verilog that instantiates its VHDL gadgets (`and_HPC2`, `xor_HPC2`,
registers, ...) with generics `security_order` and `pipeline`. This reads the VHDL
gadgets with Yosys's GHDL plugin (generics fixed to first order, pipelined), reads the
netlist, flattens, maps to Nangate45 and reports the area. It replaces the earlier
estimate that summed COMPRESS's gadget areas.

Environment: `H2H` (default `~/h2h`) holding `AGEMA/CaseStudies`, `compress/synthesis`
and `oss/oss-cad-suite`. The unmasked-clock-gating cell library is not needed.
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

H2H = Path(os.environ.get("H2H", Path.home() / "h2h"))
GADGETS = H2H / "AGEMA/CaseStudies/00_Common_Gadgets"
LIB = H2H / "compress/synthesis/nangate45-pdk/stdcells.lib"
YOSYS = H2H / "oss/oss-cad-suite/bin/yosys"
GE = 0.798
SKIP = {"module", "input", "output", "wire", "assign", "endmodule"}


def instances(text):
    """Count instances per VHDL gadget entity in the netlist (generics stripped)."""
    counts = {}
    text = re.sub(r"#\((?:[^()]|\([^()]*\))*\)", "", text)  # drop instance generics
    for m in re.finditer(r"^\s*([A-Za-z_]\w*)\s+\w+\s*\(", text, re.M):
        if m.group(1) not in SKIP:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def vhdl_files(entity):
    """VHDL sources for `entity`: its own file first, then the shared General cells."""
    scheme = "HPC3" if entity.endswith("HPC3") else "HPC2"
    own = GADGETS / scheme / f"{entity}.vhd"
    if not own.exists():  # a shared cell such as buf_sca_clk
        own = GADGETS / "General" / f"{entity}.vhd"
    general = sorted((GADGETS / "General").glob("*.vhd"))
    rest = [p for p in general if p != own and "ClockGating" not in p.name]
    return [own, *rest]


def _has_generics(entity):
    """True iff the entity's own VHDL file declares the security_order generic."""
    src = vhdl_files(entity)[0].read_text(errors="ignore")
    head = re.search(r"entity\s+\w+\s+is\s+(.*?)\bport\b", src, re.S | re.I)
    return bool(head and re.search(r"\bsecurity_order\b", head.group(1), re.I))


def entity_import(entity):
    """Yosys commands that load one gadget entity as a standalone flattened module.

    Each entity is imported into a scratch design, flattened (so its VHDL dependencies
    disappear into it), stashed, and copied into the main design under its own name.
    Importing the shared General cells for every entity would otherwise redefine them.
    """
    files = vhdl_files(entity)
    src = files[0].read_text(errors="ignore")
    head = re.search(r"entity\s+\w+\s+is\s+(.*?)\bport\b", src, re.S | re.I)
    decl = head.group(1) if head and "generic" in head.group(1).lower() else ""
    gen = " ".join(
        f"-g{g}=1"
        for g in ("security_order", "pipeline")
        if re.search(rf"\b{g}\b", decl, re.I)
    )
    names = " ".join(str(f) for f in files)
    return [
        f"design -save keep_{entity}",
        "design -reset",
        f"ghdl --std=08 -frelaxed {gen} {names} -e {entity}",
        f"hierarchy -top {entity}",
        "synth -flatten",
        f"design -stash s_{entity}",
        f"design -load keep_{entity}",
        f"design -copy-from s_{entity} -as {entity} {entity}",
    ]


def area_ge(netlist):
    """Return the Nangate45 area in GE of the AGEMA netlist `netlist`."""
    text = Path(netlist).read_text()
    top = re.search(r"^module\s+(\w+)", text, re.M).group(1)
    text = re.sub(r"#\((?:[^()]|\([^()]*\))*\)", "", text)  # instance generics
    with tempfile.TemporaryDirectory() as tmp:
        v = Path(tmp) / "m.v"
        v.write_text(text)
        lines = ["plugin -i ghdl"]
        # the GHDL plugin keeps -g settings between calls, so entities without generics
        # (buf_sca_clk, ...) must be imported before those that have them
        for e in sorted(instances(text), key=lambda x: (_has_generics(x), x)):
            lines += entity_import(e)
        lines += [
            f"read_verilog {v}",
            f"hierarchy -top {top}",
            "synth -flatten",
            f"dfflibmap -liberty {LIB}",
            f"abc -liberty {LIB}",
            f"tee -o {tmp}/stat.txt stat -liberty {LIB}",
        ]
        script = Path(tmp) / "a.ys"
        script.write_text("\n".join(lines) + "\n")
        env = dict(os.environ, PATH=f"{YOSYS.parent}:{os.environ['PATH']}")
        run = subprocess.run(
            [str(YOSYS), "-s", str(script)], capture_output=True, text=True, env=env
        )
        if run.returncode:
            err = [
                x
                for x in (run.stderr + run.stdout).splitlines()
                if "ERROR" in x or "error:" in x
            ]
            raise RuntimeError("yosys failed: " + " / ".join(err[:3]))
        stat = (Path(tmp) / "stat.txt").read_text()
    area = re.findall(r"Chip area for (?:top )?module[^:]*:\s*([\d.]+)", stat)
    return float(area[-1]) / GE


def main():
    """Print the area of the netlist given on the command line."""
    net = Path(sys.argv[1])
    print(
        f"{net.parent.name:14s} {sys.argv[2] if len(sys.argv) > 2 else '':5s} "
        f"{area_ge(net):8.1f} GE"
    )


if __name__ == "__main__":
    main()
