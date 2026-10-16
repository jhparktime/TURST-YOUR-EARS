"""Verify complete reference-blind v2 runs, then calculate all ten measurements.

Individual private predictions never enter the public aggregate comparison.
This command does not publish files or mix v1 scores with v2.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.baseline import PROMPTS, SYSTEM, load_inputs
from scripts.build_dataset import digest, write_json
from scripts.run_omni_baselines import MODEL, REVISION
from server.scoring import parse_submission
from server.scoring_v2 import score, validate_manifest


def complete_mode(omni, public, private, mode):
    checkpoint_path = omni / mode / 'checkpoint.json'
    checkpoint = json.loads(checkpoint_path.read_text())
    contract = checkpoint['contract']
    expected = {'model':MODEL,'revision':REVISION,'mode':mode,'prompt':PROMPTS[mode],
                'system':SYSTEM,'seed':0,'reference_access':False,'row_limit':None,
                'do_sample':False,'max_new_tokens':512,'output_postprocessing':'strip_only',
                'splits':['eval','test'],'input_manifests_sha256':{
                    'eval':digest(public / 'eval/inputs.json'),'test':digest(private / 'test/inputs.json')}}
    if any(contract.get(key) != value for key,value in expected.items()):
        raise ValueError('V2 baseline contract differs from frozen inputs/settings.')
    run_path = omni / mode / 'run.json'
    run = json.loads(run_path.read_text())
    if any(run.get(key) != value for key,value in expected.items()):
        raise ValueError('No matching completed v2 baseline run.')
    records = {(r['split'],r['id']):r for r in checkpoint['items']}
    if len(records) != len(checkpoint['items']) or len(records) != run['rows']:
        raise ValueError('Duplicate/incomplete v2 prediction checkpoint.')
    expected_ids, splits = set(), {}
    for split, root in [('eval',public),('test',private)]:
        path = root / split / 'inputs.json'
        rows = load_inputs(path)
        csv_path = omni / split / f'{mode}.csv'
        predictions = parse_submission(csv_path.read_bytes())
        if set(predictions) != {r['id'] for r in rows}:
            raise ValueError('Require complete v2 CSV ID coverage.')
        for row in rows:
            key = split,row['id']
            expected_ids.add(key)
            record = records[key]
            if record['prediction'] != predictions[row['id']]:
                raise ValueError('V2 CSV differs from actual model output.')
            if record['draft_sha256'] != hashlib.sha256(row['draft'].encode()).hexdigest():
                raise ValueError('V2 prediction was generated from another draft.')
            expected_audio = digest(path.parent / row['audio']) if mode == 'audio-draft' else None
            if record['audio_sha256'] != expected_audio:
                raise ValueError('V2 prediction was generated from another audio input.')
        splits[split] = predictions
    if set(records) != expected_ids:
        raise ValueError('Unexpected v2 checkpoint IDs/splits.')
    return splits, {'checkpoint_sha256':digest(checkpoint_path),'run_sha256':digest(run_path),
        'contract':contract,'rows':len(records),'output_diagnostics_by_split':run['output_diagnostics_by_split']}


def build(public, private, work):
    omni = work / 'omni'
    verified = {mode:complete_mode(omni,public,private,mode) for mode in ('text-only','audio-draft')}
    entries = []
    for split,root in [('eval',public),('test',private)]:
        ref_path = private / 'test-references.json' if split == 'test' else public / 'eval/references.json'
        refs = validate_manifest(json.loads(ref_path.read_text()))
        for name,file in [('Copy draft','copy-draft.csv'),('Whisper audio-only','whisper-audio-only.csv'),
                          ('Qwen audio-only','qwen-audio-only.csv')]:
            predictions = parse_submission((root / split / file).read_bytes())
            metrics = score(predictions,refs)
            entries.append({'baseline':name,'split':split,'metrics':metrics})
        for mode,name in [('text-only','Qwen text-only'),('audio-draft','Qwen audio+draft')]:
            predictions,_ = verified[mode]
            metrics = score(predictions[split],refs)
            write_json(omni / split / f'{mode}.scores.json',metrics)
            entries.append({'baseline':name,'split':split,'metrics':metrics})
    result = {'dataset':'tye-ko-asr-v2','protocol':'ko-correction-v2','primary_metric':'micro_cer',
        'status':'complete_measurements_pending_human_listening', 'entries':entries,'pending':[],
        'verification':{mode:proof for mode,(_,proof) in verified.items()},
        'private_row_export':False,
        'limitations':['Source-stratified self-generator overlap must be reported.',
            'No independent listening; source transcript/numeric notation may affect scores.',
            'New real-ASR drafts are not evidence that audio is necessary on every example.']}
    write_json(work / 'comparison.json',result)
    print(json.dumps({'measurements':len(entries),'pending':0,'dataset':result['dataset']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public',type=Path,required=True)
    parser.add_argument('--private',type=Path,required=True)
    parser.add_argument('--work',type=Path,required=True)
    args = parser.parse_args()
    build(args.public,args.private,args.work)
