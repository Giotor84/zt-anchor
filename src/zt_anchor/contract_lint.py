"""Deterministic lint for Italian contracts and agreements: no ML, no network, every finding has offsets.

Checks:
- ``check_amounts``     amount in digits vs amount in words: "€ 74.000,00 (settantaquattromila/00)";
- ``check_sections``    required sections/headings are present;
- ``check_definitions`` defined terms ("di seguito, il «Debitore»") that are never used again;
- ``check_references``  internal references ("art. 7", "articolo 12") to articles that do not exist,
                        ignoring citations of laws and codes ("art. 2043 c.c.", "art. 5 d.lgs. 231/2001").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

from .it_normalize import parse_amount, words_to_number


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str        # "error" | "warning" | "info"
    message: str
    start: int
    end: int
    excerpt: str


def _f(rule: str, severity: str, message: str, text: str, start: int, end: int) -> Finding:
    return Finding(rule, severity, message, start, end, text[start:end])


_AMOUNT_WITH_WORDS = re.compile(
    r"(?:€|euro|eur)\s*(?P<num>\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)\s*"
    r"\(\s*(?:euro\s+)?(?P<words>[a-zàèéìòù\s'/\-0-9]+?)\s*\)",
    re.IGNORECASE,
)


def check_amounts(text: str) -> list[Finding]:
    out: list[Finding] = []
    for m in _AMOUNT_WITH_WORDS.finditer(text):
        digits = parse_amount(m.group("num"))
        words = words_to_number(m.group("words"))
        if words is None:
            out.append(_f("amount_words_unreadable", "warning",
                          "amount in words not readable", text, m.start(), m.end()))
        elif digits is not None and digits != words:
            out.append(_f("amount_mismatch", "error",
                          f"digits say {digits}, words say {words}", text, m.start(), m.end()))
    return out


def check_sections(text: str, required: Iterable[str]) -> list[Finding]:
    out = []
    for title in required:
        if not re.search(rf"(?im)^\s*(?:\d+[.)]?\s*|art(?:icolo|\.)\s*\d+\s*[-–.:]?\s*)?{re.escape(title)}\b", text):
            out.append(Finding("section_missing", "error", f"missing section: {title}", 0, 0, ""))
    return out


_DEF = re.compile(r"\((?:di seguito|in seguito|d'ora innanzi|breviter)?[^()]{0,30}?[«\"“]([^»\"”]{2,60})[»\"”]\s*\)",
                  re.IGNORECASE)


def check_definitions(text: str) -> list[Finding]:
    out = []
    for m in _DEF.finditer(text):
        term = m.group(1).strip()
        rest = text[m.end():]
        if not re.search(rf"\b{re.escape(term)}\b", rest):
            out.append(_f("definition_unused", "warning", f"defined term never used: {term}", text, m.start(), m.end()))
    return out


_ART_HEAD = re.compile(r"(?im)^\s*art(?:icolo|\.)\s*(\d+)")
_ART_REF = re.compile(r"\bart(?:icol[oi]|t?\.)\s*(\d+)(?:\s*(?:,|e)\s*(\d+))?", re.IGNORECASE)
_LAW_AFTER = re.compile(
    r"^[\s,]*(?:(?:comma|co\.|lett\.|lettera|n\.|num\.)\s*\w+[\s,]*)*"
    r"(?:c\.?\s?c\.|c\.?\s?p\.?\s?c\.|c\.?\s?p\.|cod\.|codice|d\.?\s?lgs|d\.?\s?l\.|d\.?\s?p\.?\s?r|l\.|legge|reg\.|regolamento|r\.?\s?d\.|tub|tuf|cost\.)",
    re.IGNORECASE,
)


def check_references(text: str) -> list[Finding]:
    defined = {int(n) for n in _ART_HEAD.findall(text)}
    out = []
    for m in _ART_REF.finditer(text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        if _ART_HEAD.match(text, line_start) and _ART_HEAD.match(text, line_start).end() >= m.end() - 1:
            continue  # the heading itself
        if _LAW_AFTER.match(text[m.end():m.end() + 40]):
            continue  # citation of a law or code, not an internal reference
        for g in (m.group(1), m.group(2)):
            if g and int(g) not in defined:
                out.append(_f("reference_missing", "error", f"refers to art. {g}, which is not in the document",
                              text, m.start(), m.end()))
    return out


def lint(text: str, required_sections: Optional[Iterable[str]] = None) -> list[Finding]:
    findings = check_amounts(text) + check_definitions(text) + check_references(text)
    if required_sections:
        findings += check_sections(text, required_sections)
    return sorted(findings, key=lambda f: (f.start, f.rule))
