"""Transkription, Übersetzung, Sprachsynthese und Medienverarbeitung."""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import av
import requests

RATE = 24000


def ffmpeg():
    import imageio_ffmpeg
    return shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


def run(args):
    p = subprocess.run([ffmpeg(), '-hide_banner', '-loglevel', 'error', '-y', *map(str, args)], capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError('FFmpeg: ' + p.stderr[-1200:])


def probe(path):
    try:
        container = av.open(str(path))
    except Exception as exc:
        raise ValueError('Die Datei ist kein lesbares Video: ' + str(exc)) from exc
    with container:
        if not container.streams.video or not container.streams.audio:
            raise ValueError('Das Video muss eine Video- und eine Audiospur enthalten.')
        duration = (container.duration or 0) / av.time_base
        if duration <= 0:
            raise ValueError('Die Videodauer konnte nicht ermittelt werden.')
        return duration


def transcribe(path, model='base', progress=lambda *_: None):
    from faster_whisper import WhisperModel
    progress('Spracherkennung', 'Whisper-Modell wird geladen; beim ersten Mal ist ein Download nötig.')
    whisper = WhisperModel(model, device='cpu', compute_type='int8')
    segments, _ = whisper.transcribe(str(path), language='en', vad_filter=True, beam_size=5)
    result = []
    for s in segments:
        text = s.text.strip()
        if text and s.end > s.start:
            result.append({'start': round(s.start, 3), 'end': round(s.end, 3), 'english': text, 'german': ''})
    if not result:
        raise ValueError('Keine englische Sprache erkannt. Bitte prüfe die Tonspur.')
    return result


def translate_text(text, engine, model):
    if engine == 'ollama':
        base = os.environ.get('DUBBER_OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
        response = requests.post(base + '/api/generate', json={
            'model': model, 'stream': False,
            'system': 'Du bist ein professioneller Übersetzer und Synchronautor. Übersetze Englisch idiomatisch ins Deutsche. Gib ausschließlich die Übersetzung aus, ohne Anführungszeichen oder Erklärungen. Formuliere möglichst kurz und natürlich.',
            'prompt': text, 'options': {'temperature': 0.2},
        }, timeout=300)
        response.raise_for_status()
        translated = response.json().get('response', '').strip().strip('"')
    elif engine == 'argos':
        try:
            import argostranslate.translate
            translated = argostranslate.translate.translate(text, 'en', 'de').strip()
        except Exception as exc:
            raise RuntimeError('Argos EN→DE ist nicht installiert. Siehe Anleitung zur Offline-Einrichtung.') from exc
    else:
        raise ValueError('Unbekannte Übersetzungs-Engine.')
    if not translated:
        raise ValueError('Die Übersetzung ist leer. Bitte prüfe die Übersetzungs-Engine.')
    return translated


def translate(segments, engine, model, progress=lambda *_: None):
    for i, seg in enumerate(segments):
        progress('Übersetzung', f'Segment {i + 1} von {len(segments)} wird übersetzt.')
        seg['german'] = translate_text(seg['english'], engine, model)
    return segments


def synthesize(text, path, voice, tts):
    """Explicitly selected backend; never silently send text to the internet."""
    if tts == 'edge':
        import edge_tts
        asyncio.run(edge_tts.Communicate(text, voice).save(str(path)))
    elif tts == 'piper':
        model = os.environ.get('DUBBER_PIPER_MODEL', '')
        if not model or not Path(model).is_file() or not Path(model + '.json').is_file():
            raise RuntimeError('Piper-Modell fehlt. DUBBER_PIPER_MODEL muss auf eine .onnx-Datei mit zugehöriger .onnx.json zeigen.')
        local_piper = Path(sys.executable).parent / 'piper'
        executable = str(local_piper) if local_piper.is_file() else shutil.which('piper')
        if not executable:
            raise RuntimeError('Piper ist nicht installiert. Siehe Anleitung.')
        result = subprocess.run([executable, '--model', model, '--output_file', str(path)], input=text, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError('Piper: ' + result.stderr[-1000:])
    elif tts == 'espeak':
        executable = shutil.which('espeak-ng') or shutil.which('espeak')
        if not executable:
            raise RuntimeError('espeak-ng ist nicht installiert. Siehe Anleitung.')
        result = subprocess.run([executable, '-v', 'de', '-s', '165', '-w', str(path), '--stdin'], input=text, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError('espeak-ng: ' + result.stderr[-1000:])
    else:
        raise ValueError('Unbekannte Stimmen-Engine.')


def tempo_filters(factor):
    # FFmpeg atempo supports factors from 0.5 to 100; small steps avoid extremes.
    parts = []
    while factor > 2:
        parts.append('atempo=2')
        factor /= 2
    while factor < 0.5:
        parts.append('atempo=0.5')
        factor /= 0.5
    parts.append(f'atempo={factor:.8f}')
    return ','.join(parts)


def render(video, segments, duration, directory, voice, tts, progress=lambda *_: None):
    """Place each segment in its time window and discard every original audio stream."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    full_audio = directory / 'german.wav'
    cursor = 0
    total_samples = round(duration * RATE)
    with wave.open(str(full_audio), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        for i, seg in enumerate(segments):
            progress('Synchronisation', f'Deutsche Stimme: Segment {i + 1} von {len(segments)}.')
            start = min(total_samples, round(seg['start'] * RATE))
            end = min(total_samples, round(seg['end'] * RATE))
            if i + 1 < len(segments):
                end = min(end, round(segments[i + 1]['start'] * RATE))
            if start < cursor or end <= start:
                raise ValueError(f'Segment {i + 1} überlappt oder hat keine gültige Dauer.')
            silence = start - cursor
            while silence:
                amount = min(silence, RATE * 10)
                output.writeframesraw(b'\0\0' * amount)
                silence -= amount
            source = directory / f'voice-{i}.wav'
            normalized = directory / f'normal-{i}.wav'
            fitted = directory / f'fitted-{i}.wav'
            synthesize(seg['german'], source, voice, tts)
            run(['-i', source, '-vn', '-ac', '1', '-ar', str(RATE), '-c:a', 'pcm_s16le', normalized])
            with wave.open(str(normalized), 'rb') as w:
                samples = w.getnframes()
            if samples == 0:
                raise ValueError(f'Segment {i + 1}: Stimme ist leer.')
            slot = end - start
            if samples > slot:
                run(['-i', normalized, '-af', tempo_filters(samples / slot), '-ac', '1', '-ar', str(RATE), '-c:a', 'pcm_s16le', fitted])
                audio = fitted
            else:
                audio = normalized
            with wave.open(str(audio), 'rb') as w:
                # Bound each segment to its slot even if atempo output differs slightly.
                raw = w.readframes(slot)
            output.writeframesraw(raw)
            written = len(raw) // 2
            cursor = start + written
            for temporary in (source, normalized, fitted):
                temporary.unlink(missing_ok=True)
        remaining = total_samples - cursor
        while remaining > 0:
            amount = min(remaining, RATE * 10)
            output.writeframesraw(b'\0\0' * amount)
            remaining -= amount
    progress('Video erstellen', 'Die Originaltonspur wird entfernt und die deutsche Stimme eingesetzt.')
    target = directory / 'result.mp4'
    temporary = directory / 'result.tmp.mp4'
    run(['-i', video, '-i', full_audio, '-map', '0:v:0', '-map', '1:a:0', '-map_metadata', '-1', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-t', str(duration), temporary])
    temporary.replace(target)
    full_audio.unlink(missing_ok=True)
    return target
