from zt_anchor import lint
from zt_anchor.contract_lint import check_amounts, check_definitions, check_references, check_sections

# Synthetic agreement: names, amounts and parties are invented.
ACCORDO = """ACCORDO TRANSATTIVO

Premesse
Alfa S.p.A. (di seguito, il «Creditore») e Mario Bianchi (di seguito, il «Debitore») e Beta S.r.l.
(di seguito, il «Garante») convengono quanto segue.

Art. 1 - Oggetto
Il Debitore riconosce il debito verso il Creditore come indicato all'art. 2.

Art. 2 - Importo
Il Debitore verserà € 12.500,00 (dodicimilacinquecento/00) in unica soluzione e
€ 3.000,00 (euro tremilacinquecento/00) a titolo di spese, ai sensi dell'art. 1965 c.c.

Art. 3 - Inadempimento
In caso di mancato pagamento si applica l'art. 5 del presente accordo e l'art. 2 comma 1 d.lgs. 231/2002.
"""


def test_amount_mismatch_found_with_offsets():
    f = check_amounts(ACCORDO)
    assert len(f) == 1 and f[0].rule == "amount_mismatch"
    assert "3000" in f[0].message and "3500" in f[0].message
    assert ACCORDO[f[0].start:f[0].end] == f[0].excerpt and f[0].excerpt.startswith("€ 3.000,00")


def test_unused_definition():
    f = check_definitions(ACCORDO)
    assert [x.message for x in f] == ["defined term never used: Garante"]


def test_internal_reference_to_missing_article_but_not_law_citations():
    f = check_references(ACCORDO)
    assert [x.message for x in f] == ["refers to art. 5, which is not in the document"]


def test_required_sections():
    f = check_sections(ACCORDO, ["Premesse", "Oggetto", "Foro competente"])
    assert [x.message for x in f] == ["missing section: Foro competente"]


def test_lint_sorted_by_position():
    f = lint(ACCORDO, ["Foro competente"])
    assert [x.rule for x in f] == ["section_missing", "definition_unused", "amount_mismatch", "reference_missing"]
