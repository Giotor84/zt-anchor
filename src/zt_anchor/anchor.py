"""Verbatim anchoring: every claim of a model must point to an exact span of a source document.

Offsets are computed here, in Python, never by the model. The search tolerates only differences that do not
change meaning (case, whitespace runs, typographic quotes and dashes, words hyphenated across a line break);
anything else means the quote is not in the source and the claim is not anchored.
"""
from __future__ import annotations

import re

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Iterable, Mapping, Optional, Union

_QUOTES = {"‘": "'", "’": "'", "‚": "'", "‛": "'", "`": "'", "´": "'",
           "“": '"', "”": '"', "„": '"', "«": '"', "»": '"'}
_DASHES = {"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-"}
_DROP = {"­", "​", "﻿"}  # soft hyphen, zero-width space, BOM


@dataclass(frozen=True)
class Source:
    id: str
    text: str


@dataclass(frozen=True)
class Anchor:
    source_id: str
    start: int
    end: int
    text: str            # the exact original span, source.text[start:end]
    occurrences: int = 1  # > 1: the quote appears more than once, the first one is returned


def _normalize(text: str) -> tuple[str, list[int]]:
    """Normalized text plus, for each normalized char, its index in the original."""
    out: list[str] = []
    idx: list[int] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in _DROP:
            i += 1
            continue
        if c == "-" and i + 1 < n:  # word hyphenated across a line break: "contrat-\n  to" -> "contratto"
            j = i + 1
            while j < n and text[j] in " \t":
                j += 1
            if j < n and text[j] in "\r\n":
                while j < n and text[j].isspace():
                    j += 1
                i = j
                continue
        if c.isspace():
            if out and out[-1] != " ":
                out.append(" ")
                idx.append(i)
            i += 1
            continue
        c = _QUOTES.get(c, _DASHES.get(c, c))
        for ch in c.casefold():
            out.append(ch)
            idx.append(i)
        i += 1
    return "".join(out), idx


def _anchor_on_normalized(source: Source, norm_t: str, idx: list[int], quote: str) -> Optional[Anchor]:
    norm_q, _ = _normalize(quote)
    norm_q = norm_q.strip()
    if not norm_q:
        return None
    pos = norm_t.find(norm_q)
    matched_len = len(norm_q)
    if pos < 0 and "-" in norm_q:
        # Handle compound words split at EOL in source ("decreto-\nlegge" -> "decretolegge" vs quote "decreto-legge")
        dehyph_q = re.sub(r"(?<=\w)-(?=\w)", "", norm_q)
        if dehyph_q and dehyph_q != norm_q:
            pos = norm_t.find(dehyph_q)
            matched_len = len(dehyph_q)
            norm_q = dehyph_q
    if pos < 0:
        return None
    occurrences = norm_t.count(norm_q)
    start = idx[pos]
    end = idx[pos + matched_len - 1] + 1
    return Anchor(source.id, start, end, source.text[start:end], occurrences)


def anchor_quote(source: Source, quote: str) -> Optional[Anchor]:
    """Find ``quote`` in ``source`` and return the exact original span, or None if it is not there."""
    norm_t, idx = _normalize(source.text)
    return _anchor_on_normalized(source, norm_t, idx, quote)


class AnchorStatus(str, Enum):
    ANCHORED = "anchored"
    AMBIGUOUS = "ambiguous"          # found more than once: the position is not unique
    NOT_FOUND = "not_found"          # the quote is not in the source: likely invented
    SOURCE_UNKNOWN = "source_unknown"
    NO_QUOTE = "no_quote"


@dataclass(frozen=True)
class Claim:
    """What a model extracted: a field, its value, the verbatim quote supporting it and the source id."""
    field: str
    value: Union[str, int, float, Decimal, None]
    quote: str
    source_id: str


@dataclass(frozen=True)
class CheckedClaim:
    claim: Claim
    status: AnchorStatus
    anchor: Optional[Anchor]
    value_in_quote: Optional[bool]   # None when it cannot be checked (no anchor, no value)


def _value_in_quote(value: object, quote: str) -> Optional[bool]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        from .it_normalize import find_amounts
        return any(a == Decimal(str(value)) for a in find_amounts(quote))
    return _normalize(str(value))[0].strip() in _normalize(quote)[0]


def check_claims(claims: Iterable[Claim], sources: Union[Mapping[str, Source], Iterable[Source]]) -> list[CheckedClaim]:
    """Anchor every claim to its source and check that the value is actually inside the anchored span."""
    by_id = dict(sources) if isinstance(sources, Mapping) else {s.id: s for s in sources}
    norm_cache: dict[str, tuple[str, list[int]]] = {}
    out: list[CheckedClaim] = []
    for c in claims:
        src = by_id.get(c.source_id)
        if src is None:
            out.append(CheckedClaim(c, AnchorStatus.SOURCE_UNKNOWN, None, None))
            continue
        if not c.quote or not c.quote.strip():
            out.append(CheckedClaim(c, AnchorStatus.NO_QUOTE, None, None))
            continue
        cached = norm_cache.get(src.id)
        if cached is None:
            cached = _normalize(src.text)
            norm_cache[src.id] = cached
        a = _anchor_on_normalized(src, cached[0], cached[1], c.quote)
        if a is None:
            out.append(CheckedClaim(c, AnchorStatus.NOT_FOUND, None, None))
            continue
        status = AnchorStatus.AMBIGUOUS if a.occurrences > 1 else AnchorStatus.ANCHORED
        out.append(CheckedClaim(c, status, a, _value_in_quote(c.value, a.text)))
    return out
