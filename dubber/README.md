# Stimmwechsel – englische Videos auf Deutsch

Eine eigenständige, kostenlose Web-App: englische Sprache lokal mit Faster Whisper erkennen, mit Ollama oder Argos ins Deutsche übersetzen und eine zeitlich angepasste deutsche Erzählerstimme einsetzen. Die **gesamte Originaltonspur** (auch Musik und Effekte) wird entfernt. Ausgabe ist MP4. Der deutsche Text lässt sich vor einer erneuten Vertonung bearbeiten. Keine Sprechererkennung, Stimmklonung oder Lippensynchronisation.

## Start unter Ubuntu

Voraussetzungen: Python 3.10 oder neuer, `python3-venv`, genug freier Speicher und für die Standardübersetzung ein laufender Ollama-Server. FFmpeg wird verwendet; falls es nicht installiert ist, liefert `imageio-ffmpeg` auf unterstützten Plattformen eine ausführbare Version mit.

```bash
sudo apt update && sudo apt install -y python3-venv ffmpeg espeak-ng
# Ollama installieren/starten, falls noch nicht vorhanden; dann:
ollama pull qwen2.5:7b-instruct
# Im Wurzelverzeichnis dieses Repositories:
./dubber/start.sh
```

Im Browser **http://127.0.0.1:8765** öffnen. Das Startskript legt `.venv-dubber` an und installiert die Abhängigkeiten beim ersten Start. Zum Beenden `Strg+C`. Falls die Installation unterbrochen wurde: `.venv-dubber/bin/pip install -r dubber/requirements.txt` ausführen.

1. Video auswählen und die gewünschten Engines einstellen.
2. Auf **Video synchronisieren** klicken. Das erste Laden des Whisper-Modells lädt Modelldaten aus dem Internet herunter; danach ist das Modell im Cache. Die Verarbeitung auf der CPU kann deutlich länger als das Video dauern.
3. Unter **Deine Projekte** Ergebnis ansehen und herunterladen. Über **Text bearbeiten** lassen sich Übersetzungen korrigieren und neu vertonen. Projekte und hochgeladene Dateien bleiben lokal in `dubber/data/`, bis sie in der App gelöscht werden.

**Standard:** Whisper Base + Ollama `qwen2.5:7b-instruct` lokal; Edge TTS ist kostenlos, benötigt aber Internet und sendet den zu sprechenden Text an Microsoft. Whisper-Modelle benötigen zunächst einen Download. Wähle Piper oder espeak-ng für eine lokale Stimme. Die Tonqualität von espeak-ng ist deutlich synthetischer.

## Vollständig offline nach Einrichtung

- **Whisper:** Das gewünschte Modell einmal bei Internetverbindung laden oder im Hugging-Face-Cache bereitstellen.
- **Übersetzung:** Ollama lokal mit bereits geladenem Modell oder alternativ Argos Translate. Für Argos im Projektordner:
  ```bash
  .venv-dubber/bin/pip install argostranslate
  .venv-dubber/bin/python -c "import argostranslate.package as p; p.update_package_index(); x=next(x for x in p.get_available_packages() if x.from_code=='en' and x.to_code=='de'); p.install_from_path(x.download())"
  ```
  Danach in der App **Argos Translate** auswählen. Die Einrichtung lädt das Sprachpaket herunter.
- **Stimme:** `espeak-ng` installieren und in der App auswählen, oder Piper installieren (`.venv-dubber/bin/pip install piper-tts`) und ein deutsches Piper-ONNX-Stimmenmodell einschließlich der gleichnamigen `.onnx.json` herunterladen. Vor dem Start `export DUBBER_PIPER_MODEL=/voller/pfad/zur/stimme.onnx` setzen und **Piper** auswählen. Deutsche Modelle sind im [Piper-Stimmenverzeichnis](https://huggingface.co/rhasspy/piper-voices/tree/main/de) verfügbar. Beachte die jeweilige Modelllizenz.

## Konfiguration

- `DUBBER_OLLAMA_URL`: Ollama-Endpunkt (Standard `http://127.0.0.1:11434`). Das Modell wird in der Oberfläche gewählt und muss installiert sein.
- `DUBBER_PIPER_MODEL`: Pfad zur Piper-ONNX-Datei.
- `DUBBER_DATA_DIR`: Projektverzeichnis (Standard `dubber/data`). Enthält Originalvideo, Übersetzungen und Ergebnis.
- `DUBBER_MAX_UPLOAD_MB`: Größenlimit (Standard 1024 MB; die Anzeige in der Oberfläche zeigt den Standardwert).
- `DUBBER_HOST`, `DUBBER_PORT`: Server-Adresse und Port (Standard `127.0.0.1`, `8765`). Die App hat **keine Anmeldung**. Nur lokal oder in einem geschützten privaten Netzwerk betreiben; nicht öffentlich ins Internet stellen.

Die Transkription und Übersetzung sind nicht fehlerfrei: bitte das Ergebnis prüfen. Die Stimme wird je Segment in dessen Zeitfenster eingefügt und bei Bedarf beschleunigt. Besonders lange Übersetzungen können schnell klingen; kürze sie im Editor. Die Bildspur wird für MP4 neu kodiert, daher benötigt das Programm ausreichend Platz und Rechenzeit. Eingaben mit mehreren Tonspuren verwenden die von Whisper ausgewählte Standardtonspur, die Ausgabe enthält nur eine neue deutsche Tonspur.

## Kommandozeile

```bash
.venv-dubber/bin/python -m dubber.cli video.mp4 --output deutsch.mp4 --tts espeak
# Optionen anzeigen:
.venv-dubber/bin/python -m dubber.cli --help
```

Auch hier muss Ollama laufen; `--translation argos`, `--whisper-model`, `--ollama-model`, `--tts` und `--voice` sind wählbar. Fehler und fehlende Modelle werden angezeigt. Die CLI speichert kein bearbeitbares Projekt.
