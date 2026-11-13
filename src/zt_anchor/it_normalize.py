"""Italian amounts, number words, dates and yes/no flags — the parsing bugs that real documents and exports hit.

- ``parse_amount("€ 1.234,56")`` -> Decimal("1234.56"); also "€ 351212", "1.234" (thousands), "-1.000,5".
- ``words_to_number("settantaquattromila/00")`` -> Decimal("74000.00") (contracts write amounts in letters too).
- ``parse_date_it("12 febbraio 2026")`` -> date; two-digit years are refused unless explicitly allowed.
- ``flag(x)`` -> bool that treats NaN, "", "no", "0" as False (``bool(float("nan"))`` is True in Python).
"""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

# ---------------------------------------------------------------- amounts in digits

_AMOUNT_RE = re.compile(r"(?<![\w.,])[-+]?\d{1,3}(?:[.\s '’]\d{3})+(?:,\d+)?(?![\w])|(?<![\w.,])[-+]?\d+(?:[.,]\d+)?(?![\w])")


def parse_amount(text: object) -> Optional[Decimal]:
    """Parse an Italian-formatted amount; None when there is no number or it is ambiguous."""
    if text is None:
        return None
    if isinstance(text, (int, Decimal)) and not isinstance(text, bool):
        return Decimal(text)
    if isinstance(text, float):
        return None if math.isnan(text) else Decimal(str(text))
    s = str(text).strip()
    s = re.sub(r"(?i)\b(?:eur|euro)\b|€", "", s).strip()
    s = s.replace(" ", "").replace(" ", "").replace("'", "").replace("’", "")
    if not s or not re.fullmatch(r"[-+]?[\d.,]+", s):
        return None
    sign = -1 if s.startswith("-") else 1
    s = s.lstrip("+-")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        if s.count(",") > 1:
            return None
        s = s.replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            if not all(len(p) == 3 for p in parts[1:]):
                return None
            s = s.replace(".", "")  # Italian thousands separator
    try:
        return sign * Decimal(s)
    except InvalidOperation:
        return None


def find_amounts(text: str) -> list[Decimal]:
    """All amounts written in digits inside a text, in order."""
    out = []
    for m in _AMOUNT_RE.finditer(text):
        v = parse_amount(m.group(0))
        if v is not None:
            out.append(v)
    return out


# ---------------------------------------------------------------- amounts in words

_UNITS = {
    "zero": 0, "un": 1, "uno": 1, "una": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6, "sette": 7,
    "otto": 8, "nove": 9, "dieci": 10, "undici": 11, "dodici": 12, "tredici": 13, "quattordici": 14,
    "quindici": 15, "sedici": 16, "diciassette": 17, "diciotto": 18, "diciannove": 19,
}
_TENS = {"venti": 20, "trenta": 30, "quaranta": 40, "cinquanta": 50, "sessanta": 60, "settanta": 70,
         "ottanta": 80, "novanta": 90}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _lt100(s: str) -> int:
    if s in _UNITS:
        return _UNITS[s]
    for word, val in _TENS.items():
        for stem in (word, word[:-1]):  # "ventuno", "trentotto": the final vowel drops before uno/otto
            if s.startswith(stem):
                rest = s[len(stem):]
                if rest == "":
                    if stem == word:
                        return val
                    continue
                if rest in _UNITS and 1 <= _UNITS[rest] <= 9 and (stem == word) != (rest in ("uno", "otto")):
                    return val + _UNITS[rest]
    raise ValueError(s)


def _lt1000(s: str) -> int:
    if s == "":
        return 0
    s = s.replace("centott", "centoott")  # "centottanta" -> "cento" + "ottanta"
    i = s.find("cento")
    if i < 0:
        return _lt100(s)
    pre, post = s[:i], s[i + 5:]
    hundreds = 1 if pre == "" else _UNITS[pre]
    if not 1 <= hundreds <= 9:
        raise ValueError(s)
    return hundreds * 100 + (_lt100(post) if post else 0)


def _parse_words(s: str) -> int:
    for word, mult in (("miliardi", 10**9), ("miliardo", 10**9), ("milioni", 10**6), ("milione", 10**6)):
        i = s.find(word)
        if i >= 0:
            pre, post = s[:i], s[i + len(word):]
            n = 1 if pre in ("", "un", "uno") else _parse_words(pre)
            return n * mult + (_parse_words(post) if post else 0)
    if s.startswith("mille"):
        return 1000 + _lt1000(s[5:])
    i = s.find("mila")
    if i >= 0:
        return _lt1000(s[:i]) * 1000 + _lt1000(s[i + 4:])
    return _lt1000(s)


def words_to_number(text: str) -> Optional[Decimal]:
    """Italian number words to Decimal: "settantaquattromila/00", "un milione e duecentomila", "ventitré".

    Cents may follow as "/00", "/50" or "virgola cinquanta". Returns None when the text is not a number.
    """
    s = _strip_accents(text.lower())
    s = re.sub(r"\b(?:euro|eur|€)\b|€", " ", s)
    cents = Decimal(0)
    m = re.search(r"/\s*(\d{1,2})\s*$", s)
    if m:
        cents = Decimal(m.group(1).ljust(2, "0")) / 100
        s = s[: m.start()]
    elif "virgola" in s:
        s, dec = s.split("virgola", 1)
        dec = re.sub(r"[\s\-]", "", dec)
        try:
            d = _lt100(dec) if dec else 0
        except (ValueError, KeyError):
            return None
        cents = Decimal(d) / 100
    s = re.sub(r"\s+e\s+", " ", f" {s} ")
    s = re.sub(r"[\s\-]", "", s)
    if not s or not s.isalpha():
        return None
    try:
        return Decimal(_parse_words(s)) + cents
    except (ValueError, KeyError):
        return None


# ---------------------------------------------------------------- dates

_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
    "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6, "lug": 7, "ago": 8, "set": 9, "sett": 9,
    "ott": 10, "nov": 11, "dic": 12,
}
_DATE_NUM = re.compile(r"\b(\d{1,2})[./\-](\d{1,2})[./\-](\d{2}|\d{4})\b")
_DATE_TXT = re.compile(r"\b(\d{1,2})\s*(?:°|º)?\s+([A-Za-z]{3,9})\.?\s+(\d{2}|\d{4})\b")


def parse_date_it(text: str, allow_two_digit_year: bool = False) -> Optional[date]:
    """First Italian date in ``text`` (day first). None when absent, invalid, or the year has two digits and
    ``allow_two_digit_year`` is False: guessing the century is a decision, not a parse."""
    for rx in (_DATE_TXT, _DATE_NUM):
        m = rx.search(text)
        if not m:
            continue
        d, mo, y = m.group(1), m.group(2), m.group(3)
        month = _MONTHS.get(mo.lower()) if not mo.isdigit() else int(mo)
        if month is None:
            continue
        if len(y) == 2:
            if not allow_two_digit_year:
                return None
            y = "20" + y
        try:
            return date(int(y), month, int(d))
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------- flags

_TRUE = {"1", "si", "sì", "s", "y", "yes", "true", "vero", "x", "ok"}
_FALSE = {"0", "no", "n", "false", "falso", "", "nan", "none", "null", "-"}


def flag(value: object) -> bool:
    """Yes/no from spreadsheets and exports. NaN, None and empty strings are False."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return not (isinstance(value, float) and math.isnan(value)) and value != 0
    s = str(value).strip().lower()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    raise ValueError(f"not a yes/no value: {value!r}")
