import io
import time
import wave
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from dubber import app as web, engine


def wait(client, job_id):
    for _ in range(300):
        job = client.get('/api/jobs/' + job_id).json()
        if job['status'] != 'working':
            return job
        time.sleep(.05)
    raise AssertionError('Job timed out')


def test_pipeline_and_editor(tmp_path, monkeypatch):
    monkeypatch.setattr(web, 'DATA', tmp_path / 'jobs')
    web.DATA.mkdir()
    source = tmp_path / 'input.mp4'
    engine.run(['-f', 'lavfi', '-i', 'color=c=blue:s=160x120:r=10:d=3', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', source])
    monkeypatch.setattr(engine, 'transcribe', lambda *a, **kw: [{'start': .5, 'end': 1.3, 'english': 'Hello', 'german': ''}, {'start': 1.8, 'end': 2.5, 'english': 'World', 'german': ''}])
    monkeypatch.setattr(engine, 'translate', lambda s, *a, **kw: [dict(x, german='Hallo' if i == 0 else 'Welt') for i, x in enumerate(s)])
    spoken = []
    def synth(text, path, voice, tts):
        spoken.append(text)
        engine.run(['-f', 'lavfi', '-i', 'sine=frequency=1000:sample_rate=24000:duration=1.4', '-c:a', 'pcm_s16le', path])
    monkeypatch.setattr(engine, 'synthesize', synth)
    with TestClient(web.app) as client:
        response = client.post('/api/jobs', files={'file': ('test.mp4', source.read_bytes(), 'video/mp4')})
        assert response.status_code == 200, response.text
        job_id = response.json()['id']
        job = wait(client, job_id)
        assert job['status'] == 'done', job
        assert spoken == ['Hallo', 'Welt']
        result = client.get(f'/api/jobs/{job_id}/video')
        assert result.status_code == 200
        output = tmp_path / 'output.mp4'
        output.write_bytes(result.content)
        import av
        with av.open(str(output)) as media:
            assert len(media.streams.audio) == 1
            assert len(media.streams.video) == 1
        decoded = tmp_path / 'audio.wav'
        engine.run(['-i', output, '-map', '0:a:0', '-ac', '1', '-ar', '24000', '-c:a', 'pcm_s16le', decoded])
        with wave.open(str(decoded), 'rb') as w:
            samples = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(float)
        # Original 440 Hz tone is gone in the silence before the new narrator.
        assert np.max(np.abs(samples[3000:9000])) < 30
        assert np.max(np.abs(samples[16000:25000])) > 100
        segments = job['segments']
        segments[0]['german'] = 'Guten Tag'
        response = client.post(f'/api/jobs/{job_id}/render', json={'segments': segments})
        assert response.status_code == 200
        job = wait(client, job_id)
        assert job['status'] == 'done', job
        assert spoken[-2:] == ['Guten Tag', 'Welt']
        segments[0]['end'] = 2
        assert client.post(f'/api/jobs/{job_id}/render', json={'segments': segments}).status_code == 400
        assert client.delete(f'/api/jobs/{job_id}').status_code == 200
        assert client.get(f'/api/jobs/{job_id}').status_code == 404


def test_invalid_video_and_empty_upload(tmp_path, monkeypatch):
    monkeypatch.setattr(web, 'DATA', tmp_path)
    with TestClient(web.app) as client:
        assert client.post('/api/jobs', files={'file': ('empty.mp4', b'', 'video/mp4')}).status_code == 400
        res = client.post('/api/jobs', files={'file': ('bad.mp4', b'not a video', 'video/mp4')})
        job = wait(client, res.json()['id'])
        assert job['status'] == 'error'
        assert 'lesbares Video' in job['error']
        assert client.get('/api/jobs/../../etc/passwd').status_code != 200
