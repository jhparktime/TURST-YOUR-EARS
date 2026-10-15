"""Run Copy and blind Whisper baselines on a sealed merged dataset.

Predictions, checkpoints and private-test scores belong in a private work folder.
Audio-only reuse is keyed by exact WAV hash, fixed model and decoding settings.
No cached draft-based prediction is accepted.
"""
import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.baseline import load_inputs
from scripts.build_dataset import digest, write_json
from scripts.import_pilot160 import write_csv
from scripts.transcribe_audio import MODEL, REVISION, transcribe
from server.scoring import score, validate_manifest


def run(public, private, work, model_cache, reuse):
    work.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((public / 'metadata.json').read_text())
    if metadata != json.loads((private / 'metadata.json').read_text()):
        raise ValueError('Public/private dataset metadata mismatch.')
    state = {'dataset': metadata['name'], 'metadata_sha256': digest(public / 'metadata.json'),
        'model': MODEL, 'revision': REVISION, 'status': 'preparing',
        'started_at': datetime.now(timezone.utc).isoformat(),
        'hardware': {'platform': platform.platform(), 'machine': platform.machine()},
        'python': sys.version, 'draft_access': False, 'reference_access_during_inference': False}
    status_path = work / 'status.json'
    write_json(status_path, state)
    input_rows, split_ids = [], {}
    # Copy controls do not run a model. Save separately from audio inference.
    for split in ('train', 'eval', 'test'):
        folder = (private if split == 'test' else public) / split
        manifest = folder / 'inputs.json'
        if digest(manifest) != metadata['splits'][split]['inputs_sha256']:
            raise ValueError('Sealed input manifest changed.')
        rows = load_inputs(manifest)
        split_ids[split] = [r['id'] for r in rows]
        target = work / split
        target.mkdir(exist_ok=True)
        copied = {r['id']: r['draft'] for r in rows}
        write_csv(target / 'copy.csv', ['id', 'prediction'],
                  [{'id': r['id'], 'prediction': r['draft']} for r in rows])
        refpath = private / 'test-references.json' if split == 'test' else folder / 'references.json'
        if digest(refpath) != metadata['splits'][split]['references_sha256']:
            raise ValueError('Sealed reference manifest changed.')
        refs = validate_manifest(json.loads(refpath.read_text()))
        write_json(target / 'copy.scores.json', score(copied, refs))
        if split != 'train':
            input_rows.extend({'id': r['id'], 'audio': str((folder / r['audio']).resolve())} for r in rows)
    inputs_path = work / 'audio-only-inputs.json'
    audio_manifest = {'name': metadata['name'] + '-eval-test-blind-audio', 'items': input_rows}
    if inputs_path.exists() and json.loads(inputs_path.read_text()) != audio_manifest:
        raise ValueError('Work directory belongs to different inference inputs.')
    write_json(inputs_path, audio_manifest)
    state['input_rows'] = len(input_rows)
    state['split_rows'] = {s: len(ids) for s, ids in split_ids.items()}
    state['inputs_sha256'] = digest(inputs_path)
    infer_dir = work / 'audio-only'
    infer_dir.mkdir(exist_ok=True)
    checkpoint = infer_dir / 'audio-only.json'
    # Seed only a new run. A resumed run owns its existing checkpoint.
    if not checkpoint.exists():
        cached, receipts = {}, []
        for path in reuse:
            saved = json.loads(path.read_text())
            if (saved.get('model'), saved.get('revision')) != (MODEL, REVISION):
                raise ValueError('Audio-only reuse model mismatch.')
            for row in saved['items']:
                checksum = row['audio_sha256']
                if checksum in cached and cached[checksum]['prediction'] != row['prediction']:
                    raise ValueError('Conflicting cached predictions for identical audio.')
                cached[checksum] = row
            receipts.append({'path': str(path.resolve()), 'sha256': digest(path), 'rows': len(saved['items'])})
        seeded = []
        for row in input_rows:
            checksum = digest(Path(row['audio']))
            if checksum in cached:
                seed = cached[checksum]
                seeded.append({'id': row['id'], 'audio_sha256': checksum,
                    'prediction': seed['prediction'], 'elapsed_seconds': seed['elapsed_seconds'],
                    'reused_from_audio_sha256': checksum})
        write_json(checkpoint, {'model': MODEL, 'revision': REVISION, 'items': seeded})
        write_json(work / 'reuse.json', {'model': MODEL, 'revision': REVISION,
            'decoding': {'language': 'ko', 'task': 'transcribe', 'temperature': 0.0,
                         'condition_on_previous_text': False, 'initial_prompt': None},
            'sources': receipts, 'reused_rows': len(seeded),
            'restriction': 'Only trusted scripts.transcribe_audio blind-audio runs with these fixed settings.'})
    state['status'] = 'running_audio_only'
    state['checkpoint'] = str(checkpoint.resolve())
    write_json(status_path, state)
    print(f"Starting blind audio baseline on {len(input_rows)} frozen eval/test recordings", flush=True)
    # Only ID and audio paths enter this function; never the references or drafts.
    transcribe(inputs_path, infer_dir, model_cache)
    predictions = {r['id']: r['prediction'] for r in json.loads(checkpoint.read_text())['items']}
    scores = {}
    for split in ('eval', 'test'):
        ids = split_ids[split]
        rows = [{'id': ident, 'prediction': predictions[ident]} for ident in ids]
        path = work / split / 'audio-only.csv'
        write_csv(path, ['id', 'prediction'], rows)
        refpath = private / 'test-references.json' if split == 'test' else public / split / 'references.json'
        refs = validate_manifest(json.loads(refpath.read_text()))
        result = score({r['id']: r['prediction'] for r in rows}, refs)
        write_json(work / split / 'audio-only.scores.json', result)
        scores[split] = result
    state['status'] = 'completed'
    state['finished_at'] = datetime.now(timezone.utc).isoformat()
    state['prediction_rows'] = len(predictions)
    state['macro_cer'] = {s: result['macro_cer'] for s, result in scores.items()}
    write_json(status_path, state)
    print(json.dumps(state, ensure_ascii=False, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('public', 'private', 'work', 'model-cache'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--reuse', type=Path, action='append', default=[])
    args = parser.parse_args()
    try:
        run(args.public, args.private, args.work, args.model_cache, args.reuse)
    except Exception as exc:
        path = args.work / 'status.json'
        state = json.loads(path.read_text()) if path.exists() else {}
        write_json(path, state | {'status': 'failed', 'error': str(exc),
                                  'failed_at': datetime.now(timezone.utc).isoformat()})
        raise


if __name__ == '__main__':
    main()
