"""Tests for the language front end (design/0020).

The claims under test: the parser accepts exactly the documented language; the
masking pass yields a secure start under the refresh policy and can leak under
the naive one; the compiled circuit computes the source program; the security
constraint keeps what it must; the emitted netlist and Verilog compute the same
thing as the lowered circuit; and the in-house verdicts agree with VerifMSI.
"""

import functools
import itertools
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import seqc  # noqa: E402
from lang import ParseError, evaluate, parse  # noqa: E402

EXAMPLES = sorted((HERE / "examples").glob("*.sec"))
IDS = [p.stem for p in EXAMPLES]


@functools.cache
def compiled(name, policy="refresh"):
    prog = parse((HERE / "examples" / f"{name}.sec").read_text())
    return prog, seqc.compile_program(prog, policy)


# ---- parser -------------------------------------------------------------------


def test_precedence_not_and_xor_or():
    prog = parse("input a, b, c, d\nout y = a | b ^ c & ~d\n")
    ((_, ast),) = prog.outputs
    assert ast == (
        "or",
        ("var", "a"),
        ("xor", ("var", "b"), ("and", ("var", "c"), ("not", ("var", "d")))),
    )


def test_comments_blank_lines_and_multiple_outputs():
    src = """
    # a comment
    input x, y   # trailing comment

    t = x & y
    out u = t
    out v = t ^ x
    """
    prog = parse(src)
    assert prog.inputs == ["x", "y"]
    assert [n for n, _ in prog.outputs] == ["u", "v"]


def test_names_are_substituted_so_shared_expressions_are_equal():
    prog = parse("input a, b\nt = a & b\nout y = t ^ t\n")
    ((_, ast),) = prog.outputs
    assert ast[1] == ast[2]


@pytest.mark.parametrize(
    "src, fragment",
    [
        ("out y = a\n", "unknown name"),
        ("input a\nout y = a &\n", "expression expected"),
        ("input a\nout y = (a\n", "expected ')'"),
        ("input a\nout y = a b\n", "unexpected"),
        ("input a\nout y = 1\n", "constants are not supported"),
        ("input a\nt = a\nt = a\nout y = t\n", "already defined"),
        ("input a, a\nout y = a\n", "already defined"),
        ("input a\n", "no output"),
        ("out y = a\ninput a\n", "unknown name"),
        ("input r\nout y = r\n", "reserved"),
        ("input a\nout _w1 = a\n", "reserved"),
        ("input input\nout y = input\n", "keyword"),
        ("input a\nout y = a $ a\n", "unexpected"),
    ],
)
def test_parse_errors_say_what_and_where(src, fragment):
    with pytest.raises(ParseError) as err:
        parse(src)
    assert fragment in str(err.value)
    assert err.value.line >= 1 and err.value.col >= 1


def test_error_column_points_at_the_offending_token():
    with pytest.raises(ParseError) as err:
        parse("input a\nout y = a & zz\n")
    assert (err.value.line, err.value.col) == (2, 13)


# ---- masking policies -----------------------------------------------------------


@pytest.mark.parametrize("name", IDS)
def test_refresh_policy_start_is_secure(name):
    _, res = compiled(name, "refresh")
    assert res.start.secure


def test_naive_policy_leaks_when_a_sharing_meets_itself():
    _, res = compiled("square", "naive")
    assert not res.start.secure


# ---- the pipeline ------------------------------------------------------------------


@pytest.mark.parametrize("name", IDS)
def test_compiled_circuit_is_secure_and_computes_the_program(name):
    prog, res = compiled(name)
    assert res.constrained is not None
    assert res.constrained.secure
    assert seqc.check_function(prog, res.constrained.term)
    assert seqc.check_circuit(prog, res.constrained.term) is True


@pytest.mark.parametrize("name", IDS)
def test_optimiser_never_makes_the_start_worse_and_security_never_helps_cost(name):
    _, res = compiled(name)
    assert res.constrained.cost <= res.start.cost
    assert res.unconstrained.cost <= res.constrained.cost


def test_factoring_example_gets_much_cheaper_and_stays_secure():
    _, res = compiled("factor")
    assert res.constrained.cost < res.start.cost / 2
    assert res.constrained.secure


def test_square_unconstrained_prefers_the_leak_constrained_keeps_the_refresh():
    _, res = compiled("square")
    assert not res.unconstrained.secure
    assert res.constrained.secure
    assert res.unconstrained.cost < res.constrained.cost
    assert "refresh" in repr(res.constrained.term)


def test_naive_square_is_repaired_by_the_constraint():
    _, res = compiled("square", "naive")
    assert not res.start.secure
    assert res.constrained is not None and res.constrained.secure


def test_unused_input_is_allowed():
    prog = parse("input a, b, unused\nout y = a & b\n")
    res = seqc.compile_program(prog)
    assert res.constrained.secure
    assert seqc.check_function(prog, res.constrained.term)
    assert seqc.check_circuit(prog, res.constrained.term) is True


def test_a_program_without_ands_needs_no_randomness():
    prog = parse("input a, b\nout y = ~a ^ b\n")
    res = seqc.compile_program(prog)
    assert res.constrained.randoms == 0 and res.constrained.secure


# ---- emitters -----------------------------------------------------------------------


def assignments(prog, term):
    """Yield (ports assignment, expected output bits) over secrets and shares."""
    inputs, _, _ = seqc.gate_list(prog, term)
    secrets = [n for n in prog.inputs if f"{n}_s0" in inputs]
    rnd = [i for i in inputs if i.startswith("rnd")]
    for svals in itertools.product((0, 1), repeat=len(secrets)):
        env = dict(zip(secrets, svals, strict=True))
        full = {n: env.get(n, 0) for n in prog.inputs}
        want = [evaluate(ast, full) for _, ast in prog.outputs]
        for share0 in itertools.product((0, 1), repeat=len(secrets)):
            for rvals in itertools.product((0, 1), repeat=len(rnd)):
                ass = dict(zip(rnd, rvals, strict=True))
                for s, b0 in zip(secrets, share0, strict=True):
                    ass[f"{s}_s0"] = b0
                    ass[f"{s}_s1"] = b0 ^ env[s]
                yield ass, want


def run_verilog(text, ass):
    vals = dict(ass)
    for m in re.finditer(r"wire (\w+) = (.+?);", text):
        name, expr = m.groups()
        if "'b" in expr:
            vals[name] = int(expr.split("'b")[1])
        else:
            a, op, b = expr.split()
            vals[name] = (vals[a] & vals[b]) if op == "&" else (vals[a] ^ vals[b])
    for m in re.finditer(r"assign (\w+) = (\w+);", text):
        vals[m.group(1)] = vals[m.group(2)]
    return vals


@pytest.mark.parametrize("name", IDS)
def test_netlist_and_verilog_compute_the_program(name):
    prog, res = compiled(name)
    term = res.constrained.term
    net = seqc.emit_netlist(prog, term)
    ver = seqc.emit_verilog(prog, term, "m")
    n = 0
    for ass, want in assignments(prog, term):
        n += 1
        out = seqc.run_netlist(net, ass)
        vout = run_verilog(ver, ass)
        for i, (oname, _) in enumerate(prog.outputs):
            assert out[f"{oname}_s0"] ^ out[f"{oname}_s1"] == want[i]
            assert vout[f"{oname}_s0"] ^ vout[f"{oname}_s1"] == want[i]
    assert n > 0


def test_verilog_declares_ports_and_warns_about_glitches():
    prog, res = compiled("factor")
    ver = seqc.emit_verilog(prog, res.constrained.term, "factor")
    assert "module factor (" in ver and ver.rstrip().endswith("endmodule")
    assert "GLITCH-FREE" in ver and "NOT glitch-extended secure" in ver
    for port in ("input  a_s0", "input  rnd1", "output y_s0", "output y_s1"):
        assert port in ver


def test_verilog_rejects_keyword_names():
    prog = parse("input wire, b\nout y = wire & b\n")
    res = seqc.compile_program(prog)
    with pytest.raises(ValueError, match="Verilog keywords"):
        seqc.emit_verilog(prog, res.constrained.term)


def test_netlist_gate_count_matches_the_reported_gate_count():
    prog, res = compiled("adder")
    _, gates, _ = seqc.gate_list(prog, res.constrained.term)
    assert len([g for g in gates if g[1] != "const"]) == res.constrained.gates


# ---- command line --------------------------------------------------------------------


def test_cli_compiles_an_example(capsys):
    code = seqc.main([str(HERE / "examples" / "factor.sec")])
    out = capsys.readouterr().out
    assert code == 0
    assert "0 leaking wires" in out and "function equals the source" in out


def test_cli_reports_parse_errors_with_exit_code_2(tmp_path, capsys):
    bad = tmp_path / "bad.sec"
    bad.write_text("input a\nout y = a &\n")
    assert seqc.main([str(bad)]) == 2
    assert "line 2" in capsys.readouterr().err


def test_cli_writes_emitted_code(tmp_path, capsys):
    target = tmp_path / "f.v"
    code = seqc.main(
        [str(HERE / "examples" / "mux.sec"), "--emit", "verilog", "--out", str(target)]
    )
    capsys.readouterr()
    assert code == 0 and target.read_text().startswith("// Generated by seqc")


# ---- trust boundary -----------------------------------------------------------


@pytest.mark.parametrize("name", IDS)
def test_compiled_circuits_agree_with_verifmsi(name):
    from crosscheck import oracle_available

    if not oracle_available():
        pytest.skip("VerifMSI not available (a skip is not a pass)")
    _, res = compiled(name)
    n_wires, violations = seqc.crosscheck(res.constrained.term)
    assert n_wires > 0
    assert violations == []
