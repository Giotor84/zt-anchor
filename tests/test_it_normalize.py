import math
from datetime import date
from decimal import Decimal

import pytest

from zt_anchor import find_amounts, flag, parse_amount, parse_date_it, words_to_number


@pytest.mark.parametrize("text,expected", [
    ("€ 1.234,56", "1234.56"), ("1.234,56 €", "1234.56"), ("EUR 1234,5", "1234.5"), ("€ 351212", "351212"),
    ("1.234", "1234"), ("12.345.678", "12345678"), ("1,5", "1.5"), ("-1.000,50", "-1000.50"), ("1.5", "1.5"),
    ("1 234,00", "1234.00"),
])
def test_parse_amount(text, expected):
    assert parse_amount(text) == Decimal(expected)


@pytest.mark.parametrize("text", ["", "abc", "1,2,3", "1.23.4", None, float("nan")])
def test_parse_amount_refuses(text):
    assert parse_amount(text) is None


def test_find_amounts():
    assert find_amounts("rate da € 1.200,00 per 12 mesi, saldo 350") == [Decimal("1200.00"), Decimal("12"), Decimal("350")]


@pytest.mark.parametrize("words,expected", [
    ("settantaquattromila", 74000), ("settantaquattromila/00", 74000), ("dodicimilacinquecento/50", "12500.50"),
    ("centottantamila", 180000), ("duemilacinquecentoventuno", 2521), ("un milione e duecentomila", 1200000),
    ("ventitré", 23), ("trentuno", 31), ("trentotto", 38), ("mille", 1000), ("cento", 100), ("centotto", 108),
    ("novecentonovantanovemilanovecentonovantanove", 999999), ("euro diecimila virgola cinquanta", "10000.50"),
    ("due milioni trecentomila", 2300000), ("quattrocentomila", 400000),
])
def test_words_to_number(words, expected):
    assert words_to_number(words) == Decimal(str(expected))


@pytest.mark.parametrize("words", ["ventre", "pippo", "12 mila", "ventiuno"])
def test_words_to_number_refuses(words):
    assert words_to_number(words) is None


def test_parse_date_it():
    assert parse_date_it("consegnata il 12 febbraio 2026") == date(2026, 2, 12)
    assert parse_date_it("1° marzo 2026") == date(2026, 3, 1)
    assert parse_date_it("12 FEB 2026") == date(2026, 2, 12)
    assert parse_date_it("05/08/2026") == date(2026, 8, 5)
    assert parse_date_it("05/08/26") is None
    assert parse_date_it("05/08/26", allow_two_digit_year=True) == date(2026, 8, 5)
    assert parse_date_it("31/02/2026") is None
    assert parse_date_it("nessuna data") is None


def test_flag():
    assert flag(float("nan")) is False and bool(math.nan) is True  # the bug this exists for
    assert flag("Sì") and flag("x") and flag(1) and flag("TRUE")
    assert not flag("") and not flag("no") and not flag(0) and not flag(None)
    with pytest.raises(ValueError):
        flag("forse")
