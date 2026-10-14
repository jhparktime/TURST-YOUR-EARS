"""Validate delivered audio, public inputs and optional private evaluation references."""
import argparse
import difflib
import json
from pathlib import Path

from scripts.baseline import load_inputs
from scripts.build_dataset import digest
from server.scoring import normalize, score, validate_manifest


def validate(root, private=None):
    import numpy as np
    import soundfile as sf
    metadata = json.loads((root/'metadata.json').read_text(encoding='utf-8'))
    if metadata['status'] != 'pilot_pending_independent_listening':
        raise ValueError('This validator does not certify a human-reviewed release.')
    all_ids, all_hashes, texts = set(), set(), {}
    report = {}
    for split in ('dev','eval'):
        folder = root/split
        rows = load_inputs(folder/'inputs.json')
        checksums = json.loads((folder/'audio-checksums.json').read_text())
        if set(checksums) != {r['id'] for r in rows}:
            raise ValueError('Audio checksums do not exactly cover the input IDs.')
        if digest(folder/'inputs.json') != metadata['splits'][split]['inputs_sha256']:
            raise ValueError('Public input manifest changed after release.')
        actual_duration = 0
        for row in rows:
            path = (folder/row['audio']).resolve()
            if path.parent != (folder/'audio').resolve() or path.suffix != '.wav':
                raise ValueError('Audio must be a WAV file within this split audio directory.')
            checksum = digest(path)
            if checksum != checksums[row['id']] or checksum in all_hashes:
                raise ValueError('Audio hash mismatch or duplicate recording across the release.')
            if row['id'] in all_ids:
                raise ValueError('Repeated public ID.')
            samples, rate = sf.read(path, dtype='float64', always_2d=True)
            if rate != 16000 or samples.shape[1] != 1 or not np.all(np.isfinite(samples)) or not np.any(samples):
                raise ValueError('Audio must be finite, nonsilent 16 kHz mono samples.')
            actual_duration += len(samples)/rate
            all_hashes.add(checksum); all_ids.add(row['id'])
        if len(rows) != metadata['splits'][split]['utterances'] or abs(actual_duration-metadata['splits'][split]['duration_seconds']) > 0.001:
            raise ValueError('Audio count/duration disagrees with metadata.')
        references = folder/'references.json' if split == 'dev' else private/'eval-references.json' if private else None
        if split == 'eval' and (folder/'references.json').exists():
            raise ValueError('Private evaluation references were included in the public split.')
        if references:
            refs = validate_manifest(json.loads(references.read_text(encoding='utf-8')))
            by_id = {r['id']:r for r in refs}
            if set(by_id) != {r['id'] for r in rows} or any(by_id[row['id']]['draft'] != row['draft'] for row in rows):
                raise ValueError('Public inputs and references disagree.')
            result = score({r['id']:r['draft'] for r in rows},refs)
            if result['cer_improvement_pp'] != 0 or result['restoration_rate'] != 0 or result['harmful_edit_rate'] != 0:
                raise ValueError('Copy control violated the correction protocol.')
            saved = json.loads((folder/'copy-draft.scores.json').read_text())
            if saved != result:
                raise ValueError('Published copy-control scores are not reproducible.')
            texts[split] = {normalize(r['reference']) for r in refs}
            report[split] = {'utterances':len(rows),'audio_seconds':round(actual_duration,2),'references_checked':True,'copy_macro_cer':result['macro_cer']}
        else:
            report[split] = {'utterances':len(rows),'audio_seconds':round(actual_duration,2),'references_checked':False}
    if private:
        provenance=json.loads((private/'provenance.json').read_text(encoding='utf-8'))
        if {r['id'] for r in provenance} != all_ids or len(provenance) != len(all_ids):
            raise ValueError('Provenance must cover every selected recording exactly once.')
        source_ids = {s:{r['source_id'] for r in provenance if r['split']==s} for s in ('dev','eval')}
        if source_ids['dev'] & source_ids['eval'] or texts['dev'] & texts['eval']:
            raise ValueError('Source sentences overlap across splits.')
        for left in texts['dev']:
            for right in texts['eval']:
                if difflib.SequenceMatcher(None,left,right,autojunk=False).ratio() >= 0.85:
                    raise ValueError('Near-duplicate reference across splits.')
        if any(r['audio_sha256'] != r['source_audio_sha256'] for r in provenance):
            raise ValueError('Original source WAV bytes were changed.')
    return {'status':'software_validated_human_review_pending','splits':report,'speaker_disjointness':metadata['speaker_disjointness']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,default=Path('datasets/tye-fleurs-ko-v1'))
    p.add_argument('--private',type=Path)
    args=p.parse_args()
    print(json.dumps(validate(args.dataset,args.private),ensure_ascii=False,indent=2))


if __name__ == '__main__':main()
