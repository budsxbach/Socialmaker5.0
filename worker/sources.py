"""AuronOrigin | Kostenlose Quellen.

Wichtig: Die Pipeline funktioniert OHNE jeden API-Key. Dann laufen
Google-News-RSS (Recherche) und selbst gezeichnete Titelkarten (Visuals).
Optionale Gratis-Keys (Brave 2.000 Suchanfragen/Monat, Pexels) verbessern
nur die Qualitaet — sie sind nie eine Voraussetzung.
"""
from __future__ import annotations

import html
import re
import urllib.parse
from pathlib import Path

import feedparser
import requests

import settings as cfg

UA = {"User-Agent": "AuronOrigin/1.0 (self-hosted personal content pipeline)"}


def _clean(value: str) -> str:
    value = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", value).strip()


def rss_research(topic: str, lang: str = "en", limit: int = 7) -> list[dict]:
    """Google News RSS — kostenlos, ohne Key, ohne Registrierung."""
    hl, gl, ceid = (("en-US", "US", "US:en") if lang.startswith("en")
                    else ("de", "DE", "DE:de"))
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": topic, "hl": hl, "gl": gl, "ceid": ceid}
    )
    try:
        resp = requests.get(url, headers=UA, timeout=20)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        return [
            {
                "title": _clean(e.get("title", "")),
                "url": e.get("link", ""),
                "summary": _clean(e.get("summary", ""))[:300],
                "source": "Google News RSS",
            }
            for e in feed.entries[:limit]
            if e.get("title")
        ]
    except Exception as exc:                                # nie die Pipeline killen
        print(f"[sources] RSS nicht erreichbar: {exc}")
        return []


def brave_research(topic: str, lang: str = "en", limit: int = 5) -> list[dict]:
    """Optional: Brave Search API, Free-Tier 2.000 Queries/Monat, 1 Query/Sekunde."""
    if not cfg.BRAVE_API_KEY:
        return []
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": topic, "count": limit,
                    "search_lang": "en" if lang.startswith("en") else "de"},
            headers={**UA, "Accept": "application/json",
                     "X-Subscription-Token": cfg.BRAVE_API_KEY},
            timeout=20,
        )
        resp.raise_for_status()
        results = resp.json().get("web", {}).get("results", [])
        return [
            {"title": _clean(x.get("title", "")), "url": x.get("url", ""),
             "summary": _clean(x.get("description", "")), "source": "Brave"}
            for x in results if x.get("title")
        ]
    except Exception as exc:
        print(f"[sources] Brave nicht erreichbar: {exc}")
        return []


def research(topic: str, lang: str = "en") -> list[dict]:
    items, seen = [], set()
    for item in rss_research(topic, lang) + brave_research(topic, lang):
        key = item["title"].lower()
        if key not in seen:
            seen.add(key)
            items.append(item)
    return items[:8]


def fetch_clip(query: str, dest: Path, timeout: int = 90) -> Path | None:
    """Optional: passendes Pexels-Video im Hochformat. Ohne Key -> None."""
    if not cfg.PEXELS_API_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            params={"query": query[:80], "orientation": "portrait",
                    "per_page": 5, "size": "sd"},
            headers={**UA, "Authorization": cfg.PEXELS_API_KEY},
            timeout=20,
        )
        resp.raise_for_status()
        best = None
        for video in resp.json().get("videos", []):
            for f in video.get("video_files", []):
                width, height = f.get("width", 0), f.get("height", 0)
                if height >= width and width >= 540 and f.get("link"):
                    if best is None or width < best.get("width", 99999):
                        best = f
            if best:
                break
        if not best:
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(best["link"], headers=UA, stream=True, timeout=timeout) as dl:
            dl.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in dl.iter_content(1 << 20):
                    if chunk:
                        fh.write(chunk)
        return dest if dest.stat().st_size > 50_000 else None
    except Exception as exc:
        print(f"[sources] Pexels nicht erreichbar: {exc}")
        return None
