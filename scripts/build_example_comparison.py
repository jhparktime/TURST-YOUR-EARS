"""Publish two selected public Eval contrasts from recorded baseline predictions.

This exports public Eval rows only; selected cases do not estimate overall quality.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import wave

from server.scoring import parse_submission
from server.scoring_v2 import score, validate_manifest

ROOT = Path(__file__).resolve().parent.parent
SELECTED = [('601a22f6ff80b3227f4e', 'repair'), ('e245e5eed59e0ba5fc1a', 'preserve')]


def build(eval_root, audio_draft_csv):
    manifest = json.loads((eval_root/'references.json').read_text())
    if manifest.get('name') != 'tye-ko-asr-v2-eval':
        raise ValueError('Only the public v2 Eval split may be exported.')
    refs = {r['id']: r for r in validate_manifest(manifest)}
    canonical = json.loads((ROOT/'web/data-v2/eval.json').read_text())
    if manifest != canonical:
        raise ValueError('Eval references must match the public website version.')
    paths = {'Copy draft': eval_root/'copy-draft.csv',
             'Whisper audio-only': eval_root/'whisper-audio-only.csv',
             'Qwen audio+draft': audio_draft_csv}
    predictions = {k: parse_submission(p.read_bytes()) for k, p in paths.items()}
    if any(set(p) != set(refs) for p in predictions.values()):
        raise ValueError('Each baseline must cover exactly the public Eval IDs.')
    if any(predictions['Copy draft'][k] != r['draft'] for k, r in refs.items()):
        raise ValueError('Copy must reproduce the distributed draft.')
    expected = {e['baseline']: e['metrics'] for e in
                json.loads((ROOT/'web/data-v2/baselines.json').read_text())['entries'] if e['split']=='eval'}
    for label, values in predictions.items():
        if score(values, list(refs.values())) != expected[label]:
            raise ValueError('Recorded baseline does not match the published full Eval measurements: '+label)
    hashes = json.loads((ROOT/'datasets/tye-ko-asr-v2/eval/audio-checksums.json').read_text())
    folder = ROOT/'web/assets/examples-v2'
    examples, comparisons = [], []
    for ident, kind in SELECTED:
        ref = refs[ident]
        audio = eval_root/'audio'/f'{ident}.wav'
        digest = hashlib.sha256(audio.read_bytes()).hexdigest()
        if digest != hashes[ident]:
            raise ValueError('Audio differs from the distributed Eval recording.')
        target = folder/audio.name
        shutil.copy2(audio, target)
        with wave.open(str(target)) as stream:
            duration = stream.getnframes()/stream.getframerate()
        examples.append({**ref, 'kind': kind, 'audio': 'assets/examples-v2/'+audio.name,
                         'duration_seconds': duration, 'sha256': digest})
        systems = [{'system': label, 'prediction': p[ident], 'metrics': score({ident:p[ident]}, [ref])}
                   for label, p in predictions.items()]
        comparisons.append({'id': ident, 'systems': systems})
    example_data = {'dataset':'tye-ko-asr-v2-eval',
        'purpose':'Two illustrative public Eval cases: correction and preservation; not a population-level performance estimate',
        'source':'https://huggingface.co/datasets/kresnik/zeroth_korean', 'license':'CC-BY-4.0', 'items':examples}
    comparison_data = {'dataset':'tye-ko-asr-v2-eval', 'protocol':'ko-correction-v2',
        'selection':'Two selected contrasts from fixed organizer baseline outputs; overall ranking uses the complete Eval split',
        'sources':[{'system':k, 'csv_sha256':hashlib.sha256(p.read_bytes()).hexdigest(), 'rows':len(predictions[k])}
                   for k,p in paths.items()], 'items':comparisons}
    for name, data in [('examples.json',example_data), ('model-comparison.json',comparison_data)]:
        (folder/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return {'public_examples':len(examples), 'systems_per_example':3}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--eval-root', type=Path, required=True)
    parser.add_argument('--audio-draft-csv', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.eval_root, args.audio_draft_csv)))
