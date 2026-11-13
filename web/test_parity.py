"""The JavaScript lint must give the same findings as the Python one (needs Node.js on PATH)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from zt_anchor import lint, words_to_number

QUI = Path(__file__).resolve().parent
ACCORDO = (QUI.parent / "tests" / "test_contract_lint.py").read_text(encoding="utf-8").split('ACCORDO = """')[1].split('"""')[0]
PAROLE = ["settantaquattromila/00", "dodicimilacinquecento/50", "centottantamila", "duemilacinquecentoventuno",
          "un milione e duecentomila", "ventitré", "trentotto", "centotto", "euro diecimila virgola cinquanta",
          "ventre", "ventiuno"]

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")


def _node(script: str) -> object:
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout)


def test_same_findings_as_python():
    js = _node(
        f"const L=require({json.dumps(str(QUI / 'src' / 'lint.js'))});"
        f"process.stdout.write(JSON.stringify(L.lint({json.dumps(ACCORDO)}, ['Foro competente','Premesse'])))"
    )
    py = [(f.rule, f.start, f.end) for f in lint(ACCORDO, ["Foro competente", "Premesse"])]
    assert [(f["rule"], f["start"], f["end"]) for f in js] == py  # messages format numbers differently


def test_same_number_words_as_python():
    js = _node(
        f"const L=require({json.dumps(str(QUI / 'src' / 'lint.js'))});"
        f"process.stdout.write(JSON.stringify({json.dumps(PAROLE)}.map(L.wordsToNumber)))"
    )
    py = [None if (v := words_to_number(w)) is None else float(v) for w in PAROLE]
    assert js == py
