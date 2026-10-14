"""Validate delivered audio, public inputs and optional private evaluation references."""
import argparse
import difflib
import json
import unicodedata
from collections import Counter
from pathlib import Path

from scripts.baseline import load_inputs
from scripts.build_dataset import digest, fetch, load_pairs
from server.scoring import alignment, corruption, normalize, score, validate_manifest


def validate(root, private=None, source_cache=None):
    import numpy as np
    import soundfile as sf
    metadata = json.loads((root/'metadata.json').read_text(encoding='utf-8'))
    final = metadata['status'] == 'frozen_automatic_crosscheck'
    if metadata['status'] not in {'pilot_pending_independent_listening','frozen_automatic_crosscheck'}:
        raise ValueError('Unknown release status; human listening is not certified by this validator.')
    if final:
        lock = json.loads((root/'release-lock.json').read_text())
        actual = {str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file() and p.name!='release-lock.json'}
        if actual != lock['sha256']:
            raise ValueError('Frozen public release files changed, were added, or are missing.')
        quality = json.loads((root/'quality-report.json').read_text())
        if quality['human_listening_review'] != 'not_performed' or quality['draft_access'] or quality['reference_access']:
            raise ValueError('QA must remain blind and must not claim human listening.')
    all_ids, all_hashes, texts = set(), set(), {}
    all_references, frames = {}, {}
    report = {}
    for split in ('dev','eval'):
        folder = root/split
        rows = load_inputs(folder/'inputs.json')
        checksums = json.loads((folder/'audio-checksums.json').read_text())
        if set(checksums) != {r['id'] for r in rows}:
            raise ValueError('Audio checksums do not exactly cover the input IDs.')
        if {p.name for p in (folder/'audio').iterdir()} != {f"{r['id']}.wav" for r in rows}:
            raise ValueError('Audio directory must exactly cover public input IDs.')
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
            frames[row['id']]=len(samples)
            all_hashes.add(checksum); all_ids.add(row['id'])
        if len(rows) != metadata['splits'][split]['utterances'] or abs(actual_duration-metadata['splits'][split]['duration_seconds']) > 0.001:
            raise ValueError('Audio count/duration disagrees with metadata.')
        references = folder/'references.json' if split == 'dev' else private/'eval-references.json' if private else None
        if split == 'eval' and (folder/'references.json').exists():
            raise ValueError('Private evaluation references were included in the public split.')
        if references:
            refs = validate_manifest(json.loads(references.read_text(encoding='utf-8')))
            by_id = {r['id']:r for r in refs}
            all_references.update(by_id)
            if set(by_id) != {r['id'] for r in rows} or any(by_id[row['id']]['draft'] != row['draft'] for row in rows):
                raise ValueError('Public inputs and references disagree.')
            if dict(Counter(r['condition'] for r in refs)) != metadata['splits'][split]['conditions']:
                raise ValueError('Condition counts disagree with metadata.')
            if final and (len({sum(r['condition']==c for r in refs) for c in ('clean','single','multiple')}) != 1
                    or any(len(r['edits']) != {'clean':0,'single':1,'multiple':2}[r['condition']] for r in refs)):
                raise ValueError('Frozen release must balance exact 0/1/2-error conditions.')
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
        if any(r['reference'] != all_references[r['id']]['reference'] or r['samples'] != frames[r['id']] for r in provenance):
            raise ValueError('Scored gold/audio frames disagree with source provenance.')
        if final:
            from scripts.build_final_dataset import MAX_QA_CER, supported_edits
            mapping=load_pairs(root/'substitutions.json')
            if digest(private/'eval-references.json') != metadata['evaluation_references_sha256']:
                raise ValueError('Frozen private evaluation references changed.')
            for split in ('dev','eval'):
                selected = [r for r in provenance if r['split']==split]
                if any((r['source_split']=='train') != (split=='dev') for r in selected):
                    raise ValueError('Speaker separation requires source train vs dev/test.')
                qa = json.loads((private/f'{split}-qa.json').read_text())
                if (qa['model'],qa['revision']) != (quality['model'],quality['revision']):
                    raise ValueError('Private QA model disagrees with the quality report.')
                by_id = {r['id']:r for r in qa['items']}
                if len(by_id) != len(qa['items']) or set(by_id) != {r['id'] for r in selected}:
                    raise ValueError('Private QA must exactly cover release IDs.')
                for row in selected:
                    prediction=by_id[row['id']]
                    cer,options=supported_edits(row['reference'],prediction['prediction'],mapping)
                    if prediction['audio_sha256'] != row['audio_sha256'] or cer>MAX_QA_CER or len(options)<2:
                        raise ValueError('Blind ASR failed the candidate quality/span gate.')
                    aligned,_,_=alignment(normalize(row['reference']),normalize(prediction['prediction']))
                    for start,end in corruption(all_references[row['id']]):
                        if ''.join(aligned[start:end]) != normalize(row['reference'])[start:end]:
                            raise ValueError('An injected target was not corroborated by blind ASR.')
            previous=json.loads((private/'previous-release-exclusions.json').read_text())
            previous_ids={r['source_id'] for r in previous}
            previous_hashes={r['audio_sha256'] for r in previous}
            previous_text=[normalize(r['reference']) for r in previous]
            for row in (r for r in provenance if r['split']=='eval'):
                if row['source_id'] in previous_ids or row['audio_sha256'] in previous_hashes or any(
                        difflib.SequenceMatcher(None,normalize(row['reference']),t,autojunk=False).ratio()>=0.85 for t in previous_text):
                    raise ValueError('Final evaluation repeats a previously released sentence/recording.')
            if source_cache:
                source = {}
                for partition in ('train','dev','test'):
                    path = fetch(source_cache,partition)
                    source[partition] = {r[1]:r for r in (line.split('\t') for line in path.read_text().splitlines())}
                for row in provenance:
                    raw = source[row['source_split']][row['source_filename']]
                    if raw[0] != row['source_id'] or unicodedata.normalize('NFC',raw[3]) != row['reference'] or int(raw[5]) != row['samples']:
                        raise ValueError('Final gold/source provenance differs from pinned upstream TSV.')
    return {'status':'frozen_release_validated' if final else 'software_validated_human_review_pending',
            'private_qa_checked':bool(final and private), 'upstream_labels_checked':bool(final and private and source_cache),
            'human_listening_review':'not_performed','splits':report,'speaker_disjointness':metadata['speaker_disjointness']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,default=Path('datasets/tye-ko-v2'))
    p.add_argument('--private',type=Path)
    p.add_argument('--source-cache',type=Path)
    args=p.parse_args()
    print(json.dumps(validate(args.dataset,args.private,args.source_cache),ensure_ascii=False,indent=2))


if __name__ == '__main__':main()
