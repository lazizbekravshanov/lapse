"""The number guard: no number reaches the reader unless a tool produced it.

A language model can write a fluent sentence around a number it made up. This
check makes that impossible to miss: every number in a drafted answer must be

  - a number in a tool result from this turn, copied as written, or rounded
    while keeping at least two significant digits; or
  - a number the person typed in their own question.

A number written with a sign ("+0.24", "-0.59") must match a tool number with
that sign. Anything else is reported, and the harness refuses to show the draft.

What this cannot do: it proves a number came from the data, not that it is
attached to the right place or height. That is why every answer also lists the
files it was read from.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_MINUS = str.maketrans({"−": "-", "–": "-", "—": "-"})
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")                 # 3,713,756
_IDENTIFIER = re.compile(r"\b[A-Za-z][A-Za-z_]*[-_]?\d[\w.\-]*")    # MERRA-2, CO2, O3, v7.0, AIRS3STM, lat_14
_ORDINAL = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.I)
_LIST_MARK = re.compile(r"(?m)^\s*\d+[.)]\s+")                      # "1. " at the start of a line
_PER_TEN = re.compile(r"\b(?:per|every|each|a)\s+10\s+years\b|\b10[- ]year\b", re.I)   # same as "per ten years"
_NUMBER = re.compile(r"(?<![\w.])([+-]?)(\d+(?:\.\d+)?)(?!\.?\d)")

MIN_DIGITS = 2      # significant digits a rounded number must keep


@dataclass(frozen=True)
class Number:
    text: str        # as written, sign included
    value: float     # always positive
    sign: int        # +1 or -1 if a sign was written, else 0
    decimals: int


def numbers_in(text: str) -> list:
    """Every free-standing number in a piece of text. Names like MERRA-2 or CO2 are not numbers."""
    text = str(text).translate(_MINUS)
    text = _THOUSANDS.sub("", text)
    for pattern in (_IDENTIFIER, _ORDINAL, _LIST_MARK, _PER_TEN):
        text = pattern.sub(" ", text)
    out = []
    for m in _NUMBER.finditer(text):
        sign, digits = m.group(1), m.group(2)
        out.append(Number(text=sign + digits, value=float(digits),
                          sign={"+": 1, "-": -1, "": 0}[sign],
                          decimals=len(digits.split(".")[1]) if "." in digits else 0))
    return out


def pool(results: list, question: str = "") -> list:
    """Every signed number the answer is allowed to use: tool results and the question."""
    found = []

    def walk(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            if math.isfinite(x):
                found.append(float(x))
        elif isinstance(x, str):
            found.extend(n.value * (n.sign or 1) for n in numbers_in(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    walk(results)
    found.extend(n.value for n in numbers_in(question))            # the person's own numbers, either sign
    found.extend(-n.value for n in numbers_in(question))
    return found


def supported(n: Number, allowed: list) -> bool:
    half = 0.5 * 10.0 ** -n.decimals
    for x in allowed:
        if n.sign and x != 0 and (x > 0) != (n.sign > 0):
            continue
        gap = abs(abs(x) - n.value)
        if gap <= 1e-9:                                            # copied exactly
            return True
        if gap <= half + 1e-9 and x != 0:                          # rounded: are enough digits kept?
            kept = math.floor(math.log10(abs(x))) + 1 + n.decimals
            if kept >= MIN_DIGITS:
                return True
    return False


def check(answer: str, question: str, results: list) -> list:
    """Return the problems with a drafted answer. An empty list means it may be shown."""
    allowed = pool(results, question)
    bad, seen = [], set()
    for n in numbers_in(answer):
        if n.text not in seen and not supported(n, allowed):
            seen.add(n.text)
            bad.append(n.text)
    return [f"The number {b} is not in any tool result." for b in bad]
