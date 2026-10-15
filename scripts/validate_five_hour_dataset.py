"""Independently re-open a public eval/private test delivery and optional upstream."""
import argparse
import difflib
import hashlib
import json
import unicodedata
from collections import Counter
from pathlib import Path

from scripts.baseline import load_inputs
from scripts.build_dataset import digest
from scripts.zeroth_source import batches, verify
from server.scoring import normalize, parse_submission, score, validate_manifest


def near(a, b):
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return matcher.quick_ratio() >= .85 and matcher.ratio() >= .85


def validate(public, private, source_cache=None):
    import numpy as np
    import soundfile as sf
    metadata = json.loads((public / 'metadata.json').read_text())
    if metadata != json.loads((private / 'metadata.json').read_text()):
        raise ValueError('Public/private release metadata differs.')
    if metadata['status'] != 'pilot_pending_independent_listening' or metadata['human_listening_review'] != 'not_performed':
        raise ValueError('This release does not certify human listening.')
    for root in (public, private):
        lock = json.loads((root / 'release-lock.json').read_text())['sha256']
        actual = {str(p.relative_to(root)): digest(p) for p in root.rglob('*')
                  if p.is_file() and p.name != 'release-lock.json'}
        if actual != lock: raise ValueError('Delivered files do not match the release lock.')
    if (public / 'test').exists() or any('provenance' in p.name or 'test-references' in p.name for p in public.rglob('*')):
        raise ValueError('Private test data leaked into the public eval folder.')
    provenance = json.loads((private / 'provenance.json').read_text())
    by_id = {r['id']: r for r in provenance}
    if len(by_id) != len(provenance): raise ValueError('Duplicate provenance ID.')
    all_ids, audio_hashes, pcm_hashes, all_texts = set(), set(), set(), set()
    texts, speakers, sessions, report = {}, {}, {}, {}
    for split in ('eval', 'test'):
        folder = (public if split == 'eval' else private) / split
        inputs = load_inputs(folder / 'inputs.json')
        refpath = folder / 'references.json' if split == 'eval' else private / 'test-references.json'
        refs = validate_manifest(json.loads(refpath.read_text()))
        by_ref = {r['id']: r for r in refs}
        if set(by_ref) != {r['id'] for r in inputs}: raise ValueError('Input/reference ID coverage differs.')
        checksums = json.loads((folder / 'audio-checksums.json').read_text())
        if set(checksums) != set(by_ref): raise ValueError('Checksum coverage differs.')
        if {p.name for p in (folder / 'audio').iterdir()} != {f"{r['id']}.wav" for r in inputs}:
            raise ValueError('Audio directory has missing or extra recordings.')
        counts = Counter(r['condition'] for r in refs)
        if max(counts.values()) - min(counts.values()) > 1: raise ValueError('Condition counts are not balanced.')
        duration, frames = 0, 0
        condition_seconds = Counter()
        for row in inputs:
            ident = row['id']; reference = by_ref[ident]; origin = by_id[ident]
            if origin['split'] != split or reference['condition'] != origin['condition']:
                raise ValueError('Private provenance split/condition differs.')
            if row['draft'] != reference['draft'] or row['audio'] != f'audio/{ident}.wav':
                raise ValueError('Input draft/audio differs from its reference.')
            if reference['reference'] != origin['reference'] or len(reference['edits']) != {'clean': 0, 'single': 1, 'multiple': 2}[reference['condition']]:
                raise ValueError('Gold or exact 0/1/2-error count differs.')
            path = folder / row['audio']; checksum = digest(path)
            pcm, rate = sf.read(path, dtype='int16', always_2d=True)
            if rate != 16000 or pcm.shape != (origin['samples'], 1) or not np.any(pcm):
                raise ValueError('Invalid exported waveform shape/encoding.')
            pcm_checksum = hashlib.sha256(pcm.astype('<i2').tobytes()).hexdigest()
            if checksum != checksums[ident] or checksum != origin['audio_sha256'] or pcm_checksum != origin['pcm_sha256']:
                raise ValueError('Waveform/PCM checksum differs.')
            text = normalize(reference['reference'])
            if ident in all_ids or checksum in audio_hashes or pcm_checksum in pcm_hashes or text in all_texts:
                raise ValueError('Duplicate ID, waveform, PCM or source sentence.')
            all_ids.add(ident); audio_hashes.add(checksum); pcm_hashes.add(pcm_checksum); all_texts.add(text)
            frames += len(pcm); condition_seconds[reference['condition']] += len(pcm) / rate
        duration = frames / 16000
        expected = metadata['splits'][split]
        if len(inputs) != expected['utterances'] or dict(counts) != expected['conditions'] or duration != expected['duration_seconds']:
            raise ValueError('Delivered count/duration differs from metadata.')
        if abs(duration - metadata['target_duration_seconds'][split]) > 22:
            raise ValueError('Delivered duration differs from the one/four-hour target by over one utterance.')
        if digest(folder / 'inputs.json') != expected['inputs_sha256'] or digest(refpath) != expected['references_sha256']:
            raise ValueError('Input/reference hash differs from metadata.')
        copy = parse_submission((folder / 'copy-draft.csv').read_bytes())
        if copy != {r['id']: r['draft'] for r in inputs}: raise ValueError('Copy submission differs from drafts.')
        result = score(copy, refs)
        if result != json.loads((folder / 'copy-draft.scores.json').read_text()) or result['restoration_rate'] != 0 or result['harmful_edit_rate'] != 0:
            raise ValueError('Copy control did not reproduce the correction protocol.')
        texts[split] = [normalize(r['reference']) for r in refs]
        selected = [by_id[r['id']] for r in inputs]
        speakers[split] = {r['speaker_id'] for r in selected}
        sessions[split] = {r['session_id'] for r in selected}
        report[split] = {'utterances': len(inputs), 'seconds': duration,
            'speakers': len(speakers[split]), 'conditions': dict(counts),
            'condition_seconds': dict(condition_seconds), 'copy_macro_cer': result['macro_cer']}
    if all_ids != set(by_id): raise ValueError('Provenance does not exactly cover delivered recordings.')
    if speakers['eval'] & speakers['test'] or sessions['eval'] & sessions['test']:
        raise ValueError('Speaker/session overlap across public eval/private test.')
    previous = [normalize(r['reference']) for r in json.loads((private / 'previous-exposures.json').read_text())]
    for i, text in enumerate(texts['test']):
        if any(near(text, old) for old in texts['eval'] + previous):
            raise ValueError('Private test repeats/approximates a public sentence.')
        if i and i % 500 == 0: print(f'Checked leakage for {i} test utterances', flush=True)
    if source_cache:
        verify(source_cache, names=list(metadata['source_files']))
        source_by_id = {r['source_id']: r for r in provenance}
        seen_source = set()
        for filename, offset, row in batches(source_cache, columns=['id', 'speaker_id', 'chapter_id', 'text'], names=list(metadata['source_files'])):
            if row['id'] not in source_by_id: continue
            expected = source_by_id[row['id']]
            if (filename, offset, str(row['speaker_id']), f"{row['speaker_id']}:{row['chapter_id']}", unicodedata.normalize('NFC', row['text'])) != (
                    expected['source_file'], expected['source_row'], expected['speaker_id'], expected['session_id'], expected['reference']):
                raise ValueError('Gold/speaker/source mapping differs from pinned upstream data.')
            seen_source.add(row['id'])
        if seen_source != set(source_by_id): raise ValueError('Some selected recordings are missing upstream.')
    return {'status': 'software_validated_human_review_pending', 'human_listening_review': 'not_performed',
        'upstream_source_verified': bool(source_cache), 'splits': report,
        'total_seconds': sum(r['seconds'] for r in report.values()),
        'speaker_overlap': 0, 'duplicate_waveforms': 0, 'cross_split_near_duplicate_texts': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--private', type=Path, required=True)
    parser.add_argument('--source-cache', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = validate(args.public, args.private, args.source_cache)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output: args.output.write_text(rendered, encoding='utf-8')
    print(rendered, end='')


if __name__ == '__main__': main()
