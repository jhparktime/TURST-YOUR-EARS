"""Re-open and independently validate a merged train/eval/test delivery."""
import argparse
import hashlib
import json
from collections import Counter
from itertools import combinations
from pathlib import Path

from scripts.baseline import load_inputs
from scripts.build_dataset import digest
from scripts.merge_correction_datasets import near
from server.scoring import normalize, parse_submission, score, validate_manifest


def validate(public, private):
    import numpy as np
    import soundfile as sf

    metadata = json.loads((public / 'metadata.json').read_text())
    assert metadata == json.loads((private / 'metadata.json').read_text())
    assert metadata['selection_used_asr_predictions'] is False
    for root in (public, private):
        actual = {str(p.relative_to(root)): digest(p) for p in root.rglob('*')
                  if p.is_file() and p.name != 'release-lock.json'}
        assert actual == json.loads((root / 'release-lock.json').read_text())['sha256'], 'Incomplete release lock'
    assert not (public / 'test').exists()
    assert not any('source-pool' in str(p) or 'test-references' in p.name or 'provenance' in p.name
                   for p in public.rglob('*'))
    pool = json.loads((private / 'source-pool.json').read_text())
    origins = {r['source_id']: r for r in pool}
    assert len(origins) == len(pool) == metadata['pool']['recordings']
    assert len({r['pcm_sha256'] for r in pool}) == len(pool)
    assert sum(r['samples'] for r in pool) / 16000 == metadata['pool']['seconds']
    for i, r in enumerate(pool):
        path = private / r['audio']
        assert digest(path) == r['audio_sha256']
        info = sf.info(path)
        pcm, rate = sf.read(path, dtype='int16', always_2d=True)
        assert rate == 16000 and info.subtype == 'PCM_16' and pcm.shape == (r['samples'], 1)
        assert np.any(pcm)
        assert hashlib.sha256(pcm.astype('<i2').tobytes()).hexdigest() == r['pcm_sha256']
        if (i + 1) % 1000 == 0:
            print(f'Independently decoded {i + 1}/{len(pool)} pool recordings', flush=True)
    provenance = json.loads((private / 'provenance.json').read_text())
    by_id = {r['id']: r for r in provenance}
    assert len(by_id) == len(provenance)
    collected, sets, texts, report = set(), {}, {}, {}
    for split in ('train', 'eval', 'test'):
        folder = (private if split == 'test' else public) / split
        refpath = private / 'test-references.json' if split == 'test' else folder / 'references.json'
        refs = validate_manifest(json.loads(refpath.read_text()))
        inputs = load_inputs(folder / 'inputs.json')
        refmap = {r['id']: r for r in refs}
        checksums = json.loads((folder / 'audio-checksums.json').read_text())
        ids = {r['id'] for r in inputs}
        assert ids == set(refmap) == set(checksums)
        assert not collected & ids
        collected |= ids
        assert {p.name for p in (folder / 'audio').iterdir()} == {f'{i}.wav' for i in ids}
        part = [by_id[i] for i in ids]
        for row in inputs:
            r = by_id[row['id']]; ref = refmap[row['id']]; origin = origins[r['source_id']]
            assert r['split'] == split and r['origin_id'] == origin['origin_id']
            assert ref['reference'] == r['reference'] == origin['reference']
            assert row['draft'] == ref['draft'] == r['draft']
            assert row['audio'] == f"audio/{row['id']}.wav"
            assert r['condition'] == ref['condition']
            assert len(ref['edits']) == {'clean': 0, 'single': 1, 'multiple': 2}[ref['condition']]
            assert digest(folder / row['audio']) == checksums[row['id']] == origin['audio_sha256']
        expected = metadata['splits'][split]
        counts = dict(Counter(r['condition'] for r in refs))
        assert len(refs) == expected['utterances'] and counts == expected['conditions']
        seconds = sum(r['samples'] for r in part) / 16000
        assert seconds == expected['duration_seconds']
        assert digest(folder / 'inputs.json') == expected['inputs_sha256']
        assert digest(refpath) == expected['references_sha256']
        if split != 'train':
            assert max(counts.values()) - min(counts.values()) <= 1
            assert abs(seconds - metadata['target_duration_seconds'][split]) <= .3
        copied = parse_submission((folder / 'copy-draft.csv').read_bytes())
        assert copied == {r['id']: r['draft'] for r in inputs}
        result = score(copied, refs)
        assert result == json.loads((folder / 'copy-draft.scores.json').read_text())
        assert result['restoration_rate'] == result['harmful_edit_rate'] == 0
        oracle = score({r['id']: r['reference'] for r in refs}, refs)
        assert oracle['macro_cer'] == 0 and oracle['restoration_rate'] == 100
        sets[split] = {field: {r[field] for r in part} for field in
                       ('source_id', 'speaker_id', 'session_id', 'pcm_sha256')}
        texts[split] = {normalize(r['reference']) for r in refs}
        assert len(texts[split]) == len(refs)
        report[split] = {'recordings': len(refs), 'seconds': seconds,
                         'speakers': len(sets[split]['speaker_id']), 'copy_macro_cer': result['macro_cer']}
    assert collected == set(by_id)
    for a, b in combinations(('train', 'eval', 'test'), 2):
        for field in sets[a]:
            assert not sets[a][field] & sets[b][field], (a, b, field)
        assert not texts[a] & texts[b]
        for text in texts[a]:
            assert not any(near(text, other) for other in texts[b]), (a, b, 'near sentence')
        print(f'Cross-split speaker, session, PCM and near-sentence checks: {a}/{b} pass', flush=True)
    exposed = json.loads((private / 'previous-exposures.json').read_text())
    exposed += [r for r in pool if (r['origin'], r['origin_split']) in
                {('five-hour', 'eval'), ('incoming', 'train')}]
    exposed_texts = {normalize(r['reference']) for r in exposed}
    exposed_speakers = {r['speaker_id'] for r in pool if (r['origin'], r['origin_split']) in
                        {('five-hour', 'eval'), ('incoming', 'train')}}
    assert not sets['test']['speaker_id'] & exposed_speakers
    for text in texts['test']:
        assert not any(near(text, old) for old in exposed_texts), 'Previously exposed private-test text'
    reserved = json.loads((private / 'reserved.json').read_text())
    used = {r['source_id'] for r in provenance}; excluded = {r['source_id'] for r in reserved}
    assert len(excluded) == len(reserved) == metadata['reserved']['recordings']
    assert not used & excluded and used | excluded == set(origins), 'Lost or double-assigned pool recordings'
    return {'name': metadata['name'], 'status': 'software_validated_human_review_pending',
        'pool_recordings_decoded': len(pool), 'active_recordings': len(used), 'reserved_recordings': len(excluded),
        'cross_split_speaker_session_text_pcm_overlap': 0, 'cross_split_near_sentences': 0,
        'private_test_previously_exposed_sentences': 0, 'human_listening_review': 'not_performed',
        'splits': report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--private', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.public, args.private)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
