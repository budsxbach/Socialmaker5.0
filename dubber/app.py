"""Lokale Weboberfläche für die Video-Synchronisation."""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dubber import engine

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('DUBBER_DATA_DIR', ROOT / 'data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
MAX_BYTES = int(os.environ.get('DUBBER_MAX_UPLOAD_MB', '1024')) * 1024 * 1024
app = FastAPI(title='Stimmwechsel DE', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
lock = threading.RLock()
worker = threading.Lock()


def directory(job_id):
    if not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise HTTPException(404, 'Projekt nicht gefunden.')
    path = DATA / job_id
    if not (path / 'job.json').is_file():
        raise HTTPException(404, 'Projekt nicht gefunden.')
    return path


def read_job(job_id):
    with lock:
        try:
            return json.loads((directory(job_id) / 'job.json').read_text(encoding='utf-8'))
        except FileNotFoundError:
            raise HTTPException(404, 'Projekt nicht gefunden.')


def save(job_id, **changes):
    with lock:
        path = directory(job_id) / 'job.json'
        job = json.loads(path.read_text(encoding='utf-8'))
        job.update(changes)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(path)
        return job


def progress(job_id, stage, detail):
    save(job_id, stage=stage, detail=detail)


def process(job_id, rerender=False):
    try:
        with worker:
            job = read_job(job_id)
            path = directory(job_id)
            if not rerender:
                progress(job_id, 'Video prüfen', 'Das Video und seine Tonspur werden geprüft.')
                duration = engine.probe(path / 'source')
                save(job_id, duration=duration)
                segments = engine.transcribe(path / 'source', job['whisper_model'], lambda s, d: progress(job_id, s, d))
                # Whisper timestamps can slightly overlap or extend past the container.
                normalized = []
                for segment in segments:
                    segment['start'] = max(0.0, segment['start'], normalized[-1]['end'] if normalized else 0.0)
                    segment['end'] = min(duration, segment['end'])
                    if segment['end'] > segment['start']:
                        normalized.append(segment)
                if not normalized:
                    raise ValueError('Keine Sprachsegmente innerhalb des Videos gefunden.')
                segments = engine.translate(normalized, job['translation'], job['ollama_model'], lambda s, d: progress(job_id, s, d))
                save(job_id, segments=segments)
            else:
                duration = job['duration']
                segments = job['segments']
            engine.render(path / 'source', segments, duration, path / 'render', job['voice'], job['tts'], lambda s, d: progress(job_id, s, d))
            save(job_id, status='done', stage='Fertig', detail='Dein Video mit deutscher Tonspur ist bereit.', error=None)
    except Exception as exc:
        save(job_id, status='error', stage='Verarbeitung fehlgeschlagen', detail='Bitte prüfe die Einstellungen und versuche es erneut.', error=str(exc)[:1500])


def launch(job_id, rerender=False):
    threading.Thread(target=process, args=(job_id, rerender), daemon=True).start()


@app.get('/')
def index():
    return FileResponse(ROOT / 'static' / 'index.html')


@app.get('/api/jobs')
def list_jobs():
    jobs = []
    for p in DATA.iterdir():
        if p.is_dir() and re.fullmatch(r'[a-f0-9]{32}', p.name) and (p / 'job.json').is_file():
            try:
                jobs.append(read_job(p.name))
            except (ValueError, OSError, HTTPException):
                continue
    return sorted(jobs, key=lambda x: x.get('created', ''), reverse=True)[:50]


@app.post('/api/jobs')
async def create_job(file: UploadFile = File(...), whisper_model: str = Form('base'), translation: str = Form('ollama'), ollama_model: str = Form('qwen2.5:7b-instruct'), tts: str = Form('edge'), voice: str = Form('de-DE-KatjaNeural')):
    if whisper_model not in {'tiny', 'base', 'small', 'medium'} or translation not in {'ollama', 'argos'} or tts not in {'edge', 'piper', 'espeak'}:
        raise HTTPException(400, 'Ungültige Einstellungen.')
    if voice not in {'de-DE-KatjaNeural', 'de-DE-ConradNeural', 'de-DE-AmalaNeural', 'de-DE-KillianNeural'} or not re.fullmatch(r'[\w.:-]{1,100}', ollama_model):
        raise HTTPException(400, 'Ungültige Stimme oder ungültiger Modellname.')
    job_id = uuid.uuid4().hex
    path = DATA / job_id
    path.mkdir()
    size = 0
    try:
        with (path / 'source').open('wb') as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, f'Datei zu groß (maximal {MAX_BYTES // (1024 * 1024)} MB).')
                out.write(chunk)
        if not size:
            raise HTTPException(400, 'Die Datei ist leer.')
        from datetime import datetime, timezone
        job = {'id': job_id, 'filename': Path(file.filename or 'Video').name[:200], 'created': datetime.now(timezone.utc).isoformat(), 'status': 'working', 'stage': 'Warteschlange', 'detail': 'Das Video wartet auf die Verarbeitung.', 'segments': [], 'error': None, 'duration': None, 'whisper_model': whisper_model, 'translation': translation, 'ollama_model': ollama_model, 'tts': tts, 'voice': voice}
        (path / 'job.json').write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
        launch(job_id)
        return job
    except Exception:
        shutil.rmtree(path, ignore_errors=True)
        raise
    finally:
        await file.close()


@app.get('/api/jobs/{job_id}')
def get_job(job_id: str):
    return read_job(job_id)


class Segment(BaseModel):
    start: float
    end: float
    english: str = Field(max_length=5000)
    german: str = Field(min_length=1, max_length=5000)


class Revision(BaseModel):
    segments: list[Segment] = Field(min_length=1, max_length=10000)


@app.post('/api/jobs/{job_id}/render')
def rerender(job_id: str, revision: Revision):
    with lock:
        job = read_job(job_id)
        if job['status'] == 'working':
            raise HTTPException(409, 'Das Projekt wird gerade verarbeitet.')
        if not job.get('duration'):
            raise HTTPException(400, 'Für dieses Projekt liegt noch kein Transkript vor.')
        segments = [s.model_dump() for s in revision.segments]
        previous = 0.0
        for s in segments:
            if not all(math.isfinite(x) for x in (s['start'], s['end'])) or s['start'] < previous or s['end'] <= s['start'] or s['end'] > job['duration'] + 0.01 or not s['german'].strip():
                raise HTTPException(400, 'Segmente müssen Text und gültige, aufeinanderfolgende Zeiten innerhalb des Videos haben.')
            previous = s['end']
        save(job_id, segments=segments, status='working', stage='Warteschlange', detail='Die neue Vertonung wartet auf die Verarbeitung.', error=None)
        launch(job_id, True)
    return {'ok': True}


@app.post('/api/jobs/{job_id}/retry')
def retry(job_id: str):
    with lock:
        job = read_job(job_id)
        if job['status'] != 'error':
            raise HTTPException(409, 'Dieses Projekt kann gerade nicht erneut gestartet werden.')
        save(job_id, status='working', stage='Warteschlange', detail='Das Projekt wird erneut verarbeitet.', error=None)
        launch(job_id, bool(job.get('segments') and job.get('duration')))
    return {'ok': True}


@app.get('/api/jobs/{job_id}/video')
def video(job_id: str):
    job = read_job(job_id)
    path = directory(job_id) / 'render' / 'result.mp4'
    if job['status'] != 'done' or not path.exists():
        raise HTTPException(404, 'Video noch nicht verfügbar.')
    return FileResponse(path, media_type='video/mp4', filename='deutsch-synchronisiert.mp4', content_disposition_type='inline')


@app.delete('/api/jobs/{job_id}')
def delete(job_id: str):
    with lock:
        job = read_job(job_id)
        if job['status'] == 'working':
            raise HTTPException(409, 'Ein laufendes Projekt kann nicht gelöscht werden.')
        shutil.rmtree(directory(job_id))
    return {'ok': True}


# A stopped server cannot continue its in-memory worker. Make interrupted jobs retryable.
for existing in DATA.iterdir():
    if existing.is_dir() and re.fullmatch(r'[a-f0-9]{32}', existing.name) and (existing / 'job.json').is_file():
        try:
            if read_job(existing.name)['status'] == 'working':
                save(existing.name, status='error', stage='Unterbrochen', detail='Der Server wurde neu gestartet.', error='Bitte erneut versuchen.')
        except (OSError, ValueError, HTTPException):
            pass
