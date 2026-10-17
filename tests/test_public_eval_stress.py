import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from scripts.build_public_eval_stress import build, degrade
from scripts.build_dataset import digest, write_json
from scripts.validate_public_eval_stress import validate


def source(path):
    folder=path/'eval/audio';folder.mkdir(parents=True)
    samples=np.rint(4000*np.sin(np.arange(32000)*2*np.pi*440/16000)).astype(np.int16)
    inputs=[];refs=[]
    for ident,draft in [('right','오늘은 맑아요'),('wrong','오늘은 어두워요')]:
        sf.write(folder/(ident+'.wav'),samples,16000,subtype='PCM_16')
        inputs.append({'id':ident,'audio':'audio/'+ident+'.wav','draft':draft})
        refs.append({'id':ident,'reference':'오늘은 맑아요','draft':draft,'source':'test-drafter'})
    def manifest(rows):return {'name':'test-public-eval','protocol':'ko-correction-v2','items':rows}
    write_json(path/'eval/inputs.json',manifest(inputs));write_json(path/'eval/references.json',manifest(refs))
    write_json(path/'metadata.json',{'name':'test-public-only'})
    (path/'NOTICE').write_text('Fixture; no private data.')


def test_complete_paired_waveforms_and_references_validate(tmp_path):
    public=tmp_path/'public';source(public)
    out=tmp_path/'probe';metadata=build(public,out,expected_rows=2)
    assert metadata['derived_audio_rows']==6 and metadata['new_audio_rows']==4
    assert metadata['draft_correct_per_condition']==metadata['draft_error_per_condition']==1
    result=validate(public,out,expected_rows=2)
    assert result['all_packet_masks_and_preserved_samples_verified']
    with pytest.raises(ValueError,match='never overwrite'):build(public,out,expected_rows=2)


def test_audio_transforms_ignore_changed_reference_text_and_are_repeatable(tmp_path):
    public=tmp_path/'public';source(public)
    a=tmp_path/'a';build(public,a,expected_rows=2)
    refpath=public/'eval/references.json';refs=json.loads(refpath.read_text())
    for r in refs['items']:r['reference']='다른 정답을 사용해도 음성은 같아야 합니다'
    write_json(refpath,refs)
    b=tmp_path/'b';build(public,b,expected_rows=2)
    assert {p.name:digest(p) for p in (a/'eval/audio').glob('*.wav')}=={
        p.name:digest(p) for p in (b/'eval/audio').glob('*.wav')}


def test_validator_detects_corrupted_preserved_audio(tmp_path):
    public=tmp_path/'public';source(public)
    out=tmp_path/'probe';build(public,out,expected_rows=2)
    path=next((out/'eval/audio').glob('*packet_loss_20.wav'))
    y,sr=sf.read(path,dtype='int16');y[:500]=123;sf.write(path,y,sr,subtype='PCM_16')
    with pytest.raises(AssertionError):validate(public,out,expected_rows=2)


def test_public_packet_ignores_extra_secret_file(tmp_path):
    import zipfile
    from scripts.package_public_eval_stress import package
    public=tmp_path/'public';source(public)
    probe=tmp_path/'probe';build(public,probe,expected_rows=2)
    write_json(probe/'validation.json',validate(public,probe,expected_rows=2))
    (probe/'private-test-references.json').write_text('PRIVATE_SENTINEL_MUST_NOT_EXPORT')
    output=tmp_path/'public.zip';receipt=package(public,probe,output,expected_rows=2)
    assert receipt['archive_members']==16 and receipt['explicit_allowlist_verified']
    with zipfile.ZipFile(output) as z:
        assert 'private-test-references.json' not in z.namelist()
        assert not any(b'PRIVATE_SENTINEL' in z.read(name) for name in z.namelist())


def test_silent_input_is_rejected_instead_of_dropping_a_recording():
    with pytest.raises(ValueError,match='Silent source'):degrade(np.zeros(16000,dtype=np.int16),'zero','gaussian_5db')


def test_model_receipt_rejects_output_from_different_audio(tmp_path):
    import csv
    from scripts.baseline import PROMPTS, SYSTEM, load_inputs
    from scripts.run_omni_baselines import MODEL, REVISION
    from scripts.score_public_eval_stress import new_qwen
    public=tmp_path/'public';source(public)
    probe=tmp_path/'probe';build(public,probe,expected_rows=2)
    inputs=probe/'inference/eval/inputs.json';rows=load_inputs(inputs)
    work=tmp_path/'run';(work/'omni/audio-only').mkdir(parents=True);(work/'omni/eval').mkdir()
    original={'model_files_sha256':{'weights':'fixed-fixture'},'packages':{'torch':'fixture'}}
    contract={**original,'model':MODEL,'revision':REVISION,'mode':'audio-only','prompt':PROMPTS['audio-only'],
        'system':SYSTEM,'seed':0,'do_sample':False,'max_new_tokens':512,'row_limit':None,'reference_access':False,
        'splits':['eval'],'input_manifests_sha256':{'eval':digest(inputs)},'device':'mps','dtype':'torch.bfloat16',
        'attention':'sdpa','output_postprocessing':'strip_only'}
    records=[{'id':r['id'],'split':'eval','prediction':'실제 출력','audio_sha256':digest(inputs.parent/r['audio']),
        'draft_sha256':None,'new_tokens':1,'at_token_limit':False,'empty_output':False} for r in rows]
    checkpoint=work/'omni/audio-only/checkpoint.json'
    write_json(checkpoint,{'contract':contract,'items':records})
    write_json(work/'omni/audio-only/run.json',{**contract,'rows':len(rows),
        'output_diagnostics_by_split':{'eval':{'utterances':len(rows),'at_token_limit':0,'empty_outputs':0}}})
    with (work/'omni/eval/audio-only.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['id','prediction']);writer.writerows((r['id'],r['prediction']) for r in records)
    predictions,_=new_qwen(probe,work,'audio-only',original)
    assert len(predictions)==4
    records[0]['audio_sha256']='another-audio'
    write_json(checkpoint,{'contract':contract,'items':records})
    with pytest.raises(AssertionError):new_qwen(probe,work,'audio-only',original)


@pytest.mark.parametrize('field',['draft','reference'])
def test_full_public_stress_browser_python_parity(field):
    import shutil
    import subprocess
    from server.scoring_v2 import score
    from scripts.evaluate_public_stress import evaluate
    if not shutil.which('node'):pytest.skip('Node is required.')
    root=Path(__file__).resolve().parent.parent
    folder=root/'web/data-stress'
    manifest=json.loads((folder/'eval.json').read_text())
    pairing=json.loads((folder/'pair-index.json').read_text())
    predictions={r['id']:r[field] for r in manifest['items']}
    p=subprocess.run(['node','-e',"const fs=require('node:fs'),s=require('./web/stress-scorer.js'),p=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(s.score(new Map(Object.entries(p.predictions)),p.manifest,p.pairing)));"],
        input=json.dumps({'manifest':manifest,'pairing':pairing,'predictions':predictions}),text=True,capture_output=True,check=True,cwd=root)
    result=json.loads(p.stdout);pairs={r['id']:r for r in pairing['items']}
    assert result==evaluate(predictions,manifest,pairing)
    assert result['unique_recordings']==409 and result['derived_audio_rows']==1227
    for condition,values in result['by_condition'].items():
        rows=[r for r in manifest['items'] if pairs[r['id']]['condition']==condition]
        subsets={'all':rows,'original_draft_correct':[r for r in rows if pairs[r['id']]['draft_correct']],
            'original_draft_error':[r for r in rows if not pairs[r['id']]['draft_correct']]}
        for name,subset in subsets.items():assert values[name]==score({r['id']:predictions[r['id']] for r in subset},subset)
