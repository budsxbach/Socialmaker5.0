"""Kommandozeilen-Variante: python -m dubber.cli VIDEO --output AUSGABE.mp4"""
import argparse
import shutil
import tempfile
from pathlib import Path
from dubber import engine


def main():
    parser = argparse.ArgumentParser(description='Englisches Video mit deutscher Stimme synchronisieren.')
    parser.add_argument('video', type=Path)
    parser.add_argument('--output', type=Path, default=Path('deutsch-synchronisiert.mp4'))
    parser.add_argument('--whisper-model', choices=['tiny', 'base', 'small', 'medium'], default='base')
    parser.add_argument('--translation', choices=['ollama', 'argos'], default='ollama')
    parser.add_argument('--ollama-model', default='qwen2.5:7b-instruct')
    parser.add_argument('--tts', choices=['edge', 'piper', 'espeak'], default='edge')
    parser.add_argument('--voice', default='de-DE-KatjaNeural')
    args = parser.parse_args()
    if args.video.resolve() == args.output.resolve():
        parser.error('Ausgabedatei und Eingabedatei müssen verschieden sein.')
    def report(stage, detail): print(f'{stage}: {detail}', flush=True)
    duration = engine.probe(args.video)
    segments = engine.transcribe(args.video, args.whisper_model, report)
    normalized = []
    for segment in segments:
        segment['start'] = max(0, segment['start'], normalized[-1]['end'] if normalized else 0)
        segment['end'] = min(duration, segment['end'])
        if segment['end'] > segment['start']:
            normalized.append(segment)
    if not normalized: raise ValueError('Keine Sprachsegmente innerhalb des Videos gefunden.')
    segments = engine.translate(normalized, args.translation, args.ollama_model, report)
    with tempfile.TemporaryDirectory(prefix='stimmwechsel-') as tmp:
        result = engine.render(args.video, segments, duration, tmp, args.voice, args.tts, report)
        shutil.copy2(result, args.output)
    print(f'Fertig: {args.output}')


if __name__ == '__main__':
    main()
