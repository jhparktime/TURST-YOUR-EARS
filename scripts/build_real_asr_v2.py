"""Build real-ASR v2 candidates from a frozen reference-blind assignment.

Never filters recordings by ASR accuracy, modifies gold, or overwrites v1.
The private output includes test gold/provenance and must not be published.
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import unicodedata
from collections import Counter
from pathlib import Path

from scripts.build_dataset import digest, write_json
from scripts.baseline import PROMPTS, SYSTEM
from scripts.prepare_real_asr_v2 import NAME, SOURCES, assignment
from server.scoring import normalize, parse_submission
from server.scoring_v2 import VERSION, aligned_slots, condition, score, validate_manifest


def ident(old):
    return hashlib.sha256(f'{NAME}:{old}'.encode()).hexdigest()[:20]


def verified_qwen(folder, split_names, expected_manifests):
    checkpoint = json.loads((folder / 'audio-only/checkpoint.json').read_text())
    contract = checkpoint['contract']
    expected = {'model':'Qwen/Qwen2.5-Omni-3B',
        'revision':'f75b40e3da2003cdd6e1829b1f420ca70797c34e',
        'mode':'audio-only', 'reference_access':False, 'seed':0,
        'system':SYSTEM, 'prompt':PROMPTS['audio-only'],
        'do_sample':False, 'max_new_tokens':512, 'row_limit':None,
        'output_postprocessing':'strip_only', 'input_manifests_sha256':expected_manifests}
    if any(contract.get(key) != value for key, value in expected.items()):
        raise ValueError('Qwen drafter contract differs from the fixed reference-blind run.')
    run = json.loads((folder / 'audio-only/run.json').read_text())
    if any(run.get(key) != value for key, value in expected.items()):
        raise ValueError('Qwen drafter has no matching completed run receipt.')
    items = checkpoint['items']
    lookup = {(row['split'], row['id']):row for row in items}
    if len(lookup) != len(items) or len(items) != run['rows']:
        raise ValueError('Duplicate or incomplete Qwen checkpoint.')
    for split in split_names:
        csv_rows = parse_submission((folder / split / 'audio-only.csv').read_bytes())
        selected = {i:r['prediction'] for (s,i),r in lookup.items() if s == split}
        if csv_rows != selected:
            raise ValueError('Qwen CSV is not identical to its saved inference output.')
    return lookup, {'checkpoint_sha256':digest(folder / 'audio-only/checkpoint.json'),
                    'run_sha256':digest(folder / 'audio-only/run.json'),
                    'contract':contract, 'rows':len(items)}


def verified_whisper(folder):
    checkpoint = json.loads((folder / 'audio-only.json').read_text())
    run = json.loads((folder / 'run.json').read_text())
    if checkpoint['model'] != 'mlx-community/whisper-large-v3-turbo' or checkpoint['revision'] != 'a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb':
        raise ValueError('Whisper drafter model/version mismatch.')
    if (run.get('reference_access') is not False or run.get('draft_access') is not False
            or run.get('decoding') != {'language':'ko','task':'transcribe','temperature':0.0,
                                      'condition_on_previous_text':False}):
        raise ValueError('Whisper drafter must have the fixed reference-blind decoding receipt.')
    rows = checkpoint['items']
    lookup = {r['id']:r for r in rows}
    if len(lookup) != len(rows):
        raise ValueError('Duplicate Whisper drafter rows.')
    csv_rows = parse_submission((folder / 'audio-only.csv').read_bytes())
    if csv_rows != {i:r['prediction'] for i,r in lookup.items()}:
        raise ValueError('Whisper CSV differs from saved inference output.')
    return lookup, {'checkpoint_sha256':digest(folder / 'audio-only.json'), 'run':run,
                    'rows':len(rows), 'model':checkpoint['model'], 'revision':checkpoint['revision']}


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def build(args):
    import soundfile as sf
    if args.public.exists() or args.private.exists():
        raise ValueError('V2 outputs must be new folders; never overwrite a release.')
    plan_path = args.plan / 'plan.json'
    if digest(plan_path) != (args.plan / 'plan.sha256').read_text().strip():
        raise ValueError('Frozen assignment plan changed.')
    plan = json.loads(plan_path.read_text())
    metadata = json.loads((args.source_public / 'metadata.json').read_text())
    if digest(args.source_public / 'metadata.json') != plan['source_metadata_sha256']:
        raise ValueError('Frozen source metadata changed.')
    old_inputs = {s:json.loads(((args.source_private if s == 'test' else args.source_public) /
                  s / 'inputs.json').read_text())['items'] for s in ('train','eval','test')}
    for split, rows in old_inputs.items():
        path = (args.source_private if split == 'test' else args.source_public) / split / 'inputs.json'
        if digest(path) != metadata['splits'][split]['inputs_sha256']:
            raise ValueError('Source input bytes changed after assignment.')
        expected_assignment = assignment(rows, split)
        planned = plan['splits'][split]['items']
        if {r['id']:r['source'] for r in planned} != expected_assignment:
            raise ValueError('Draft assignment differs from its deterministic plan.')
    qwen_old, qwen_old_receipt = verified_qwen(args.qwen_existing, ('eval','test'),
        {s:metadata['splits'][s]['inputs_sha256'] for s in ('eval','test')})
    qwen_train, qwen_train_receipt = verified_qwen(args.qwen_train, ('train',),
        {'train':digest(args.plan / 'jobs/qwen-omni/train/inputs.json')})
    whisper_old, whisper_old_receipt = verified_whisper(args.whisper_existing)
    whisper_train, whisper_train_receipt = verified_whisper(args.whisper_train)
    expected_train_qwen = {('train',r['id']) for r in plan['splits']['train']['items'] if r['source']=='qwen-omni'}
    expected_train_whisper = {r['id'] for r in plan['splits']['train']['items'] if r['source']=='whisper-turbo'}
    if set(qwen_train) != expected_train_qwen or set(whisper_train) != expected_train_whisper:
        raise ValueError('Training drafter output does not exactly match its assigned jobs.')
    if qwen_old_receipt['contract']['model_files_sha256'] != qwen_train_receipt['contract']['model_files_sha256']:
        raise ValueError('Existing and training Qwen draft weights differ.')
    expected_old = {(s,r['id']) for s in ('eval','test') for r in old_inputs[s]}
    if set(qwen_old) != expected_old or set(whisper_old) != {i for _,i in expected_old}:
        raise ValueError('Existing audio-only runs must cover all eval/test recordings.')
    # Select every draft before opening the source gold. No score-based filters.
    selected, selected_records = {}, {}
    for split, group in plan['splits'].items():
        for item in group['items']:
            source, old = item['source'], item['id']
            if source == 'qwen-omni':
                row = (qwen_train if split == 'train' else qwen_old)[(split,old)]
            else:
                row = (whisper_train if split == 'train' else whisper_old)[old]
            if row['audio_sha256'] != item['audio_sha256'] or digest(Path(item['audio'])) != item['audio_sha256']:
                raise ValueError('Drafter output refers to different input audio.')
            selected[(split,old)] = unicodedata.normalize('NFC',row['prediction'])
            selected_records[(split,old)] = row
    provenance = {r['id']:r for r in json.loads((args.source_private / 'provenance.json').read_text())}
    args.public.mkdir(parents=True)
    args.private.mkdir(parents=True, mode=0o700)
    summary, private_mapping, receipts = {}, [], {}
    for split, group in plan['splits'].items():
        source_ref = (args.source_private / 'test-references.json' if split == 'test'
                      else args.source_public / split / 'references.json')
        if digest(source_ref) != metadata['splits'][split]['references_sha256']:
            raise ValueError('Source reference bytes changed.')
        refs = {r['id']:r for r in json.loads(source_ref.read_text())['items']}
        if set(refs) != {r['id'] for r in group['items']}:
            raise ValueError('Source references do not match the frozen assignment IDs.')
        destination = (args.private if split == 'test' else args.public) / split
        (destination / 'audio').mkdir(parents=True)
        inputs, references, audio_hashes, review = [], [], {}, []
        duration, speakers, diagnostics = 0.0, set(), Counter()
        for item in group['items']:
            old, source = item['id'], item['source']
            new, draft = ident(old), selected[(split,old)]
            reference = refs[old]['reference']
            out = destination / 'audio' / f'{new}.wav'
            shutil.copyfile(item['audio'],out)
            if digest(out) != item['audio_sha256']:
                raise ValueError('Copied audio bytes differ from source.')
            info = sf.info(out)
            if info.samplerate != 16000 or info.channels != 1:
                raise ValueError('Expected original 16 kHz mono recording.')
            duration += info.frames / info.samplerate
            speakers.add(provenance[old]['speaker_id'])
            inputs.append({'id':new,'audio':f'audio/{new}.wav','draft':draft})
            references.append({'id':new,'reference':reference,'draft':draft,'source':source})
            audio_hashes[new] = item['audio_sha256']
            aligned = aligned_slots(normalize(reference),normalize(draft))
            numeric_flag = any(c.isdigit() and not ('\uac00' <= c <= '\ud7a3') for c in draft) and not any(c.isdigit() for c in reference)
            diagnostics['empty_drafts'] += not draft.strip()
            diagnostics['length_limited_drafts'] += bool(selected_records[(split,old)].get('at_token_limit', False))
            diagnostics['numeric_notation_review_flags'] += numeric_flag
            review.append({'id':new,'audio':f'audio/{new}.wav','source':source,
                'reference':reference,'draft':draft,'error_type':condition(aligned),
                'draft_cer':100*aligned['errors']/len(normalize(reference)),
                **{k:aligned[k] for k in ('substitutions','deletions','insertions')},
                'numeric_notation_review_flag':bool(numeric_flag),
                'review_status':'not_reviewed','reviewer':'','heard_text_before_reveal':'',
                'verdict':'','audio_required':'','notes':''})
            private_mapping.append({'id':new,'v1_id':old,'split':split,'source':source,
                'speaker_id':provenance[old]['speaker_id'],
                'session_id':provenance[old]['session_id'],'audio_sha256':item['audio_sha256']})
        input_manifest = {'name':f'{NAME}-{split}','protocol':VERSION,'items':inputs}
        ref_manifest = {'name':f'{NAME}-{split}','protocol':VERSION,'items':references}
        validate_manifest(ref_manifest)
        metrics = score({r['id']:r['draft'] for r in references},references)
        write_json(destination / 'inputs.json',input_manifest)
        ref_path = args.private / 'test-references.json' if split == 'test' else destination / 'references.json'
        write_json(ref_path,ref_manifest)
        write_json(destination / 'audio-checksums.json',audio_hashes)
        write_csv(destination / 'copy-draft.csv',[{'id':r['id'],'prediction':r['draft']} for r in inputs])
        write_json(destination / 'copy-draft.scores.json',metrics)
        # All test answers and error labels stay outside the test-input packet.
        review_path = args.private / 'test-listening-review.csv' if split == 'test' else destination / 'listening-review.csv'
        write_csv(review_path,review)
        summary[split] = {'visibility':'private' if split == 'test' else 'public',
            'utterances':len(inputs),'duration_seconds':duration,'speakers':len(speakers),
            'sources':dict(Counter(r['source'] for r in references)),
            'conditions':{k:v['utterances'] for k,v in metrics['conditions'].items()},
            'draft_micro_cer':metrics['micro_cer'],'draft_macro_utterance_cer':metrics['macro_cer'],
            'draft_errors':metrics['counts'],'diagnostics':dict(diagnostics),
            'inputs_sha256':digest(destination / 'inputs.json'),'references_sha256':digest(ref_path)}
        receipts[split] = {'copy':metrics}
        # Frozen existing audio-only outputs are valid on exactly the same WAVs.
        if split != 'train':
            for name, lookup in [('Whisper audio-only',whisper_old),('Qwen audio-only',qwen_old)]:
                predictions = {ident(r['id']):(lookup[r['id']] if name.startswith('Whisper') else lookup[(split,r['id'])])['prediction']
                               for r in group['items']}
                write_csv(destination / (name.split()[0].lower()+'-audio-only.csv'),
                    [{'id':i,'prediction':value} for i,value in predictions.items()])
                receipts[split][name] = score(predictions,references)
    new_metadata = {'name':NAME,'protocol':VERSION,'primary_metric':'micro_cer',
        'status':'constructed',
        'source':metadata['source'],'source_revision':metadata['source_revision'],'license':metadata['license'],
        'assignment_plan_sha256':digest(plan_path),'selection_used_asr_scores':False,
        'source_models':plan['sources'],'splits':summary,
        'reference_policy':'Unchanged upstream reference; NFC normalization only.',
        'draft_policy':'Actual fixed audio-only output, NFC only; one draft per recording; no filtering by errors.',
        'limitations':['Public read speech; not spontaneous conversation.',
            'V1 test aggregate scores were known during design; not a new fully blind source holdout.',
            'Drafters are also measured as audio-only baselines; source-stratified self-generator effects must be shown.',
            'Numeric spelling and source transcription conventions may affect CER.',
            'Real ASR errors do not by themselves establish novelty or acoustic necessity.']}
    write_json(args.public / 'metadata.json',new_metadata)
    write_json(args.private / 'metadata.json',new_metadata)
    write_json(args.private / 'source-mapping.json',private_mapping)
    write_json(args.private / 'baseline-reuse.json',receipts)
    write_json(args.private / 'drafter-provenance.json',{'plan_sha256':digest(plan_path),
        'qwen_existing':qwen_old_receipt,'qwen_train':qwen_train_receipt,
        'whisper_existing':whisper_old_receipt,'whisper_train':whisper_train_receipt})
    notice = (args.source_public / 'NOTICE').read_text()
    for root in (args.public,args.private):
        (root / 'NOTICE').write_text(notice + '\nV2: actual ASR drafts and independently versioned alignment-based metrics.\n')
        (root / 'README.md').write_text(f'# {NAME}\n\nKorean audio-grounded transcript correction dataset.\n'
            'See metadata.json and the repository docs/real-asr-v2.md for rules and limitations.\n'
            'V1 and V2 scores are not comparable. Protocol: ko-correction-v2. Primary: Micro CER.\n')
    for path in args.private.rglob('*'):
        os.chmod(path,0o700 if path.is_dir() else 0o600)
    print(json.dumps({'dataset':NAME,'status':new_metadata['status'],
                      'splits':summary,'private_rows_published':False},ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan','source-public','source-private','qwen-existing','qwen-train',
                 'whisper-existing','whisper-train','public','private'):
        parser.add_argument('--'+name,type=Path,required=True)
    build(parser.parse_args())
