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

Purpose
-------
This is the FRONT END of the compiler: it reads a small Boolean program as text and
turns it into abstract syntax trees (ASTs), one per output. It is a hand-written
tokenizer plus a recursive-descent parser, with no parser-generator dependency
(design/0020). `seqc.py` takes these ASTs, masks them, optimises them and emits a
netlist or Verilog.

A worked example. The program
    input a, b
    out y = a & b ^ a
parses (`&` binds tighter than `^`) to the tree
    ("xor", ("and", ("var", "a"), ("var", "b")), ("var", "a"))
and `Program.inputs == ["a", "b"]`, `Program.outputs == [("y", <that tree>)]`.
"""

import re
from dataclasses import dataclass, field

KEYWORDS = {"input", "out"}  # words with a fixed meaning; cannot be used as names
# `r`, `r1`, ... name the compiler's fresh random bits; `_...` names generated wires
# `^` start of the name, `r\d*` is "r" plus optional digits, `_.*` is "_" plus anything
_RESERVED = re.compile(r"^(r\d*|_.*)$")
# One token. After optional whitespace (`\s*`), exactly one of four alternatives:
#   (#.*)                    group 1: a comment up to the end of the line
#   ([A-Za-z_][A-Za-z0-9_]*) group 2: a name (letters, digits, underscores)
#   (\d+)                    group 3: a number (rejected later: no constants)
#   (.)                      group 4: any other single character (an operator, etc.)
_TOKEN = re.compile(r"\s*(?:(#.*)|([A-Za-z_][A-Za-z0-9_]*)|(\d+)|(.))")


class ParseError(Exception):
    """A source error, with a 1-based line and column."""

    def __init__(self, message, line, col):
        """Store the position and build the message `line L, column C: message`."""
        super().__init__(f"line {line}, column {col}: {message}")
        self.line = line  # 1-based line number, e.g. 2
        self.col = col  # 1-based column number, e.g. 13


@dataclass
class Program:
    """A parsed program: its secret inputs and its exported outputs.

    Attributes:
        inputs: input names in declaration order, e.g. ["a", "b", "c"].
        outputs: `[(name, ast)]` in source order, e.g. [("y", ("xor", ...))].
    """

    inputs: list = field(default_factory=list)
    outputs: list = field(default_factory=list)  # [(name, ast)]

    def n_and(self):
        """Number of AND operations in the source (an `or` counts as one here)."""
        return sum(_count(ast, ("and", "or")) for _, ast in self.outputs)

    def n_xor(self):
        """Number of XOR operations in the source (an `or` counts as one here)."""
        return sum(_count(ast, ("xor", "or")) for _, ast in self.outputs)


def _count(ast, ops):
    """Count the nodes of `ast` whose operator is in `ops`.

    Algorithm: this node counts 1 if its operator (first element) is in `ops`, plus the
    count of every child that is itself a tuple (a sub-AST). Variable leaves have a
    string, not a tuple, as their second element, so they contribute 0.
    """
    n = 1 if ast[0] in ops else 0
    return n + sum(_count(c, ops) for c in ast[1:] if isinstance(c, tuple))


def tokenize(text):
    """Return [(kind, value, col)] for one line; kinds: name, num, sym.

    Algorithm, step by step:
      1. Start at position 0. Try to match one token at the current position.
      2. Stop if nothing matches (or the match is empty).
      3. Advance past the match. A comment ends the line; a name, number or symbol is
         recorded with the 1-based column where it starts.
      4. Whitespace-only matches record nothing.
    Example: `"t = a & b # note"` gives name t (col 1), sym = (col 3), name a (col 5),
    sym & (col 7), name b (col 9).
    """
    out = []  # tokens found so far
    pos = 0  # current position in the text
    while pos < len(text):
        m = _TOKEN.match(text, pos)  # try to match one token starting at `pos`
        if not m or m.end() == pos:  # no match, or a match that consumed nothing
            break
        pos = m.end()  # move past what was matched
        comment, name, num, sym = m.groups()  # exactly one of these is not None
        if comment is not None:
            break  # a comment runs to the end of the line
        if name is not None:
            # `m.start(2)` is where group 2 began (0-based); +1 makes the column 1-based
            out.append(("name", name, m.start(2) + 1))
        elif num is not None:
            out.append(("num", num, m.start(3) + 1))
        elif sym is not None and not sym.isspace():
            out.append(("sym", sym, m.start(4) + 1))
    return out


class _Parser:
    """A recursive-descent parser for ONE line's expression (internal).

    Attributes:
        toks: the line's tokens.
        i: index of the next unread token.
        line: the line number, for error messages.
        env: name -> AST of everything defined so far (shared across lines).
    """

    def __init__(self, toks, line_no, env):
        """Start at the first token of a line, with the program's name table."""
        self.toks, self.i, self.line, self.env = toks, 0, line_no, env

    def err(self, msg, col=None):
        """Raise a `ParseError`; the column defaults to the current token's."""
        if col is None:
            # the current token's column, or 1 if the line has run out of tokens
            col = self.toks[self.i][2] if self.i < len(self.toks) else 1
        raise ParseError(msg, self.line, col)

    def check_name(self, tok):
        """Reject a name token that is a keyword or reserved for the compiler."""
        if tok[1] in KEYWORDS:
            self.err(f"'{tok[1]}' is a keyword", tok[2])
        if _RESERVED.match(tok[1]):
            self.err(
                f"'{tok[1]}' is reserved (r, r1, ... are fresh random bits; "
                "names starting with '_' are generated wires)",
                tok[2],
            )

    def peek(self):
        """The next token without consuming it, or None at the end of the line."""
        return self.toks[self.i] if self.i < len(self.toks) else None

    def eat(self, kind, value=None):
        """Consume the next token if it matches `kind` (and `value`); else None.

        Example: `eat("sym", "&")` consumes an `&` and returns its token, or returns
        None and consumes nothing if the next token is anything else.
        """
        t = self.peek()
        if t is None or t[0] != kind or (value is not None and t[1] != value):
            return None
        self.i += 1  # move past the token we matched
        return t

    # The grammar, lowest precedence first (each level calls the next one down):
    #   expr  := xor_ ( "|" xor_ )*
    #   xor_  := and_ ( "^" and_ )*
    #   and_  := unary ( "&" unary )*
    #   unary := "~" unary | "(" expr ")" | name
    # Operators of equal precedence group to the left: `a ^ b ^ c` is `(a ^ b) ^ c`.

    def expr(self):
        """Parse `|` (the loosest-binding operator): `xor_ ( "|" xor_ )*`."""
        left = self.xor_()
        while self.eat("sym", "|"):  # as long as another `|` follows
            left = ("or", left, self.xor_())
        return left

    def xor_(self):
        """Parse `^`: `and_ ( "^" and_ )*`."""
        left = self.and_()
        while self.eat("sym", "^"):
            left = ("xor", left, self.and_())
        return left

    def and_(self):
        """Parse `&`: `unary ( "&" unary )*`."""
        left = self.unary()
        while self.eat("sym", "&"):
            left = ("and", left, self.unary())
        return left

    def unary(self):
        """Parse the tightest level: `~x`, a parenthesised expression, or a name."""
        if self.eat("sym", "~"):
            return ("not", self.unary())  # `~~a` works: unary calls itself
        if self.eat("sym", "("):
            e = self.expr()  # a full expression inside the parentheses
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
            # names are SUBSTITUTED: the stored AST is returned, so a name used twice
            # is one expression (and later one gadget)
            return self.env[t[1]]
        self.err(f"unexpected '{t[1]}'")


def parse(source):
    """Parse a program. Raises ParseError with a line and column.

    Algorithm, step by step, for each line of the source:
      1. Tokenize it; skip blank and comment-only lines.
      2. If it starts with `input`: read a comma-separated list of names, check each
         is valid and new, and record it as an input (its AST is `("var", name)`).
      3. Otherwise it is an assignment `name = expr` or `out name = expr`: read the
         name, check it, read `=`, parse the expression, and bind the name to the AST
         (single assignment: redefining a name is an error). An `out` line also adds
         the pair to the program's outputs.
      4. After the statement, any leftover token is an error.
    At the end the program must declare at least one input and export at least one
    output.
    """
    prog = Program()
    env = {}  # name -> ast (inputs map to ("var", name))
    out_names = set()  # names exported with `out` (recorded, not otherwise used)
    for line_no, text in enumerate(source.splitlines(), start=1):
        toks = tokenize(text)
        if not toks:
            continue  # a blank line or a comment
        p = _Parser(toks, line_no, env)
        first = toks[0]  # the first token decides the kind of statement
        if first[0] == "name" and first[1] == "input":
            p.i = 1  # start reading after the word `input`
            while True:
                t = p.eat("name")
                if t is None:
                    p.err("input name expected")
                p.check_name(t)
                if t[1] in env:
                    p.err(f"'{t[1]}' is already defined", t[2])
                env[t[1]] = ("var", t[1])
                prog.inputs.append(t[1])
                if not p.eat("sym", ","):  # no comma: the list is finished
                    break
        else:
            exported = bool(first[0] == "name" and first[1] == "out")
            p.i = 1 if exported else 0  # skip the `out` keyword if there is one
            name = p.eat("name")
            if name is None or name[1] in KEYWORDS:
                p.err("a name was expected before '='")
            p.check_name(name)
            if not p.eat("sym", "="):
                p.err("expected '='")
            if name[1] in env:
                p.err(f"'{name[1]}' is already defined", name[2])
            ast = p.expr()  # the right-hand side
            env[name[1]] = ast
            if exported:
                out_names.add(name[1])
                prog.outputs.append((name[1], ast))
        if p.peek() is not None:  # tokens left over after a complete statement
            p.err(f"unexpected '{p.peek()[1]}'")
    if not prog.inputs:
        raise ParseError("the program declares no inputs", 1, 1)
    if not prog.outputs:
        raise ParseError("the program exports no output (use 'out name = ...')", 1, 1)
    return prog


def evaluate(ast, env):
    """The unmasked Boolean value of an AST, given {input: 0/1}.

    Algorithm: recurse. A variable looks up its value; `not` is `1 - v` (flips 0/1);
    `and`, `xor` and `or` evaluate both operands and combine them with `&`, `^`, `|`.
    The dictionary builds all three results and indexes one, which is fine for 0/1.
    """
    op = ast[0]
    if op == "var":
        return env[ast[1]]
    if op == "not":
        return 1 - evaluate(ast[1], env)
    a, b = evaluate(ast[1], env), evaluate(ast[2], env)  # the two operand values
    return {"and": a & b, "xor": a ^ b, "or": a | b}[op]
