"""AuronOrigin | Worker-API + 1-Klick-Freigabe-Seite.

Laeuft auf dem Dell, nur ueber Tailscale erreichbar (ufw regelt das).
  GET  /health          Zustand
  POST /run             ein komplettes Video-Paket bauen
  POST /plan            Wochenplan (7 Themen) erzeugen
  GET  /packages        Entwuerfe auflisten
  POST /approve         Entwurf -> out/FREIGEGEBEN (dein 1 Klick)
  POST /discard         Entwurf -> out/VERWORFEN
  GET  /review          klickbare Freigabe-Oberflaeche
  /out/...              fertige Dateien zum Download
"""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import pipeline
import settings as cfg

app = FastAPI(title="AuronOrigin Worker", version="1.0")
app.mount("/out", StaticFiles(directory=str(cfg.OUT)), name="out")


def _auth(request: Request) -> None:
    if cfg.WORKER_TOKEN and request.headers.get("X-Auron-Token") != cfg.WORKER_TOKEN:
        raise HTTPException(status_code=401, detail="X-Auron-Token fehlt oder ist falsch")


class RunBody(BaseModel):
    topic: str | None = None
    lang: str | None = None


class SlugBody(BaseModel):
    slug: str


@app.get("/health")
def health():
    disk = shutil.disk_usage(cfg.HOME)
    return {
        "ok": True,
        "model": cfg.OLLAMA_MODEL,
        "ollama": cfg.OLLAMA_URL,
        "lang": cfg.CONTENT_LANG,
        "target_seconds": cfg.TARGET_SECONDS,
        "free_gb": round(disk.free / 1024 ** 3, 1),
        "drafts": len(pipeline.list_drafts()),
        "brave_key": bool(cfg.BRAVE_API_KEY),
        "pexels_key": bool(cfg.PEXELS_API_KEY),
    }


@app.post("/run")
def run(body: RunBody, request: Request):
    _auth(request)
    try:
        return pipeline.run(topic=body.topic, lang=body.lang)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/plan")
def plan(body: RunBody, request: Request):
    _auth(request)
    return pipeline.plan_week(lang=body.lang)


@app.get("/packages")
def packages():
    return {"drafts": pipeline.list_drafts()}


@app.post("/approve")
def approve(body: SlugBody, request: Request):
    _auth(request)
    try:
        return pipeline.approve(body.slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/discard")
def discard(body: SlugBody, request: Request):
    _auth(request)
    try:
        return pipeline.discard(body.slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


REVIEW_TEMPLATE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AuronOrigin | Freigabe</title>
<style>
:root{--bg:#080d19;--card:#111a2c;--acc:#35e0c8;--txt:#e8edf7;--mut:#93a4c0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);
font:15px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;padding:28px}
h1{font-size:25px;margin:0 0 4px}small{color:var(--mut)}
.wrap{max-width:900px;margin:auto}.bar{display:flex;gap:10px;flex-wrap:wrap;
margin:20px 0 28px;align-items:center}
input,button{font:inherit;border-radius:9px;border:1px solid #2a3a55;padding:9px 13px}
input{background:#0d1524;color:var(--txt);min-width:250px}
button{cursor:pointer;background:var(--acc);color:#04121a;font-weight:700;border:0}
button.ghost{background:transparent;color:var(--mut);border:1px solid #2a3a55}
button.red{background:#ff7a7a}.card{background:var(--card);border:1px solid #22314c;
border-radius:14px;padding:18px;margin:0 0 22px}
video{width:100%;max-width:270px;border-radius:10px;background:#000;display:block;margin-bottom:14px}
h2{font-size:17px;margin:0 0 6px}.meta{color:var(--mut);font-size:13px;margin-bottom:10px}
pre{white-space:pre-wrap;background:#0b1220;padding:12px;border-radius:8px;font-size:13px}
.row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.ok{color:var(--acc)}
</style></head><body><div class="wrap">
<h1>AuronOrigin · 1-Klick-Freigabe</h1>
<small>Alles in out/ENTWURF wartet hier. Freigabe verschiebt nach out/FREIGEGEBEN —
der Upload bleibt bewusst manuell (Privatkonten, markensicher).</small>
<div class="bar">
<input id="tok" placeholder="WORKER_TOKEN (aus ~/AuronOrigin/.env)">
<button class="ghost" onclick="save()">Token speichern</button>
<button class="ghost" onclick="location.reload()">Neu laden</button>
</div>
<div id="list">__CARDS__</div></div>
<script>
const key='auron_worker_token';
document.getElementById('tok').value=localStorage.getItem(key)||'';
function save(){localStorage.setItem(key,document.getElementById('tok').value.trim());alert('Token gespeichert');}
async function act(slug,kind){
 const token=document.getElementById('tok').value.trim();
 localStorage.setItem(key,token);
 const r=await fetch('/'+kind,{method:'POST',headers:{'Content-Type':'application/json',
  'X-Auron-Token':token},body:JSON.stringify({slug})});
 const d=await r.json();
 document.getElementById('msg-'+slug).textContent=r.ok
   ? (kind==='approve'?'✓ Freigegeben — Ordner out/FREIGEGEBEN/'+slug:'✓ Verworfen')
   : ('Fehler: '+(d.detail||'unbekannt'));
 if(r.ok) setTimeout(()=>location.reload(),900);
}
</script></body></html>"""


@app.get("/review", response_class=HTMLResponse)
def review():
    drafts = pipeline.list_drafts()
    if not drafts:
        cards = "<div class='card'>Noch keine Entwürfe. Starte n8n oder: " \
                "<code>curl -X POST http://127.0.0.1:8787/run -d '{}'</code></div>"
    else:
        cards = ""
        for d in drafts:
            slug = html.escape(d["slug"])
            title = html.escape(d.get("title", ""))
            caption = html.escape(d.get("caption", "")[:600])
            cards += f"""<div class="card">
<h2>{title}</h2>
<div class="meta">{slug} · {d.get('duration_seconds', 0)} s ·
{d.get('scenes', 0)} Szenen · {d.get('sources', 0)} Quellen
{' · ⚠ Notfall-Skript' if d.get('degraded') else ''}</div>
<video controls preload="metadata" src="{html.escape(d.get('video_url',''))}"></video>
<pre>{caption}</pre>
<div class="row"><button onclick="act('{slug}','approve')">✓ Freigeben</button>
<button class="red" onclick="act('{slug}','discard')">✕ Verwerfen</button>
<a class="ghost" href="/out/ENTWURF/{slug}/UPLOAD.md" target="_blank">Upload-Checkliste</a>
<a class="ghost" href="/out/ENTWURF/{slug}/captions.srt" target="_blank">SRT</a></div>
<div class="ok" id="msg-{slug}"></div></div>"""
    return HTMLResponse(REVIEW_TEMPLATE.replace("__CARDS__", cards))
