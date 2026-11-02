# Socialmaker5.0 · AuronOrigin

Agenten, die Aufgaben ausführen, um die Online-Präsenz zu vertiefen —
**lokal, selbst gehostet, 0 € laufende Kosten**.

> 👉 **Der eigentliche Plan ist [`index.html`](index.html)** — eine klickbare Checkliste
> mit Copy-Button für jeden Befehl, Fortschrittsanzeige (im Browser gespeichert),
> Suche, Druck-/PDF-Ansicht und allen Dateiinhalten inline. Einfach öffnen,
> nichts installieren. `python3 -m http.server 3000 --bind 0.0.0.0` zeigt sie im Browser.

## Was entsteht

Eine Pipeline, die **jeden Morgen ohne Zutun** ein hochladebereites Paket ablegt:
Recherche → lokales KI-Skript → KI-Stimme → Stock-Clips/Titelkarten → FFmpeg-Schnitt
→ Untertitel → Titel, Beschreibung, Hashtags und Plattform-Texte für YouTube,
Instagram, Facebook, X und TikTok. Danach **1 Klick Freigabe** und manueller Upload.

| Rechner | Rolle |
|---|---|
| Dell Latitude 5530 (16 GB, i5-1235U, Iris Xe) | Ollama `qwen2.5:7b-instruct` (CPU), Python-Worker, TTS, FFmpeg, Dateiablage |
| 24/7-Laptop (5 GB, Ryzen) | Docker + n8n (SQLite), Cron, Wochenplan |

Verbunden über **Tailscale** (Free-Tier), Firewall nur auf `tailscale0`.
Optionale Gratis-APIs: Brave Search (2.000/Monat), Pexels. **Ohne jeden Key
läuft die Pipeline trotzdem** (Google-News-RSS + selbst gezeichnete Titelkarten).

## Schnellstart

```bash
git clone -b arena/ede4bccb-socialmaker5-0 https://github.com/budsxbach/Socialmaker5.0.git ~/Socialmaker5.0
bash ~/Socialmaker5.0/setup/00-both-machines.sh    # BEIDE Rechner
sudo tailscale up                                  # BEIDE Rechner, einmalig
bash ~/Socialmaker5.0/setup/01-dell-ollama.sh      # nur Dell
bash ~/Socialmaker5.0/setup/02-server-n8n.sh       # nur 24/7-Laptop
bash ~/Socialmaker5.0/setup/03-worker.sh           # nur Dell
```

Danach `~/AuronOrigin/.env` setzen (`WORKER_TOKEN`, `CONTENT_LANG=en`),
`n8n/workflow.json` importieren (Platzhalter mit `sed` ersetzen — siehe Plan),
und `http://DELL_IP:8787/review` öffnen.

## Ehrliche Grenzen

- **CPU-only:** 7B-Q4 mit ~5–10 Tok/s. Gut für Skripte/JSON, nicht für lokale
  Bild-/Videogenerierung oder Avatare. Iris Xe hat keinen nutzbaren VRAM-Vorteil.
- **Kein Auto-Upload:** Privatkonten + Plattform-Regeln → Automation bis zur
  1-Klick-Freigabe, Upload bewusst manuell (markensicher, kein App-Review nötig).
- **Geld:** Shorts-Ad-Umsatz ist klein; TikTok zahlt erst ab > 1 Minute, YouTube
  verlangt Watch Hours/Abos (ab 01.02.2027 doppelte Hürde für Neuanmeldungen).
  Der Hebel ist Langform + Sponsoring + eigene Produkte. 0 € = organisches Wachstum.
- **Kennzeichnung:** EU AI Act Art. 50 gilt seit 02.08.2026; Plattform-Labels
  (YouTube „AI use“, TikTok-Toggle, Meta „AI info“) gehören in jeden Upload.

Details, Zahlen und Quellen: [`index.html`](index.html) → „Realitätscheck“,
„Geld verdienen“, „Recht & Kennzeichnung“.

## Dateien

| Pfad | Inhalt |
|---|---|
| `index.html` | klickbarer Plan (generiert) |
| `src/plan.template.html` | Template mit `{{FILE:...}}`-Platzhaltern |
| `tools/build_plan.py` | `python3 tools/build_plan.py` baut `index.html` |
| `setup/00…03-*.sh` | Installationsskripte in Phasenreihenfolge |
| `config/` | systemd-Drop-in, docker-compose, `.env`-Vorlage |
| `worker/` | FastAPI-Worker: Recherche, Ollama, TTS, FFmpeg, Freigabe-UI |
| `n8n/workflow.json` | importierbarer Workflow (täglich + wöchentlich) |
| `systemd/auron-worker.service` | Autostart des Workers |

## Technischer Hinweis

`index.html` wird aus dem Template generiert; die eingebetteten Dateiinhalte sind
dadurch **identisch** mit den echten Dateien im Repo. Nach einer Änderung an einer
Datei einfach `python3 tools/build_plan.py` erneut ausführen.

Keine Rechts-, Steuer- oder Anlageberatung. Plattformregeln vor Veröffentlichung
selbst prüfen.
