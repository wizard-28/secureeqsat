"""The source language of the SecureEqSat compiler front end (design/0020).

    # comments run to the end of the line
    input a, b, c
    t = a & b
    out y = t ^ (a & c)

Statements are one per line:

  input x, y, ...     declare secret inputs (each becomes a 2-share sharing)
  name = expr         bind a name to an expression (single assignment)
  out name = expr     bind a name and export it as an output

Operators, highest precedence first: `~` (not), `&` (and), `^` (xor), `|` (or).
Names are substituted on use, so an expression used twice is one expression
(and one gadget). There are no constants: a share-wise constant has no
sharing (`~x` is supported).

An AST is a nested tuple: ("var", name), ("not", e), ("and", l, r),
("xor", l, r), ("or", l, r).
"""

import re
from dataclasses import dataclass, field

KEYWORDS = {"input", "out"}
# `r`, `r1`, ... name the compiler's fresh random bits; `_...` names generated wires
_RESERVED = re.compile(r"^(r\d*|_.*)$")
_TOKEN = re.compile(r"\s*(?:(#.*)|([A-Za-z_][A-Za-z0-9_]*)|(\d+)|(.))")


class ParseError(Exception):
    """A source error, with a 1-based line and column."""

    def __init__(self, message, line, col):
        super().__init__(f"line {line}, column {col}: {message}")
        self.line = line
        self.col = col


@dataclass
class Program:
    inputs: list = field(default_factory=list)
    outputs: list = field(default_factory=list)  # [(name, ast)]

    def n_and(self):
        return sum(_count(ast, ("and", "or")) for _, ast in self.outputs)

    def n_xor(self):
        return sum(_count(ast, ("xor", "or")) for _, ast in self.outputs)


def _count(ast, ops):
    n = 1 if ast[0] in ops else 0
    return n + sum(_count(c, ops) for c in ast[1:] if isinstance(c, tuple))


def tokenize(text):
    """Return [(kind, value, col)] for one line; kinds: name, num, sym."""
    out = []
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        comment, name, num, sym = m.groups()
        if comment is not None:
            break
        if name is not None:
            out.append(("name", name, m.start(2) + 1))
        elif num is not None:
            out.append(("num", num, m.start(3) + 1))
        elif sym is not None and not sym.isspace():
            out.append(("sym", sym, m.start(4) + 1))
    return out


class _Parser:
    def __init__(self, toks, line_no, env):
        self.toks, self.i, self.line, self.env = toks, 0, line_no, env

    def err(self, msg, col=None):
        if col is None:
            col = self.toks[self.i][2] if self.i < len(self.toks) else 1
        raise ParseError(msg, self.line, col)

    def check_name(self, tok):
        if tok[1] in KEYWORDS:
            self.err(f"'{tok[1]}' is a keyword", tok[2])
        if _RESERVED.match(tok[1]):
            self.err(
                f"'{tok[1]}' is reserved (r, r1, ... are fresh random bits; "
                "names starting with '_' are generated wires)",
                tok[2],
            )

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def eat(self, kind, value=None):
        t = self.peek()
        if t is None or t[0] != kind or (value is not None and t[1] != value):
            return None
        self.i += 1
        return t

    def expr(self):
        left = self.xor_()
        while self.eat("sym", "|"):
            left = ("or", left, self.xor_())
        return left

    def xor_(self):
        left = self.and_()
        while self.eat("sym", "^"):
            left = ("xor", left, self.and_())
        return left

    def and_(self):
        left = self.unary()
        while self.eat("sym", "&"):
            left = ("and", left, self.unary())
        return left

    def unary(self):
        if self.eat("sym", "~"):
            return ("not", self.unary())
        if self.eat("sym", "("):
            e = self.expr()
            if not self.eat("sym", ")"):
                self.err("expected ')'")
            return e
        t = self.peek()
        if t is None:
            self.err("expression expected at end of line")
        if t[0] == "num":
            self.err("constants are not supported (use ~x for a share-wise NOT)")
        if t[0] == "name":
            if t[1] in KEYWORDS:
                self.err(f"'{t[1]}' is a keyword")
            if t[1] not in self.env:
                self.err(f"unknown name '{t[1]}'", t[2])
            self.i += 1
            return self.env[t[1]]
        self.err(f"unexpected '{t[1]}'")


def parse(source):
    """Parse a program. Raises ParseError with a line and column."""
    prog = Program()
    env = {}  # name -> ast (inputs map to ("var", name))
    out_names = set()
    for line_no, text in enumerate(source.splitlines(), start=1):
        toks = tokenize(text)
        if not toks:
            continue
        p = _Parser(toks, line_no, env)
        first = toks[0]
        if first[0] == "name" and first[1] == "input":
            p.i = 1
            while True:
                t = p.eat("name")
                if t is None:
                    p.err("input name expected")
                p.check_name(t)
                if t[1] in env:
                    p.err(f"'{t[1]}' is already defined", t[2])
                env[t[1]] = ("var", t[1])
                prog.inputs.append(t[1])
                if not p.eat("sym", ","):
                    break
        else:
            exported = bool(first[0] == "name" and first[1] == "out")
            p.i = 1 if exported else 0
            name = p.eat("name")
            if name is None or name[1] in KEYWORDS:
                p.err("a name was expected before '='")
            p.check_name(name)
            if not p.eat("sym", "="):
                p.err("expected '='")
            if name[1] in env:
                p.err(f"'{name[1]}' is already defined", name[2])
            ast = p.expr()
            env[name[1]] = ast
            if exported:
                out_names.add(name[1])
                prog.outputs.append((name[1], ast))
        if p.peek() is not None:
            p.err(f"unexpected '{p.peek()[1]}'")
    if not prog.inputs:
        raise ParseError("the program declares no inputs", 1, 1)
    if not prog.outputs:
        raise ParseError("the program exports no output (use 'out name = ...')", 1, 1)
    return prog


def evaluate(ast, env):
    """The unmasked Boolean value of an AST, given {input: 0/1}."""
    op = ast[0]
    if op == "var":
        return env[ast[1]]
    if op == "not":
        return 1 - evaluate(ast[1], env)
    a, b = evaluate(ast[1], env), evaluate(ast[2], env)
    return {"and": a & b, "xor": a ^ b, "or": a | b}[op]
