"""AuronOrigin | Text-to-Speech mit 3-Stufen-Fallback (0 EUR).

1. edge-tts  — kostenlos, natuerliche Stimmen, braucht Internet aber keinen Key
2. piper     — komplett offline, falls installiert + Modell in .env hinterlegt
3. espeak-ng — immer da (apt), robotisch, aber die Pipeline laeuft garantiert
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import settings as cfg


def probe(path: Path) -> float:
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            text=True, timeout=30,
        )
        return float(out.strip())
    except Exception:
        return 0.0


def _edge(text: str, voice: str, dest: Path) -> None:
    import edge_tts

    async def _go():
        communicate = edge_tts.Communicate(text, voice, rate="+5%")
        await communicate.save(str(dest))

    asyncio.run(_go())


def _piper(text: str, lang: str, wav: Path) -> bool:
    model = cfg.PIPER_MODEL_EN if lang.startswith("en") else cfg.PIPER_MODEL_DE
    if not model or not shutil.which("piper") or not Path(model).exists():
        return False
    subprocess.run(["piper", "--model", model, "--output_file", str(wav)],
                   input=text.encode("utf-8"), check=True, timeout=180)
    return wav.exists()


def _espeak(text: str, lang: str, wav: Path) -> None:
    voice = "en-us" if lang.startswith("en") else "de"
    subprocess.run(["espeak-ng", "-v", voice, "-s", "150", "-w", str(wav)],
                   input=text.encode("utf-8"), check=True, timeout=180)


def synth(text: str, dest_mp3: Path, lang: str = "en") -> tuple[Path, float]:
    """Gibt (mp3-Pfad, Dauer in Sekunden) zurueck."""
    dest_mp3 = Path(dest_mp3)
    dest_mp3.parent.mkdir(parents=True, exist_ok=True)
    wav = dest_mp3.with_suffix(".wav")
    voice = cfg.TTS_VOICE_EN if lang.startswith("en") else cfg.TTS_VOICE_DE

    if cfg.TTS_ENGINE in ("edge", "auto"):
        try:
            _edge(text, voice, dest_mp3)
            duration = probe(dest_mp3)
            if duration > 0.5:
                return dest_mp3, duration
        except Exception as exc:
            print(f"[voice] edge-tts: {exc} -> Fallback")

    try:
        if _piper(text, lang, wav):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                            "-ar", "44100", "-ac", "2", "-b:a", "128k", str(dest_mp3)],
                           check=True, timeout=120)
            duration = probe(dest_mp3)
            if duration > 0.5:
                return dest_mp3, duration
    except Exception as exc:
        print(f"[voice] piper: {exc} -> Fallback")

    _espeak(text, lang, wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                    "-ar", "44100", "-ac", "2", "-b:a", "128k", str(dest_mp3)],
                   check=True, timeout=120)
    return dest_mp3, max(probe(dest_mp3), 1.0)
