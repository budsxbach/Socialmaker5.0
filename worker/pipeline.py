"""AuronOrigin | Die eigentliche Pipeline.

Recherche (RSS/Brave) -> lokales Ollama-Modell -> strenges JSON -> TTS ->
Stock-Clips oder gezeichnete Karten -> FFmpeg -> fertiges Upload-Paket.
Alles landet zuerst in out/ENTWURF/ und wartet auf deine 1-Klick-Freigabe.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import time
from pathlib import Path

import requests

import render
import settings as cfg
import sources
import voice

SYSTEM_PROMPT = """You are the senior short-form scriptwriter for the brand AuronOrigin.
Audience: solo entrepreneurs, freelancers and curious tech people who want practical,
honest explanations about AI, software and digital systems. Tone: calm, precise,
useful - never hype, never clickbait, never false claims, never invented statistics.

You MUST answer with ONE valid JSON object and nothing else. No markdown, no code fences.
Schema:
{
  "title": "max 60 characters",
  "hook": "one sentence, spoken in the first 3 seconds",
  "thumbnail_text": "max 4 words",
  "scenes": [
    {"narration": "18-25 words of spoken text",
     "caption": "max 9 words, shown on screen",
     "visual_query": "2-4 English keywords for a stock video search"}
  ],
  "description": "YouTube description, 2-3 sentences, plain text",
  "hashtags": ["#...", "..."],
  "post_text": "one short standalone post for X / Facebook, max 240 characters"
}
Rules: exactly 8 scenes. Total spoken words 150-190 (about 65-80 seconds at
normal speaking rate). Each scene stands on its own. No numbering inside text.
If the research context contains no hard facts, do NOT invent numbers, dates or names.
Write everything in {LANG}.
"""

USER_TEMPLATE = """Topic: {TOPIC}
Research context (may be empty):
{RESEARCH}

Write the 8-scene script now. Output ONLY the JSON object."""


def _ollama(messages: list[dict], model: str | None = None, timeout: int = 420) -> str:
    payload = {
        "model": model or cfg.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "format": "json",
        "keep_alive": "15m",
        "options": {
            "temperature": 0.72,
            "top_p": 0.9,
            "num_ctx": 4096,
            "num_predict": 1200,
            "num_thread": cfg.OLLAMA_THREADS,
        },
    }
    resp = requests.post(f"{cfg.OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _parse_json(raw: str) -> dict | None:
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None


def _validate(data: dict, topic: str) -> dict:
    scenes = data.get("scenes") or []
    clean = []
    for sc in scenes[:8]:
        if not isinstance(sc, dict):
            continue
        narration = str(sc.get("narration") or "").strip()
        if len(narration.split()) < 5:
            continue
        clean.append({
            "narration": narration,
            "caption": str(sc.get("caption") or narration)[:90],
            "visual_query": str(sc.get("visual_query") or topic)[:80],
        })
    if not clean:
        raise ValueError("Modell hat keine brauchbaren Szenen geliefert")
    return {
        "title": str(data.get("title") or topic)[:70],
        "hook": str(data.get("hook") or clean[0]["narration"])[:200],
        "thumbnail_text": str(data.get("thumbnail_text") or topic)[:40],
        "scenes": clean,
        "description": str(data.get("description") or "")[:1200],
        "hashtags": [str(h) for h in (data.get("hashtags") or []) if str(h).startswith("#")][:12],
        "post_text": str(data.get("post_text") or topic)[:280],
    }


def _fallback_script(topic: str, lang: str) -> dict:
    """Notfall-Skript, wenn Ollama nicht erreichbar ist — Pipeline bleibt lauffaehig."""
    de = lang.startswith("de")
    lines = (
        [f"{topic}: acht Dinge, die fast niemand erklärt.",
         "Das Problem beginnt nicht bei der Technik, sondern bei der Frage davor.",
         "Wer ein System baut, spart sich später hundert einzelne Entscheidungen.",
         "Die erste Regel: alles, was sich wiederholt, gehört automatisiert.",
         "Die zweite Regel: automatisiere erst, wenn der Ablauf von Hand funktioniert.",
         "Kostenlos heisst hier nicht gratis im Preis, sondern gratis im Aufwand.",
         "Messbar wird es erst, wenn du die Zahl vorher und nachher kennst.",
         "Prüfe die Quellen, bevor du irgendetwas davon ungeprüft übernimmst."]
        if de else
        [f"{topic}: eight things nobody explains properly.",
         "The problem starts before the tool - it starts with the question.",
         "A system you build once saves a hundred small decisions later.",
         "Rule one: anything you repeat deserves to be automated.",
         "Rule two: never automate a process you have not run by hand.",
         "Free here means no running cost, not no effort.",
         "It only becomes measurable when you know the number before and after.",
         "Check the sources before you repeat any claim from this video."]
    )
    return {
        "title": topic[:70],
        "hook": lines[0],
        "thumbnail_text": topic[:40],
        "scenes": [{"narration": line, "caption": " ".join(line.split()[:8]),
                    "visual_query": topic} for line in lines],
        "description": (lines[0] + " " + lines[1]),
        "hashtags": ["#AI", "#Automation", "#Solopreneur", "#AuronOrigin"],
        "post_text": lines[0],
    }


def build_script(topic: str, research_items: list[dict], lang: str) -> tuple[dict, bool]:
    context = "\n".join(f"- {i['title']}: {i['summary']}" for i in research_items[:6]) \
        or "(no live sources available - use general knowledge, invent no facts)"
    language = "German" if lang.startswith("de") else "English"
    system = SYSTEM_PROMPT.replace("{LANG}", language)
    user = USER_TEMPLATE.replace("{TOPIC}", topic).replace("{RESEARCH}", context)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    try:
        data = _parse_json(_ollama(messages)) or _parse_json(
            _ollama(messages + [{"role": "user", "content": "Return ONLY the JSON object now."}]))
        if data:
            return _validate(data, topic), False
    except Exception as exc:
        print(f"[pipeline] Ollama nicht verfuegbar: {exc}")
    return _fallback_script(topic, lang), True


def next_topic() -> str:
    topics_file = Path(__file__).with_name("topics.json")
    topics = json.loads(topics_file.read_text(encoding="utf-8"))
    state = cfg.CACHE / "topic_state.json"
    idx = 0
    if state.exists():
        try:
            idx = int(json.loads(state.read_text(encoding="utf-8")).get("index", 0))
        except Exception:
            idx = 0
    item = topics[idx % len(topics)]
    state.write_text(json.dumps({"index": idx + 1}), encoding="utf-8")
    return item["topic"] if isinstance(item, dict) else str(item)


def _slug(topic: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:42]
    return dt.datetime.now().strftime("%Y%m%d-%H%M") + "-" + (clean or "video")


def _write_texts(pkg: Path, content: dict, lang: str, sources_used: list[dict],
                 seconds: float, degraded: bool) -> None:
    tags = " ".join(content["hashtags"]) or "#AI #Automation #AuronOrigin"
    (pkg / "title.txt").write_text(content["title"] + "\n", encoding="utf-8")
    (pkg / "caption.txt").write_text(
        f"{content['hook']}\n\n{content['description']}\n\n{tags}\n", encoding="utf-8")
    (pkg / "hashtags.txt").write_text(tags + "\n", encoding="utf-8")
    (pkg / "post.txt").write_text(f"{content['post_text']}\n\n{tags}\n", encoding="utf-8")
    (pkg / "beschreibung.txt").write_text(
        f"{content['title']}\n\n{content['description']}\n\n"
        "Erstellt mit lokaler KI (Ollama), kostenlosen Quellen und FFmpeg.\n"
        "KI-generierte Inhalte sind entsprechend gekennzeichnet.\n\n"
        f"{tags}\n", encoding="utf-8")
    (pkg / "quellen.json").write_text(
        json.dumps(sources_used, ensure_ascii=False, indent=2), encoding="utf-8")
    (pkg / "UPLOAD.md").write_text(
        "# Upload-Checkliste — " + content["title"] + "\n\n"
        "1. video.mp4 ansehen (Ton, Schnitt, Untertitel, Dauer).\n"
        "2. KI-Kennzeichnung auf JEDER Plattform aktivieren (siehe unten).\n"
        "3. captions.srt hochladen, wo possible (YouTube, Facebook, TikTok).\n"
        "4. title.txt + beschreibung.txt + thumbnail.png verwenden.\n"
        "5. caption.txt fuer Instagram / TikTok, post.txt fuer X / Facebook.\n\n"
        "| Plattform | Wo kennzeichnen |\n|---|---|\n"
        "| YouTube | Studio > Attribute > „AI use“: Ja |\n"
        "| TikTok | Mehr Optionen > „AI-generated content“ an |\n"
        "| Instagram / Facebook | „Add AI label“ / AI-Disclosure-Tool |\n"
        "| X | Hinweis in den Post-Text aufnehmen |\n\n"
        "Hinweis: Pflicht bei realistisch wirkenden KI-Bildern/-Stimmen; "
        "EU AI Act Art. 50 gilt seit 02.08.2026. Bei Unsicherheit immer kennzeichnen.\n",
        encoding="utf-8")
    (pkg / "manifest.json").write_text(json.dumps({
        "slug": pkg.name,
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "lang": lang,
        "title": content["title"],
        "duration_seconds": round(seconds, 1),
        "scenes": len(content["scenes"]),
        "degraded": degraded,
        "sources": len(sources_used),
        "status": "ENTWURF",
        "hashtags": content["hashtags"],
        "caption": content["hook"] + "\n\n" + content["description"] + "\n\n" + tags,
        "post_text": content["post_text"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def run(topic: str | None = None, lang: str | None = None) -> dict:
    lang = (lang or cfg.CONTENT_LANG).lower()
    topic = topic or next_topic()
    started = time.time()
    slug = _slug(topic)
    work = cfg.CACHE / slug
    pkg = cfg.DRAFTS / slug
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    pkg.mkdir(parents=True, exist_ok=True)

    used_sources = sources.research(topic, lang)
    content, degraded = build_script(topic, used_sources, lang)
    scenes = content["scenes"][:8]

    scene_files, durations = [], []
    for i, scene in enumerate(scenes):
        mp3 = work / f"voice_{i:02d}.mp3"
        _, dur = voice.synth(scene["narration"], mp3, lang)
        dur = max(dur, 2.0)
        clip = sources.fetch_clip(scene["visual_query"], work / f"clip_{i:02d}.mp4")
        visual = clip or render.make_card(scene["caption"], work / f"card_{i:02d}.png", i)
        scene_files.append(render.render_scene(i, scene, mp3, visual, work, dur))
        durations.append(dur)

    joined = render.concat(scene_files, work)
    final = pkg / "video.mp4"
    render.finalize(joined, final)
    render.thumbnail(final, pkg / "thumbnail.png")
    render.write_srt(scenes, durations, pkg / "captions.srt")
    seconds = render.duration(final)
    _write_texts(pkg, content, lang, used_sources, seconds, degraded)

    shutil.rmtree(work, ignore_errors=True)
    return {
        "slug": slug, "title": content["title"], "lang": lang,
        "duration_seconds": round(seconds, 1), "scenes": len(scenes),
        "sources": len(used_sources), "degraded": degraded,
        "elapsed_seconds": round(time.time() - started, 1),
        "path": str(pkg),
        "review_url": "/review",
        "note": ("Ollama war nicht erreichbar -> Notfall-Skript verwendet."
                 if degraded else "Bereit zur Freigabe."),
    }


def list_drafts() -> list[dict]:
    out = []
    for folder in sorted(cfg.DRAFTS.iterdir(), reverse=True):
        manifest = folder / "manifest.json"
        if folder.is_dir() and manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                data["slug"] = folder.name
                data["video_url"] = f"/out/ENTWURF/{folder.name}/video.mp4"
                out.append(data)
            except Exception:
                continue
    return out


def approve(slug: str) -> dict:
    src, dst = cfg.DRAFTS / slug, cfg.APPROVED / slug
    if not src.exists():
        raise FileNotFoundError(f"Kein Entwurf: {slug}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.move(str(src), str(dst))
    manifest_file = dst / "manifest.json"
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    data["status"] = "FREIGEGEBEN"
    data["approved_at"] = dt.datetime.now().isoformat(timespec="seconds")
    manifest_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (dst / "FREIGABE.txt").write_text(
        "Freigegeben — jetzt manuell hochladen. Siehe UPLOAD.md in diesem Ordner.\n"
        + data.get("caption", "") + "\n", encoding="utf-8")
    return {"slug": slug, "status": "FREIGEGEBEN", "path": str(dst),
            "caption": data.get("caption", ""), "post_text": data.get("post_text", "")}


def discard(slug: str) -> dict:
    src, dst = cfg.DRAFTS / slug, cfg.REJECTED / slug
    if not src.exists():
        raise FileNotFoundError(f"Kein Entwurf: {slug}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"slug": slug, "status": "VERWORFEN"}


def plan_week(lang: str | None = None) -> dict:
    """Montags: 7 Themen + Hooks vom schnellen 3B-Modell, ohne Video zu rendern."""
    lang = (lang or cfg.CONTENT_LANG).lower()
    language = "German" if lang.startswith("de") else "English"
    prompt = (
        f"You are the content planner for AuronOrigin (AI, automation, digital systems "
        f"for solo entrepreneurs). Return ONLY a JSON object with key 'ideas': an array "
        f"of exactly 7 objects with keys 'topic', 'hook', 'pillar'. Topics must be "
        f"evergreen, specific, non-hype, in {language}. No markdown."
    )
    try:
        raw = _ollama([{"role": "user", "content": prompt}],
                      model=cfg.OLLAMA_FAST_MODEL, timeout=240)
        data = _parse_json(raw) or {}
        ideas = data.get("ideas", [])[:7]
    except Exception as exc:
        print(f"[pipeline] Wochenplan: {exc}")
        ideas = []
    if len(ideas) < 7:
        ideas = [{"topic": next_topic(), "hook": "Was davon ist wirklich neu?",
                  "pillar": "Systeme"} for _ in range(7)]
    week = dt.date.today().strftime("%G-KW%V")
    path = cfg.PLANS / f"wochenplan-{week}-{lang}.md"
    lines = [f"# AuronOrigin | Wochenplan {week} ({lang})", ""]
    for i, idea in enumerate(ideas, 1):
        lines += [f"## Tag {i}: {idea.get('topic', '')}",
                  f"- Hook: {idea.get('hook', '')}",
                  f"- Säule: {idea.get('pillar', '')}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return {"path": str(path), "ideas": len(ideas), "week": week}
