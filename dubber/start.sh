#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v python3 >/dev/null; then echo 'Bitte Python 3.10 oder neuer installieren.' >&2; exit 1; fi
if [ ! -x .venv-dubber/bin/python ]; then
  echo 'Erstelle virtuelle Umgebung und installiere Abhängigkeiten …'
  python3 -m venv .venv-dubber
  .venv-dubber/bin/pip install -r dubber/requirements.txt
fi
echo 'Stimmwechsel läuft auf http://127.0.0.1:8765'
exec .venv-dubber/bin/python -m uvicorn dubber.app:app --host "${DUBBER_HOST:-127.0.0.1}" --port "${DUBBER_PORT:-8765}"
