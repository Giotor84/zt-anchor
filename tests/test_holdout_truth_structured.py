import json

import pytest

from zt_anchor import (
    HoldoutInvalidated,
    Statement,
    StructuredOutputError,
    Truth,
    evaluate,
    extract_json,
    fingerprint,
    freeze,
    generate_structured,
    load_frozen,
    render_markdown,
    validate,
)


def test_freeze_and_invalidate(tmp_path):
    reader = tmp_path / "reader.py"
    reader.write_text("THRESHOLD = 0.8\n")
    fp = fingerprint([reader], {"model": "local-14b", "prompt": "v1"})
    ids = [f"doc-{i:03d}" for i in range(50)]
    sample = freeze(ids, 10, seed=7, system_fingerprint=fp, path=tmp_path / "holdout.json")
    assert len(sample) == 10 and load_frozen(tmp_path / "holdout.json", fp) == sample
    with pytest.raises(FileExistsError):
        freeze(ids, 10, seed=8, system_fingerprint=fp, path=tmp_path / "holdout.json")
    reader.write_text("THRESHOLD = 0.7\n")  # tuning the reader after freezing
    with pytest.raises(HoldoutInvalidated):
        load_frozen(tmp_path / "holdout.json", fingerprint([reader], {"model": "local-14b", "prompt": "v1"}))


def test_evaluate_separates_abstentions_from_errors():
    gold = {"a": "CONSEGNATA", "b": "COMPIUTA GIACENZA", "c": "CONSEGNATA", "d": "RESPINTA"}
    pred = {"a": "CONSEGNATA", "b": None, "c": "RESPINTA"}
    r = evaluate(pred, gold)
    assert (r.correct, r.wrong, r.abstained, r.answered) == (1, 1, 2, 2)
    assert r.coverage == 0.5 and r.selective_accuracy == 0.5
    assert r.wrong_ids == ("c",) and r.missing_ids == ("d",)


def test_truth_labels_need_evidence():
    with pytest.raises(ValueError):
        Statement("830 tests pass", Truth.VERIFIED_SYNTHETIC)
    md = render_markdown([
        Statement("deploy on the client cluster", Truth.VERIFY_LIVE),
        Statement("extraction schema is valid", Truth.VERIFIED_SYNTHETIC, "pytest tests/test_schema.py"),
    ])
    assert md.index("VERIFIED_SYNTHETIC") < md.index("VERIFY_LIVE")


SCHEMA = {
    "type": "object",
    "required": ["importo", "esito"],
    "additionalProperties": False,
    "properties": {
        "importo": {"type": "number", "minimum": 0},
        "esito": {"type": "string", "enum": ["accolta", "respinta", "non classificabile"]},
        "citazioni": {"type": "array", "items": {"type": "string", "minLength": 3}},
    },
}


def test_extract_json_from_chatty_answers():
    assert extract_json('Sure! ```json\n{"a": 1}\n``` hope it helps') == {"a": 1}
    assert extract_json('Answer: {"q": "he said \\"no\\" {x}", "n": [1, 2]} done') == {"q": 'he said "no" {x}', "n": [1, 2]}
    with pytest.raises(StructuredOutputError):
        extract_json("no json here")


def test_validate():
    assert validate({"importo": 10, "esito": "accolta"}, SCHEMA) == []
    errs = validate({"importo": -1, "esito": "boh", "extra": 1, "citazioni": ["ok!", "x"]}, SCHEMA)
    assert len(errs) == 4
    assert validate({"importo": True, "esito": "accolta"}, SCHEMA)  # bool is not a number


def test_generate_structured_retries_with_feedback():
    prompts = []
    answers = iter(["I think it was accepted", '{"importo": 100, "esito": "accettata"}',
                    '{"importo": 100, "esito": "accolta"}'])

    def fake_model(prompt):
        prompts.append(prompt)
        return next(answers)

    assert generate_structured(fake_model, "Estrai.", SCHEMA) == {"importo": 100, "esito": "accolta"}
    assert "not in" in prompts[2] and len(prompts) == 3


def test_generate_structured_gives_up():
    with pytest.raises(StructuredOutputError):
        generate_structured(lambda p: json.dumps({"importo": "x"}), "Estrai.", SCHEMA, attempts=2)
