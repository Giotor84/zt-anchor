from decimal import Decimal

from zt_anchor import AnchorStatus, Claim, Policy, Source, Status, anchor_quote, check_claims, decide

DOC = Source(
    "accordo-001",
    "Art. 2 – Importo\nIl Debitore si impegna a versare la somma di € 12.500,00 (dodicimilacinquecento/00)\n"
    "entro il 30 giugno 2026, a saldo e stral-\n  cio di ogni pretesa. Il pagamento avverrà con bonifico.",
)


def test_anchor_exact_offsets():
    a = anchor_quote(DOC, "la somma di € 12.500,00")
    assert a is not None and DOC.text[a.start:a.end] == a.text == "la somma di € 12.500,00"


def test_anchor_tolerates_case_spaces_quotes_and_hyphenation():
    a = anchor_quote(DOC, "a SALDO e   stralcio di ogni pretesa")
    assert a is not None and a.text.startswith("a saldo e stral-")
    assert anchor_quote(DOC, "Art. 2 - Importo") is not None  # en dash vs hyphen


def test_invented_quote_is_not_anchored():
    assert anchor_quote(DOC, "entro il 31 dicembre 2026") is None


def test_check_claims_statuses_and_value_in_quote():
    claims = [
        Claim("importo", Decimal("12500"), "versare la somma di € 12.500,00", "accordo-001"),
        Claim("importo_sbagliato", Decimal("15000"), "versare la somma di € 12.500,00", "accordo-001"),
        Claim("scadenza", "30 giugno 2026", "entro il 30 giugno 2026", "accordo-001"),
        Claim("inventato", "rate mensili", "in 24 rate mensili", "accordo-001"),
        Claim("fonte", "x", "x", "accordo-999"),
        Claim("ripetuto", "il", "il", "accordo-001"),
    ]
    c = {x.claim.field: x for x in check_claims(claims, [DOC])}
    assert c["importo"].status is AnchorStatus.ANCHORED and c["importo"].value_in_quote is True
    assert c["importo_sbagliato"].value_in_quote is False
    assert c["scadenza"].value_in_quote is True
    assert c["inventato"].status is AnchorStatus.NOT_FOUND
    assert c["fonte"].status is AnchorStatus.SOURCE_UNKNOWN
    assert c["ripetuto"].status is AnchorStatus.AMBIGUOUS


def test_decide_three_outcomes():
    checked = {x.claim.field: x for x in check_claims([
        Claim("importo", Decimal("12500"), "€ 12.500,00", "accordo-001"),
        Claim("importo2", Decimal("15000"), "€ 12.500,00", "accordo-001"),
        Claim("rate", "24", "in 24 rate", "accordo-001"),
    ], [DOC])}
    ok = decide("importo", Decimal("12500"), confidence=0.97, checked=checked["importo"])
    assert ok.status is Status.ACCEPTED and ok.filled == Decimal("12500")
    review = decide("importo2", Decimal("15000"), confidence=0.97, checked=checked["importo2"])
    assert review.status is Status.NEEDS_REVIEW and review.filled is None and review.cell() == "DA VERIFICARE"
    no = decide("rate", "24", confidence=0.99, checked=checked["rate"])
    assert no.status is Status.ABSTAINED and no.cell() == ""
    low = decide("importo", Decimal("12500"), confidence=0.4, checked=checked["importo"])
    assert low.status is Status.ABSTAINED
    assert decide("x", None).status is Status.ABSTAINED


def test_policy_without_anchor_requirement():
    d = decide("ocr_esito", "CONSEGNATA", confidence=0.95, policy=Policy(require_anchor=False))
    assert d.status is Status.ACCEPTED


def test_anchor_compound_hyphenated_word_across_newline():
    src = Source("d1", "Convertito dal decreto-\nlegge 18 ottobre 2012 n. 179.")
    a = anchor_quote(src, "decreto-legge 18 ottobre 2012")
    assert a is not None
    assert "decreto-" in a.text and "legge 18 ottobre 2012" in a.text
