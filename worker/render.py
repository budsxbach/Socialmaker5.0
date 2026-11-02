"""AuronOrigin | FFmpeg-Renderer (reine CPU, Iris Xe wird NICHT benoetigt).

Jede Szene wird einzeln mit identischen Codec-Parametern encodiert, damit der
Zusammenschnitt per Concat-Demuxer ohne Neuberechnung (-c copy) funktioniert.
Das ist auf einem i5-1235U deutlich schneller als ein grosser Filtergraph.
"""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import settings as cfg


def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, check=True, text=True, capture_output=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg-Fehler:\n{' '.join(cmd)}\n{exc.stderr[-1200:]}") from exc


def wrap(text: str, width: int = 30) -> str:
    return "\n".join(textwrap.wrap(text or "", width=width, break_long_words=False))


def make_card(headline: str, path: Path, index: int = 0) -> Path:
    """Titelkarte ohne jede externe Bildquelle — funktioniert immer offline."""
    W, H = cfg.W, cfg.H
    grad = Image.new("RGB", (1, H))
    top, bottom = (9, 13, 30), (23, 43, 73)
    for y in range(H):
        t = y / H
        grad.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    img = grad.resize((W, H))
    draw = ImageDraw.Draw(img)
    accent = (53, 224, 200) if index % 2 == 0 else (139, 124, 255)
    draw.ellipse([int(W * 0.18), int(H * 0.20), int(W * 0.82), int(H * 0.62)],
                 outline=accent, width=9)
    draw.ellipse([int(W * 0.30), int(H * 0.28), int(W * 0.70), int(H * 0.54)],
                 outline=accent, width=3)
    try:
        font = ImageFont.truetype(cfg.FONT_BOLD, 76)
        small = ImageFont.truetype(cfg.FONT_REGULAR, 38)
    except OSError:
        font = small = ImageFont.load_default()
    draw.text((W // 2, int(H * 0.10)), "AURONORIGIN", font=small,
              fill=(160, 180, 210), anchor="mm")
    lines = wrap(headline, 22).split("\n")[:5]
    y = int(H * 0.70)
    for line in lines:
        draw.text((W // 2, int(y)), line, font=font, fill=(255, 255, 255), anchor="mm")
        y += 100
    draw.rectangle([int(W * 0.30), int(H * 0.90), int(W * 0.70), int(H * 0.905)],
                   fill=accent)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def render_scene(index: int, scene: dict, voice_mp3: Path, visual: Path,
                 work: Path, duration: float) -> Path:
    W, H, FPS = cfg.W, cfg.H, cfg.FPS
    caption_file = work / f"caption_{index:02d}.txt"
    # drawtext expandiert %-Sequenzen: Prozentzeichen doppeln
    caption_file.write_text(
        wrap(scene.get("caption", ""), 30).replace("%", "%%"), encoding="utf-8")
    out = work / f"scene_{index:02d}.mp4"

    box_y, box_h = int(H * 0.72), int(H * 0.22)
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,"
        f"fps={FPS},format=yuv420p,"
        f"drawbox=x=0:y={box_y}:w={W}:h={box_h}:color=black@0.55:t=fill,"
        f"drawtext=fontfile={cfg.FONT_BOLD}:textfile={caption_file}:"
        f"fontcolor=white:fontsize=52:line_spacing=14:"
        f"x=(w-text_w)/2:y={box_y + 40}:borderw=1:bordercolor=black@0.6"
    )

    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if visual.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv"):
        cmd += ["-stream_loop", "-1", "-i", str(visual)]
    else:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-i", str(visual)]
    cmd += [
        "-i", str(voice_mp3), "-t", f"{duration:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-r", str(FPS),
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-shortest", "-movflags", "+faststart", str(out),
    ]
    _run(cmd)
    return out


def concat(scene_files: list[Path], work: Path) -> Path:
    listing = work / "concat.txt"
    listing.write_text("\n".join(f"file '{p.as_posix()}'" for p in scene_files) + "\n",
                       encoding="utf-8")
    joined = work / "joined.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", str(listing), "-c", "copy", str(joined)])
    return joined


def finalize(joined: Path, final: Path) -> Path:
    music = next((p for p in sorted(cfg.MUSIC.glob("*.mp3"))), None)
    base = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined)]
    if music:
        base += ["-stream_loop", "-1", "-i", str(music),
                 "-filter_complex",
                 "[1:a]volume=0.10[m];[0:a][m]amix=inputs=2:duration=first:"
                 "dropout_transition=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]",
                 "-map", "0:v", "-map", "[a]"]
    else:
        base += ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
    base += ["-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
             "-movflags", "+faststart", str(final)]
    _run(base)
    return final


def thumbnail(final: Path, path: Path) -> Path:
    _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "2", "-i", str(final),
          "-frames:v", "1", str(path)], timeout=120)
    return path


def _timestamp(seconds: float) -> str:
    ms = int(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(scenes: list[dict], durations: list[float], path: Path) -> Path:
    start, lines = 0.0, []
    for i, (scene, dur) in enumerate(zip(scenes, durations), 1):
        lines.append(f"{i}\n{_timestamp(start)} --> {_timestamp(start + dur)}\n"
                     f"{scene.get('caption', '')}\n")
        start += dur
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def duration(path: Path) -> float:
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1", str(path)], timeout=60)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0
