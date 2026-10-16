"""Freeze reference-blind drafter assignment before preparing real-ASR v2.

No reference text, per-utterance score or synthetic condition is opened here.
Existing speaker/text-disjoint recordings are retained, not selected by errors.
The plan contains private IDs and must stay outside the public repository.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.baseline import load_inputs
from scripts.build_dataset import digest, write_json

NAME = 'tye-ko-asr-v2'
SEED = 'tye-real-asr-v2-assignment-20261016'
SOURCES = ('whisper-turbo', 'qwen-omni')


def assignment(rows, split):
    ordered = sorted(rows, key=lambda r: hashlib.sha256(
        f'{SEED}:{split}:{r["id"]}'.encode()).hexdigest())
    return {row['id']: SOURCES[index % 2] for index, row in enumerate(ordered)}


def prepare(public, private, output):
    if output.exists():
        raise ValueError('Plan output already exists; never overwrite a frozen assignment.')
    metadata = json.loads((public / 'metadata.json').read_text())
    if metadata['name'] != 'tye-ko-merged-v1':
        raise ValueError('Expected the frozen merged-v1 source recordings.')
    plan = {'name': NAME, 'state': 'assignment_frozen_before_reference_text_read',
            'source_dataset': metadata['name'], 'source_metadata_sha256': digest(public / 'metadata.json'),
            'seed': SEED, 'assignment': 'SHA256(seed:split:id) rank, alternate two fixed drafters',
            'selection_uses_reference_or_asr_score': False,
            'audio_split_changed': False, 'recordings_dropped': 0, 'sources': {
                'whisper-turbo': {'model': 'mlx-community/whisper-large-v3-turbo',
                    'revision': 'a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb',
                    'language': 'ko', 'temperature': 0, 'previous_context': False},
                'qwen-omni': {'model': 'Qwen/Qwen2.5-Omni-3B',
                    'revision': 'f75b40e3da2003cdd6e1829b1f420ca70797c34e',
                    'mode': 'audio-only', 'seed': 0, 'max_new_tokens': 512,
                    'do_sample': False, 'reference_access': False}}, 'splits': {}}
    output.mkdir(parents=True, mode=0o700)
    for split in ('train', 'eval', 'test'):
        path = (private if split == 'test' else public) / split / 'inputs.json'
        if digest(path) != metadata['splits'][split]['inputs_sha256']:
            raise ValueError('Source inputs differ from the frozen source metadata.')
        rows = load_inputs(path)
        assigned = assignment(rows, split)
        planned = [{'id': row['id'], 'source': assigned[row['id']],
                    'audio': str((path.parent / row['audio']).resolve()),
                    'audio_sha256': digest(path.parent / row['audio'])} for row in rows]
        plan['splits'][split] = {'source_inputs_sha256': digest(path),
            'utterances': len(rows), 'source_counts': dict(Counter(assigned.values())), 'items': planned}
        if split == 'train':
            # Only missing training drafts require inference. Audio-only models
            # ignore this original synthetic draft, which is never a target.
            for source in SOURCES:
                selected = [dict(row, audio=str((path.parent / row['audio']).resolve()))
                            for row in rows if assigned[row['id']] == source]
                target = output / 'jobs' / source / 'train' / 'inputs.json'
                target.parent.mkdir(parents=True, exist_ok=True)
                write_json(target, {'name': f'{NAME}-training-drafter-jobs-{source}',
                                    'items': selected})
    write_json(output / 'plan.json', plan)
    (output / 'plan.sha256').write_text(digest(output / 'plan.json') + '\n')
    print(json.dumps({'plan_sha256': digest(output / 'plan.json'),
        'splits': {key: {k: v for k, v in value.items() if k != 'items'}
                   for key, value in plan['splits'].items()}}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--private', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.public, args.private, args.output)
