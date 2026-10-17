"""Verify public-only stress predictions and compare all paired conditions."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from scripts.baseline import PROMPTS, SYSTEM, load_inputs
from scripts.build_dataset import digest, write_json
from scripts.run_omni_baselines import MODEL, REVISION
from scripts.transcribe_audio import MODEL as WHISPER_MODEL, REVISION as WHISPER_REVISION
from server.scoring import parse_submission
from server.scoring_v2 import score, validate_manifest

LABELS=('Copy draft','Whisper audio-only','Qwen audio-only','Qwen text-only','Qwen audio+draft')
CONDITIONS=('original','gaussian_5db','packet_loss_20')


def new_qwen(probe,work,mode,original_contract):
    inputs=probe/'inference/eval/inputs.json';rows=load_inputs(inputs)
    checkpoint=work/'omni'/mode/'checkpoint.json';runpath=work/'omni'/mode/'run.json'
    saved=json.loads(checkpoint.read_text());run=json.loads(runpath.read_text())
    expected={'model':MODEL,'revision':REVISION,'mode':mode,'prompt':PROMPTS[mode],'system':SYSTEM,
        'seed':0,'do_sample':False,'max_new_tokens':512,'row_limit':None,'reference_access':False,
        'splits':['eval'],'input_manifests_sha256':{'eval':digest(inputs)},
        'device':'mps','dtype':'torch.bfloat16','attention':'sdpa','output_postprocessing':'strip_only',
        'model_files_sha256':original_contract['model_files_sha256'],
        'packages':original_contract['packages']}
    assert all(saved['contract'].get(k)==v and run.get(k)==v for k,v in expected.items())
    records={r['id']:r for r in saved['items']}
    csvpath=work/'omni/eval'/(mode+'.csv');predictions=parse_submission(csvpath.read_bytes())
    assert len(records)==len(saved['items'])==run['rows']==len(rows)
    assert set(records)==set(predictions)=={r['id'] for r in rows}
    for row in rows:
        record=records[row['id']]
        assert record['split']=='eval' and record['prediction']==predictions[row['id']]
        assert record['audio_sha256']==digest((inputs.parent/row['audio']).resolve())
        assert record['draft_sha256']==(hashlib.sha256(row['draft'].encode()).hexdigest() if mode=='audio-draft' else None)
        assert record['at_token_limit']==(record['new_tokens']>=512)
        assert record['empty_output']==(not record['prediction'])
    return predictions,{'checkpoint_sha256':digest(checkpoint),'run_sha256':digest(runpath),
        'predictions_sha256':digest(csvpath),'rows':len(rows),
        'output_diagnostics':run['output_diagnostics_by_split']['eval']}


def new_whisper(probe,work):
    checkpoint=work/'whisper/audio-only.json';runpath=work/'whisper/run.json'
    saved=json.loads(checkpoint.read_text());run=json.loads(runpath.read_text())
    assert saved['model']==run['model']==WHISPER_MODEL and saved['revision']==run['revision']==WHISPER_REVISION
    assert run['inputs_sha256']==digest(work/'blind-audio-inputs.json')
    assert run['draft_access'] is False and run['reference_access'] is False and run['prompt'] is None
    assert run['decoding']=={'language':'ko','task':'transcribe','temperature':0.0,'condition_on_previous_text':False}
    records={r['id']:r for r in saved['items']}
    csvpath=work/'whisper/audio-only.csv';predictions=parse_submission(csvpath.read_bytes())
    inputs=probe/'inference/eval/inputs.json';rows=load_inputs(inputs)
    assert len(saved['items'])==len(records)==len(rows)
    assert set(records)==set(predictions)=={r['id'] for r in rows}
    for row in rows:
        assert records[row['id']]['audio_sha256']==digest((inputs.parent/row['audio']).resolve())
        assert records[row['id']]['prediction']==predictions[row['id']]
    return predictions,{'checkpoint_sha256':digest(checkpoint),'run_sha256':digest(runpath),
        'predictions_sha256':digest(csvpath),'rows':len(rows)}


def build(public,base_results,probe,work):
    metadata=json.loads((probe/'metadata.json').read_text())
    validation=json.loads((probe/'validation.json').read_text())
    assert validation['metadata_sha256']==digest(probe/'metadata.json')
    assert validation['derived_audio_rows']==1227 and validation['private_test_used'] is False
    original=json.loads((base_results/'comparison.json').read_text())
    assert original['dataset']=='tye-ko-asr-v2' and len(original['entries'])==10 and not original['pending']
    reuse=original['public_eval_reuse']
    assert reuse['inputs_sha256']==digest(public/'eval/inputs.json')==metadata['source_inputs_sha256']
    assert reuse['references_sha256']==digest(public/'eval/references.json')==metadata['source_references_sha256']
    files={label:public/'eval'/file for label,file in [('Copy draft','copy-draft.csv'),
        ('Whisper audio-only','whisper-audio-only.csv'),('Qwen audio-only','qwen-audio-only.csv')]}
    files.update({label:base_results/'omni/eval'/(mode+'.csv') for mode,label in [
        ('text-only','Qwen text-only'),('audio-draft','Qwen audio+draft')]})
    original_refs=validate_manifest(json.loads((public/'eval/references.json').read_text()))
    original_metrics={r['baseline']:r['metrics'] for r in original['entries'] if r['split']=='eval'}
    old={}
    for label,path in files.items():
        assert digest(path)==reuse['predictions_sha256'][label]
        old[label]=parse_submission(path.read_bytes())
        assert score(old[label],original_refs)==original_metrics[label]
    qwen_contract=original['verification']['text-only']['contract']
    fresh={};proof={}
    for mode,label in [('audio-only','Qwen audio-only'),('audio-draft','Qwen audio+draft')]:
        fresh[label],proof[label]=new_qwen(probe,work,mode,qwen_contract)
    fresh['Whisper audio-only'],proof['Whisper audio-only']=new_whisper(probe,work)
    refs=validate_manifest(json.loads((probe/'eval/references.json').read_text()))
    pairs=json.loads((probe/'pairs.json').read_text())['items'];index={r['id']:r for r in pairs}
    predictions={label:{} for label in LABELS}
    for ref in refs:
        pair=index[ref['id']];base=pair['base_id']
        for label in LABELS:
            predictions[label][ref['id']]=(ref['draft'] if label=='Copy draft' else
                old[label][base] if pair['condition']=='original' or label=='Qwen text-only' else fresh[label][ref['id']])
    entries=[]
    for condition in CONDITIONS:
        subset=[r for r in refs if index[r['id']]['condition']==condition]
        assert len(subset)==409
        for label in LABELS:
            metrics=score({r['id']:predictions[label][r['id']] for r in subset},subset)
            entries.append({'baseline':label,'condition':condition,'metrics':metrics})
    for label in ['Copy draft','Qwen text-only']:
        metrics=[r['metrics'] for r in entries if r['baseline']==label]
        assert metrics[0]==metrics[1]==metrics[2]
    grouped={(r['baseline'],r['condition']):r['metrics'] for r in entries}
    gap={c:grouped['Qwen audio-only',c]['micro_cer']-grouped['Qwen audio+draft',c]['micro_cer'] for c in CONDITIONS}
    output=work/'predictions';output.mkdir(exist_ok=True)
    paths={}
    for label,values in predictions.items():
        path=output/(label.lower().replace(' ','-').replace('+','-')+'.csv')
        with path.open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['id','prediction'])
            writer.writerows((r['id'],values[r['id']]) for r in refs)
        paths[label]={'file':path.name,'sha256':digest(path)}
    result={'dataset':metadata['name'],'protocol':'ko-correction-v2','scope':'public_eval_development_only',
        'unique_recordings':409,'derived_audio_rows':1227,'entries':entries,'pending':[],
        'qwen_audio_only_minus_audio_draft_cer_pp':gap,
        'qwen_extra_draft_benefit_vs_original_pp':{c:gap[c]-gap['original'] for c in CONDITIONS[1:]},
        'metadata_sha256':digest(probe/'metadata.json'),'plan_sha256':digest(probe/'plan.json'),
        'validation_sha256':digest(probe/'validation.json'),
        'original_v2_comparison_sha256':digest(base_results/'comparison.json'),
        'new_model_verification':proof,'predictions':paths,
        'human_listening_review':'not_performed','private_test_used':False,
        'limitations':['Synthetic noise and simple packet erasure are not a representative field-noise benchmark.',
            'Public development only; original v2 aggregate results were known before designing this probe.',
            'Corruption can remove evidence; human acoustic recoverability has not been reviewed.',
            'No confidence/abstention output or significance analysis is included.']}
    write_json(work/'comparison.json',result)
    print(json.dumps({'dataset':result['dataset'],'measurements':len(entries),'private_test_used':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['public','base_results','probe','work']:parser.add_argument('--'+key.replace('_','-'),type=Path,required=True)
    args=parser.parse_args();build(args.public,args.base_results,args.probe,args.work)
