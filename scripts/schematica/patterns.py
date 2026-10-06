"""WorldEdit-style block patterns: weighted random material lists.

Accepted syntax (comma- or ``+``-separated)::

    stone_bricks                          # single block
    stone_bricks,mossy_stone_bricks       # equal choice
    3x stone_bricks, cracked_stone_bricks # weight 3 vs 1
    75%stone_bricks,25%mossy              # percent weights (relative, need not sum to 100)
    oak_log[axis=y]                       # full blockstate strings are fine

Weights are *relative* (like WorldEdit: ``5%dirt,15%stone`` means 25%/75%).
"""
from __future__ import annotations

import re

_WEIGHT_PCT = re.compile(r"^(\d+(?:\.\d+)?)\s*%\s*(.+)$")
_WEIGHT_X = re.compile(r"^(\d+(?:\.\d+)?)\s*[x×]\s*(.+)$")


def parse_pattern(text: str | list[str] | tuple[str, ...]) -> list[tuple[str, float]]:
    """Parse a pattern string into ``[(blockstate, weight), ...]``.

    Raises ValueError on empty/invalid patterns (no tokens, non-positive
    weights, or a missing block name).
    """
    if isinstance(text, (list, tuple)):
        items = [(str(b), 1.0) for b in text]
        if not items:
            raise ValueError("pattern cannot be an empty list")
        return items
    tokens = [t.strip() for t in re.split(r"[,+|]", text) if t.strip()]
    if not tokens:
        raise ValueError("pattern is empty")
    out: list[tuple[str, float]] = []
    for tok in tokens:
        if re.fullmatch(r"\d+(?:\.\d+)?\s*(?:%|[x×])", tok):
            raise ValueError(f"weight without block name in {tok!r}")
        m = _WEIGHT_PCT.match(tok) or _WEIGHT_X.match(tok)
        if m:
            w, b = float(m.group(1)), m.group(2).strip()
            if w <= 0:
                raise ValueError(f"pattern weight must be positive in {tok!r}")
        else:
            w, b = 1.0, tok
        if not b:
            raise ValueError(f"pattern token missing block name in {tok!r}")
        out.append((b, w))
    return out


def is_weighted_pattern(text: str) -> bool:
    """Heuristic: does this look like a weighted pattern (vs a plain list)?"""
    return bool(re.search(r"\d+(?:\.\d+)?\s*(?:%|[x×])", text))


def cumulative(pattern: list[tuple[str, float]]) -> list[float]:
    """Cumulative distribution (last == 1.0) over pattern weights."""
    total = sum(w for _, w in pattern)
    if total <= 0:
        raise ValueError("pattern weights must sum to a positive value")
    acc = 0.0
    out: list[float] = []
    for _, w in pattern:
        acc += w
        out.append(acc / total)
    out[-1] = 1.0
    return out
