"""Build the single-file offline page: web/dist/zt-anchor-lint.html (lint engine + pdf.js inlined, no network).

    python web/build.py
"""
from __future__ import annotations

from pathlib import Path

QUI = Path(__file__).resolve().parent


def _safe(js: str) -> str:
    return js.replace("</script", "<\\/script")  # a literal </script> inside inlined JS would close the tag


def build() -> Path:
    page = (QUI / "src" / "app.html").read_text(encoding="utf-8")
    parts = {
        "/*__LINT_JS__*/": (QUI / "src" / "lint.js").read_text(encoding="utf-8"),
        "/*__PDF_JS__*/": (QUI / "vendor" / "pdf.min.js").read_text(encoding="utf-8"),
        "/*__PDF_WORKER__*/": (QUI / "vendor" / "pdf.worker.min.js").read_text(encoding="utf-8"),
    }
    for marker, js in parts.items():
        if page.count(marker) != 1:
            raise ValueError(f"marker {marker} must appear exactly once")
        page = page.replace(marker, _safe(js))
    out = QUI / "dist" / "zt-anchor-lint.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    p = build()
    print(f"{p} ({p.stat().st_size // 1024} KB)")
