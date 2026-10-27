"""Tests for the language front end (design/0020).

The claims under test: the parser accepts exactly the documented language; the
masking pass yields a secure start under the refresh policy and can leak under
the naive one; the compiled circuit computes the source program; the security
constraint keeps what it must; the emitted netlist and Verilog compute the same
thing as the lowered circuit; and the in-house verdicts agree with VerifMSI.

Purpose
-------
These tests are the evidence for the compiler front end. They run every example
program in `examples/` through the whole pipeline and check, for each: the parse,
the masking policy, the optimiser's result (secure, computes the source, never worse
than the start, security never makes it cheaper), the emitted netlist and Verilog
(evaluated bit by bit against the source), the command line, and (if installed)
VerifMSI. Run with: uv run pytest experiments/frontend -q
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

EXAMPLES = sorted((HERE / "examples").glob("*.sec"))  # every example program file
IDS = [p.stem for p in EXAMPLES]  # file names without `.sec`, used as test ids


@functools.cache
def compiled(name, policy="refresh"):
    """Compile example `name` once per (name, policy) and cache the result.

    `functools.cache` remembers the return value, so the slow compile runs only once
    even though many tests use it. Returns `(parsed program, Result)`.
    """
    prog = parse((HERE / "examples" / f"{name}.sec").read_text())
    return prog, seqc.compile_program(prog, policy)


# ---- parser -------------------------------------------------------------------


def test_precedence_not_and_xor_or():
    """`~` binds tightest, then `&`, then `^`, then `|`."""
    prog = parse("input a, b, c, d\nout y = a | b ^ c & ~d\n")
    ((_, ast),) = prog.outputs  # unpack the single (name, ast) pair
    assert ast == (
        "or",
        ("var", "a"),
        ("xor", ("var", "b"), ("and", ("var", "c"), ("not", ("var", "d")))),
    )


def test_comments_blank_lines_and_multiple_outputs():
    """Comments, trailing comments and blank lines are ignored; several outputs work."""
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
    """A name used twice stands for one expression (so it becomes one gadget)."""
    prog = parse("input a, b\nt = a & b\nout y = t ^ t\n")
    ((_, ast),) = prog.outputs
    assert ast[1] == ast[2]  # both operands of the XOR are the same tree


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
    """Each malformed program raises a ParseError naming the problem and position."""
    with pytest.raises(ParseError) as err:
        parse(src)
    assert fragment in str(err.value)
    assert err.value.line >= 1 and err.value.col >= 1  # a real 1-based position


def test_error_column_points_at_the_offending_token():
    """The reported line and column point at the bad token (`zz`, line 2, column 13)."""
    with pytest.raises(ParseError) as err:
        parse("input a\nout y = a & zz\n")
    assert (err.value.line, err.value.col) == (2, 13)


# ---- masking policies -----------------------------------------------------------


@pytest.mark.parametrize("name", IDS)
def test_refresh_policy_start_is_secure(name):
    """With the refresh policy the masked start circuit is secure for every example."""
    _, res = compiled(name, "refresh")
    assert res.start.secure


def test_naive_policy_leaks_when_a_sharing_meets_itself():
    """Without refreshes, `z & z` feeds one sharing into both operands and leaks."""
    _, res = compiled("square", "naive")
    assert not res.start.secure


# ---- the pipeline ------------------------------------------------------------------


@pytest.mark.parametrize("name", IDS)
def test_compiled_circuit_is_secure_and_computes_the_program(name):
    """The chosen circuit is secure, equals the source, and reconstructs its outputs."""
    prog, res = compiled(name)
    assert res.constrained is not None
    assert res.constrained.secure
    assert seqc.check_function(prog, res.constrained.term)  # term-level equivalence
    # circuit-level reconstruction; `is True` rules out None ("too large to run")
    assert seqc.check_circuit(prog, res.constrained.term) is True


@pytest.mark.parametrize("name", IDS)
def test_optimiser_never_makes_the_start_worse_and_security_never_helps_cost(name):
    """Optimised <= start, and ignoring security can only be cheaper or equal."""
    _, res = compiled(name)
    assert res.constrained.cost <= res.start.cost
    assert res.unconstrained.cost <= res.constrained.cost


def test_factoring_example_gets_much_cheaper_and_stays_secure():
    """`factor.sec` more than halves its cost (26 -> 11) and remains secure."""
    _, res = compiled("factor")
    assert res.constrained.cost < res.start.cost / 2
    assert res.constrained.secure


def test_square_unconstrained_prefers_the_leak_constrained_keeps_the_refresh():
    """On the square, the cheapest circuit leaks; the secure one keeps the refresh."""
    _, res = compiled("square")
    assert not res.unconstrained.secure
    assert res.constrained.secure
    assert res.unconstrained.cost < res.constrained.cost
    assert "refresh" in repr(res.constrained.term)


def test_naive_square_is_repaired_by_the_constraint():
    """Starting from a LEAKING naive program, the constraint finds a secure circuit."""
    _, res = compiled("square", "naive")
    assert not res.start.secure
    assert res.constrained is not None and res.constrained.secure


def test_unused_input_is_allowed():
    """A declared input that the program never reads causes no problem."""
    prog = parse("input a, b, unused\nout y = a & b\n")
    res = seqc.compile_program(prog)
    assert res.constrained.secure
    assert seqc.check_function(prog, res.constrained.term)
    assert seqc.check_circuit(prog, res.constrained.term) is True


def test_a_program_without_ands_needs_no_randomness():
    """XOR and NOT are share-wise, so a program without ANDs uses no random bits."""
    prog = parse("input a, b\nout y = ~a ^ b\n")
    res = seqc.compile_program(prog)
    assert res.constrained.randoms == 0 and res.constrained.secure


# ---- emitters -----------------------------------------------------------------------


def assignments(prog, term):
    """Yield (ports assignment, expected output bits) over secrets and shares.

    Algorithm: for every value of the secrets the circuit reads, compute the expected
    outputs from the source; then for every choice of share 0 of each secret and every
    value of the random inputs, set share 1 = share 0 ^ secret and yield the ports.
    """
    inputs, _, _ = seqc.gate_list(prog, term)  # readable input port names
    # secrets that actually have ports (an unused input has none)
    secrets = [n for n in prog.inputs if f"{n}_s0" in inputs]
    rnd = [i for i in inputs if i.startswith("rnd")]  # the random input ports
    for svals in itertools.product((0, 1), repeat=len(secrets)):
        env = dict(zip(secrets, svals, strict=True))  # value of each secret
        full = {n: env.get(n, 0) for n in prog.inputs}  # unused inputs read as 0
        want = [evaluate(ast, full) for _, ast in prog.outputs]  # expected outputs
        for share0 in itertools.product((0, 1), repeat=len(secrets)):
            for rvals in itertools.product((0, 1), repeat=len(rnd)):
                ass = dict(zip(rnd, rvals, strict=True))  # random port values
                for s, b0 in zip(secrets, share0, strict=True):
                    ass[f"{s}_s0"] = b0  # share 0: free
                    ass[f"{s}_s1"] = b0 ^ env[s]  # share 1: share 0 ^ secret
                yield ass, want


def run_verilog(text, ass):
    """Evaluate the `wire` and `assign` lines of emitted Verilog for the inputs `ass`.

    A tiny interpreter, just enough for what `emit_verilog` produces: `wire n = a & b;`,
    `wire n = a ^ b;`, `wire n = 1'bX;` (a literal) and `assign port = wire;`. Returns
    the dict of all values.
    """
    vals = dict(ass)  # start with the input port values
    # `(\w+)` captures a name; `(.+?)` the expression up to the `;` (lazy match)
    for m in re.finditer(r"wire (\w+) = (.+?);", text):
        name, expr = m.groups()
        if "'b" in expr:
            vals[name] = int(expr.split("'b")[1])  # `1'b0` -> 0
        else:
            a, op, b = expr.split()  # e.g. "x & y" -> ["x", "&", "y"]
            vals[name] = (vals[a] & vals[b]) if op == "&" else (vals[a] ^ vals[b])
    for m in re.finditer(r"assign (\w+) = (\w+);", text):
        vals[m.group(1)] = vals[m.group(2)]  # copy a wire's value to an output port
    return vals


@pytest.mark.parametrize("name", IDS)
def test_netlist_and_verilog_compute_the_program(name):
    """Both emitted forms, evaluated bit by bit, equal the source on every input."""
    prog, res = compiled(name)
    term = res.constrained.term
    net = seqc.emit_netlist(prog, term)
    ver = seqc.emit_verilog(prog, term, "m")
    n = 0  # how many assignments were checked
    for ass, want in assignments(prog, term):
        n += 1
        out = seqc.run_netlist(net, ass)
        vout = run_verilog(ver, ass)
        for i, (oname, _) in enumerate(prog.outputs):
            # XOR of the two output shares must equal the source's output value
            assert out[f"{oname}_s0"] ^ out[f"{oname}_s1"] == want[i]
            assert vout[f"{oname}_s0"] ^ vout[f"{oname}_s1"] == want[i]
    assert n > 0  # the loop really ran


def test_verilog_declares_ports_and_warns_about_glitches():
    """The Verilog has the right module and ports, and states its glitch limitation."""
    prog, res = compiled("factor")
    ver = seqc.emit_verilog(prog, res.constrained.term, "factor")
    assert "module factor (" in ver and ver.rstrip().endswith("endmodule")
    assert "GLITCH-FREE" in ver and "NOT glitch-extended secure" in ver
    for port in ("input  a_s0", "input  rnd1", "output y_s0", "output y_s1"):
        assert port in ver


def test_verilog_rejects_keyword_names():
    """A program variable named like a Verilog keyword is refused at emission."""
    prog = parse("input wire, b\nout y = wire & b\n")
    res = seqc.compile_program(prog)
    with pytest.raises(ValueError, match="Verilog keywords"):
        seqc.emit_verilog(prog, res.constrained.term)


def test_netlist_gate_count_matches_the_reported_gate_count():
    """The emitted netlist has exactly as many gates as the report says."""
    prog, res = compiled("adder")
    _, gates, _ = seqc.gate_list(prog, res.constrained.term)
    # constants are listed as gates in the netlist but are not counted as gates
    assert len([g for g in gates if g[1] != "const"]) == res.constrained.gates


# ---- command line --------------------------------------------------------------------


def test_cli_compiles_an_example(capsys):
    """`seqc factor.sec` exits 0 and prints the verification lines."""
    code = seqc.main([str(HERE / "examples" / "factor.sec")])
    out = capsys.readouterr().out  # everything printed to standard output
    assert code == 0
    assert "0 leaking wires" in out and "function equals the source" in out


def test_cli_reports_parse_errors_with_exit_code_2(tmp_path, capsys):
    """A syntax error gives exit code 2 and a message naming the line."""
    bad = tmp_path / "bad.sec"  # a temporary file the test creates
    bad.write_text("input a\nout y = a &\n")
    assert seqc.main([str(bad)]) == 2
    assert "line 2" in capsys.readouterr().err  # the error goes to standard error


def test_cli_writes_emitted_code(tmp_path, capsys):
    """`--emit verilog --out FILE` writes a Verilog file starting with the header."""
    target = tmp_path / "f.v"
    code = seqc.main(
        [str(HERE / "examples" / "mux.sec"), "--emit", "verilog", "--out", str(target)]
    )
    capsys.readouterr()  # discard the printed report
    assert code == 0 and target.read_text().startswith("// Generated by seqc")


# ---- trust boundary -----------------------------------------------------------


@pytest.mark.parametrize("name", IDS)
def test_compiled_circuits_agree_with_verifmsi(name):
    """VerifMSI finds no disagreement on any wire of any compiled example."""
    from crosscheck import oracle_available

    if not oracle_available():
        pytest.skip("VerifMSI not available (a skip is not a pass)")
    _, res = compiled(name)
    n_wires, violations = seqc.crosscheck(res.constrained.term)
    assert n_wires > 0
    assert violations == []
