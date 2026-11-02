#!/usr/bin/env python3
"""Baut die klickbare index.html aus src/plan.template.html.

{{FILE:pfad}} wird durch den HTML-escapten Inhalt der Datei ersetzt,
{{DATE}} durch das Erstellungsdatum. So ist der Plan im Browser identisch
mit den echten Dateien im Repo — ohne doppelte Kopien.
"""
from __future__ import annotations

import html
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "src" / "plan.template.html"
OUTPUT = ROOT / "index.html"


def build() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")

    def inject(match: re.Match) -> str:
        rel = match.group(1).strip()
        path = ROOT / rel
        if not path.is_file():
            raise SystemExit(f"Fehlende Datei in {{FILE:...}}: {rel}")
        return html.escape(path.read_text(encoding="utf-8"), quote=False)

    text = re.sub(r"\{\{FILE:([^}]+)\}\}", inject, text)
    text = text.replace("{{DATE}}", date.today().strftime("%d.%m.%Y"))
    if "{{FILE:" in text or "{{DATE}}" in text:
        raise SystemExit("Nicht alle Platzhalter ersetzt.")
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"OK: {OUTPUT.relative_to(ROOT)} ({len(text):,} Zeichen)")


if __name__ == "__main__":
    build()
