"""End-to-end demo on a synthetic agreement, no model needed: a fake LLM answer goes through
structured validation -> anchoring -> abstention -> contract lint -> truth-labelled report.

    python examples/demo_synthetic.py

Replace ``fake_model`` with a call to your model (llama.cpp, Bedrock, any OpenAI-compatible server).
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from zt_anchor import (  # noqa: E402
    Claim, Source, Statement, Truth, check_claims, decide, generate_structured, lint, render_markdown,
)

DOC = Source("accordo-demo", """ACCORDO TRANSATTIVO

Premesse
Alfa S.p.A. (di seguito, il «Creditore») e Mario Bianchi (di seguito, il «Debitore») convengono quanto segue.

Art. 1 - Importo
Il Debitore verserà al Creditore € 12.500,00 (dodicimilacinquecento/00) entro il 30 giugno 2026.

Art. 2 - Inadempimento
In caso di mancato pagamento entro il termine si applica l'art. 4 del presente accordo.
""")

SCHEMA = {
    "type": "object",
    "required": ["fields"],
    "properties": {"fields": {"type": "array", "items": {
        "type": "object",
        "required": ["field", "value", "quote", "confidence"],
        "properties": {
            "field": {"type": "string"}, "value": {"type": ["string", "number", "null"]},
            "quote": {"type": "string"}, "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
    }}},
}


def fake_model(prompt: str) -> str:
    """What a real model might answer: one correct field, one with an invented quote, one uncertain."""
    return "Ecco i dati estratti:\n```json\n" + json.dumps({"fields": [
        {"field": "importo", "value": 12500, "quote": "€ 12.500,00 (dodicimilacinquecento/00)", "confidence": 0.97},
        {"field": "rateizzazione", "value": "24 rate mensili", "quote": "in 24 rate mensili", "confidence": 0.91},
        {"field": "scadenza", "value": "30 giugno 2026", "quote": "entro il 30 giugno 2026", "confidence": 0.72},
    ]}, ensure_ascii=False) + "\n```"


def main() -> None:
    out = generate_structured(fake_model, f"Estrai importo, rateizzazione e scadenza.\n\n{DOC.text}", SCHEMA)
    fields = out["fields"]
    claims = [Claim(f["field"], Decimal(str(f["value"])) if isinstance(f["value"], (int, float)) else f["value"],
                    f["quote"], DOC.id) for f in fields]
    checked = check_claims(claims, [DOC])

    print("EXTRACTION")
    for f, c in zip(fields, checked):
        d = decide(f["field"], c.claim.value, confidence=f["confidence"], checked=c)
        where = f"[{c.anchor.start}:{c.anchor.end}]" if c.anchor else "[-]"
        print(f"  {d.field:<14} {str(d.cell()):<16} {d.status.value:<13} {where:<10} {'; '.join(d.reasons)}")

    print("\nCONTRACT LINT")
    for f in lint(DOC.text, ["Premesse", "Foro competente"]):
        print(f"  {f.severity:<7} {f.rule:<20} {f.message}")

    print()
    print(render_markdown([
        Statement("pipeline runs end to end on the synthetic agreement", Truth.VERIFIED_SYNTHETIC,
                  "python examples/demo_synthetic.py"),
        Statement("accuracy on real agreements", Truth.VERIFY_LIVE),
    ], title="What this demo proves"))


if __name__ == "__main__":
    main()
