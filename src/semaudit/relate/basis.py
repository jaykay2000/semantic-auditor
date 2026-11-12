"""Declared bases: the other forms in which a fact's true value may correctly be shown.

A price can be right in more than one form: before or after VAT, before or after a promotion. An owner who
accepts a second form says so in the contract, on the fact, as a basis: a named arithmetic expression over the
fact's own true value and other facts' true values at the same moment, optionally limited to some surfaces and
to moments when a condition holds. A claim that misses the fact's truth but states one of the bases declared for
its surface is a correct claim in that basis, never a violation; the issue text and the review say which basis.

A basis is evaluation only. The extractor never sees it, so adding one changes no extraction (and no cache key):
an owner can accept a form after a review and re-run the review for free.

Grammar (kept small on purpose, so a basis reads like the owner's own sentence): numbers, fact ids, + - * /,
parentheses, and in `when` one comparison (< <= > >= == !=) joined by `and` / `or`. A fact with no true value at
that moment makes the basis unavailable there, never zero.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Callable
from typing import Any

_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b}
_CMP = {ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b,
        ast.GtE: lambda a, b: a >= b, ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b}


class Unavailable(Exception):
    """A name the expression needs has no true value at this moment (or a division by zero)."""


def names(expr: str) -> set[str]:
    """Every fact id the expression reads. Raises ValueError on anything outside the grammar."""
    tree = ast.parse(expr, mode="eval")
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif not isinstance(n, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.USub, ast.UAdd, ast.Constant,
                                ast.Compare, ast.BoolOp, ast.And, ast.Or, ast.Load, *_BIN, *_CMP)):
            raise ValueError(f"not allowed in a basis: {type(n).__name__}")
        if isinstance(n, ast.Constant) and (isinstance(n.value, bool) or not isinstance(n.value, (int, float))):
            raise ValueError(f"not allowed in a basis: the constant {n.value!r}")
    return out


def evaluate(expr: str, value: Callable[[str], Any]) -> Any:
    """The expression's value, reading each fact id through `value`. Raises Unavailable."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Name):
            v = value(n.id)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise Unavailable(n.id)
            return float(v)
        if isinstance(n, ast.UnaryOp):
            return -ev(n.operand) if isinstance(n.op, ast.USub) else ev(n.operand)
        if isinstance(n, ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Div) and b == 0:
                raise Unavailable("division by zero")
            return _BIN[type(n.op)](a, b)
        if isinstance(n, ast.Compare):
            left, ok = ev(n.left), True
            for op, right in zip(n.ops, n.comparators):
                r = ev(right)
                ok = ok and _CMP[type(op)](left, r)
                left = r
            return ok
        if isinstance(n, ast.BoolOp):
            vals = [ev(v) for v in n.values]
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        raise ValueError(type(n).__name__)
    names(expr)                                          # refuse anything outside the grammar before reading
    return ev(ast.parse(expr, mode="eval"))


def values(fact, surface: str | None, truth: Any, value: Callable[[str], Any]) -> list[tuple[str, float]]:
    """(basis id, value) for every basis the fact declares that applies on this surface at this moment. `truth` is
    the fact's own true value as the rule compares it (so a rule that names an oracle gets that oracle's basis);
    every other name reads through `value`. A basis whose inputs are missing is left out."""
    out = []
    for b in getattr(fact, "bases", None) or []:
        if b.surfaces and surface not in b.surfaces:
            continue
        look = lambda n: truth if n == fact.id else value(n)   # noqa: E731
        try:
            if b.when and not evaluate(b.when, look):
                continue
            v = evaluate(b.value, look)
        except Unavailable:
            continue
        if b.round:
            v = round(round(v / b.round) * b.round, 10)
        if not math.isfinite(v):
            continue
        out.append((b.id, v))
    return out
