"""AuronOrigin | Zentrale Konfiguration.

Liest ~/AuronOrigin/.env (und als Fallback die .env im Repo-Root).
Alle Pfade sind bewusst relativ zum Home-Verzeichnis: kein Root, keine sudo-Noetigkeit.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent          # .../AuronOrigin/worker
ROOT = HERE.parent                              # .../AuronOrigin
load_dotenv(ROOT / ".env", override=False)
load_dotenv(ROOT.parent / ".env", override=False)


def env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def env_int(key: str, default: int) -> int:
    try:
        return int(env(key, str(default)))
    except ValueError:
        return default


HOME = Path(env("AU_HOME") or str(Path.home() / "AuronOrigin")).expanduser()
OUT = HOME / "out"
DRAFTS = OUT / "ENTWURF"
APPROVED = OUT / "FREIGEGEBEN"
REJECTED = OUT / "VERWORFEN"
PLANS = OUT / "PLAN"
ASSETS = HOME / "assets"
MUSIC = ASSETS / "music"
CACHE = HOME / "cache"
for _p in (OUT, DRAFTS, APPROVED, REJECTED, PLANS, ASSETS, MUSIC, CACHE):
    _p.mkdir(parents=True, exist_ok=True)

OLLAMA_URL = env("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = env("OLLAMA_MODEL", "qwen2.5:7b-instruct")
OLLAMA_FAST_MODEL = env("OLLAMA_FAST_MODEL", "llama3.2:3b")
OLLAMA_THREADS = env_int("OLLAMA_NUM_THREADS", 10)

WORKER_TOKEN = env("WORKER_TOKEN")
CONTENT_LANG = env("CONTENT_LANG", "en")
TARGET_SECONDS = env_int("TARGET_SECONDS", 70)

BRAVE_API_KEY = env("BRAVE_API_KEY")
PEXELS_API_KEY = env("PEXELS_API_KEY")

TTS_ENGINE = env("TTS_ENGINE", "edge")
TTS_VOICE_EN = env("TTS_VOICE_EN", "en-US-GuyNeural")
TTS_VOICE_DE = env("TTS_VOICE_DE", "de-DE-KatjaNeural")
PIPER_MODEL_EN = env("PIPER_MODEL_EN")
PIPER_MODEL_DE = env("PIPER_MODEL_DE")

W = 1080
H = 1920
FPS = 30
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
