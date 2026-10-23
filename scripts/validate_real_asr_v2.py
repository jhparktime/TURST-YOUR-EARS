"""Independently verify v2 candidate files against original recordings and runs.

This is an integrity/dataset-construction check, not a listening-quality audit.
It never certifies that upstream reference text matches what was spoken.
"""
import argparse
import csv
import json
import unicodedata
from collections import Counter
from pathlib import Path

from scripts.build_dataset import digest, write_json
from scripts.prepare_real_asr_v2 import assignment
from server.scoring import normalize, parse_submission
from server.scoring_v2 import score, validate_manifest


def validate(args):
    import soundfile as sf
    metadata = json.loads((args.public / 'metadata.json').read_text())
    old_metadata = json.loads((args.source_public / 'metadata.json').read_text())
    mapping_rows = json.loads((args.private / 'source-mapping.json').read_text())
    mapping = {r['id']:r for r in mapping_rows}
    assert len(mapping) == len(mapping_rows) == 2631, 'Mapping coverage/collision'
    source_prov = {r['id']:r for r in json.loads((args.source_private / 'provenance.json').read_text())}
    asr_old = json.loads((args.whisper_existing / 'audio-only.json').read_text())['items']
    asr_train = json.loads((args.whisper_train / 'audio-only.json').read_text())['items']
    whisper = {r['id']:r for r in asr_old + asr_train}
    qwen_rows = (json.loads((args.qwen_existing / 'audio-only/checkpoint.json').read_text())['items'] +
                 json.loads((args.qwen_train / 'audio-only/checkpoint.json').read_text())['items'])
    qwen = {(r['split'],r['id']):r for r in qwen_rows}
    speakers, sessions, texts, audios, results, active_ids = {}, {}, {}, {}, {}, set()
    for split, target_seconds in [('train',4395.9708125),('eval',3600),('test',14400)]:
        root = (args.private if split == 'test' else args.public) / split
        old_root = (args.source_private if split == 'test' else args.source_public) / split
        old_input_path = old_root / 'inputs.json'
        assert digest(old_input_path) == old_metadata['splits'][split]['inputs_sha256']
        old_inputs = json.loads(old_input_path.read_text())['items']
        assigned = assignment(old_inputs,split)
        old_ref_path = args.source_private / 'test-references.json' if split == 'test' else old_root / 'references.json'
        assert digest(old_ref_path) == old_metadata['splits'][split]['references_sha256']
        old_refs = {r['id']:r for r in json.loads(old_ref_path.read_text())['items']}
        input_manifest = json.loads((root / 'inputs.json').read_text())
        assert input_manifest['protocol'] == 'ko-correction-v2'
        inputs = input_manifest['items']
        ref_path = args.private / 'test-references.json' if split == 'test' else root / 'references.json'
        refs = validate_manifest(json.loads(ref_path.read_text()))
        refs_by_id = {r['id']:r for r in refs}
        assert len(refs_by_id) == len(inputs) == old_metadata['splits'][split]['utterances']
        checksums = json.loads((root / 'audio-checksums.json').read_text())
        seconds = 0.0
        speakers[split], sessions[split], texts[split], audios[split] = set(), set(), set(), set()
        old_seen = set()
        for row in inputs:
            assert set(row) == {'id','audio','draft'}, 'Reference/type/source label in model input'
            new = row['id']
            assert new not in active_ids, 'Duplicate cross-split ID'
            active_ids.add(new)
            link, ref = mapping[new], refs_by_id[new]
            old = link['v1_id']
            assert link['split'] == split and old not in old_seen
            old_seen.add(old)
            assert link['source'] == ref['source'] == assigned[old]
            original = source_prov[old]
            assert ref['reference'] == old_refs[old]['reference'] == original['reference']
            record = qwen[(split,old)] if ref['source'] == 'qwen-omni' else whisper[old]
            assert ref['draft'] == row['draft'] == unicodedata.normalize('NFC',record['prediction'])
            wav = (root / row['audio']).resolve()
            assert wav.parent == (root / 'audio').resolve(), 'Audio escaped split directory'
            assert digest(wav) == checksums[new] == record['audio_sha256'] == original['audio_sha256']
            samples, rate = sf.read(wav,dtype='float32')
            assert rate == 16000 and samples.ndim == 1 and len(samples) > 0
            assert bool(((samples >= -1) & (samples <= 1)).all()), 'Invalid/nonfinite audio'
            seconds += len(samples)/rate
            speakers[split].add(original['speaker_id'])
            sessions[split].add(original['session_id'])
            texts[split].add(normalize(ref['reference']))
            audios[split].add(checksums[new])
        assert old_seen == set(old_refs), 'Dropped or added recordings'
        assert abs(seconds-target_seconds) < 2, 'Duration target changed'
        assert abs(seconds-metadata['splits'][split]['duration_seconds']) < 1e-6
        assert digest(root / 'inputs.json') == metadata['splits'][split]['inputs_sha256']
        assert digest(ref_path) == metadata['splits'][split]['references_sha256']
        copied = parse_submission((root / 'copy-draft.csv').read_bytes())
        assert copied == {r['id']:r['draft'] for r in inputs}
        fresh = score(copied,refs)
        assert fresh == json.loads((root / 'copy-draft.scores.json').read_text())
        assert fresh['harmful_edit_rate'] == fresh['unwanted_insertion_rate'] == 0
        assert fresh['slot_restoration_rate'] == 0 and fresh['cer_improvement_pp'] == 0
        gold = score({r['id']:r['reference'] for r in refs},refs)
        assert gold['micro_cer'] == gold['harmful_edit_rate'] == gold['unwanted_insertion_rate'] == 0
        assert gold['slot_restoration_rate'] == 100
        assert not any('test' in str(p.relative_to(args.public)).lower() for p in args.public.rglob('*'))
        results[split] = {'utterances':len(inputs),'duration_seconds':seconds,
            'sources':dict(Counter(r['source'] for r in refs)),
            'conditions':{k:v['utterances'] for k,v in fresh['conditions'].items()},
            'draft_micro_cer':fresh['micro_cer'],'copy_invariants':'passed','gold_invariants':'passed'}
    for left,right in [('train','eval'),('train','test'),('eval','test')]:
        for label,groups in [('speakers',speakers),('sessions',sessions),('normalized_text',texts),('audio',audios)]:
            assert not groups[left] & groups[right], f'Cross-split {label} overlap'
    result = {'dataset':metadata['name'],'protocol':metadata['protocol'],'state':'integrity_verified',
        'active_recordings':len(active_ids),'source_recordings_dropped':0,'splits':results,
        'cross_split_speaker_session_exact_text_audio_disjoint':True,
        'near_text_check':'Inherited unchanged references and split from frozen merged-v1; not a new independent near-text audit.',
        'drafts_match_actual_audio_only_outputs':True,'upstream_reference_text_unchanged':True,
        'reference_verification':metadata.get('reference_verification',{}),'source_metadata_sha256':digest(args.source_public / 'metadata.json'),
        'metadata_sha256':digest(args.public / 'metadata.json'),
        'validator_source_sha256':digest(Path(__file__))}
    write_json(args.output,result)
    print(json.dumps(result,ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('public','private','source-public','source-private','whisper-existing','whisper-train',
                 'qwen-existing','qwen-train','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    validate(parser.parse_args())
