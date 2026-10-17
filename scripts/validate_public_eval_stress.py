"""Check every paired public stress WAV and unchanged draft/reference."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import soundfile as sf

from scripts.baseline import load_inputs
from scripts.build_dataset import digest, write_json
from server.scoring import normalize
from server.scoring_v2 import validate_manifest

CONDITIONS=('original','gaussian_5db','packet_loss_20')


def validate(public, probe, expected_rows=409):
    metadata=json.loads((probe/'metadata.json').read_text())
    plan=json.loads((probe/'plan.json').read_text())
    assert metadata['plan_sha256']==digest(probe/'plan.json')
    assert plan['specification_sha256']==digest(probe/'frozen-specification.md')
    assert plan['source_inputs_sha256']==digest(public/'eval/inputs.json')
    assert plan['source_references_sha256']==digest(public/'eval/references.json')
    assert plan['source_metadata_sha256']==digest(public/'metadata.json')
    for key,file in [('inputs','eval/inputs.json'),('references','eval/references.json'),
                     ('pairs','pairs.json'),('inference_inputs','inference/eval/inputs.json')]:
        assert metadata[key+'_sha256']==digest(probe/file)
    base={r['id']:r for r in load_inputs(public/'eval/inputs.json')}
    gold={r['id']:r for r in validate_manifest(json.loads((public/'eval/references.json').read_text()))}
    rows=load_inputs(probe/'eval/inputs.json')
    refs={r['id']:r for r in validate_manifest(json.loads((probe/'eval/references.json').read_text()))}
    pair_rows=json.loads((probe/'pairs.json').read_text())['items']
    assert len(base)==len(gold)==expected_rows
    assert len(rows)==len(refs)==len(pair_rows)==expected_rows*3
    pairs={r['id']:r for r in pair_rows}
    assert len(pairs)==len(pair_rows) and set(pairs)==set(refs)=={r['id'] for r in rows}
    assert {(p['base_id'],p['condition']) for p in pair_rows}=={(b,c) for b in base for c in CONDITIONS}
    snr=[]
    for row in rows:
        pair=pairs[row['id']];bid=pair['base_id'];condition=pair['condition']
        assert row['id']==bid+'--'+condition
        assert row['draft']==base[bid]['draft']==refs[row['id']]['draft']
        assert refs[row['id']]=={**gold[bid],'id':row['id']}
        assert pair['draft_correct']==(normalize(gold[bid]['reference'])==normalize(row['draft']))
        original=(public/'eval'/base[bid]['audio']).resolve()
        target=(probe/'eval'/row['audio']).resolve()
        assert target.is_relative_to((probe/'eval/audio').resolve())
        assert digest(original)==pair['original_audio_sha256']
        assert digest(target)==pair['audio_sha256']
        x,sr=sf.read(original,dtype='int16');y,yr=sf.read(target,dtype='int16')
        assert sr==yr==16000 and x.ndim==y.ndim==1 and len(x)==len(y)==pair['frames']
        assert sf.info(target).subtype=='PCM_16'
        if condition=='original':assert digest(target)==digest(original)
        elif condition=='gaussian_5db':
            assert digest(target)!=digest(original)
            gain=pair['gain'];assert 0<gain<=1
            speech=x.astype(np.float64)/32768*gain
            noise=y.astype(np.float64)/32768-speech
            measured=float(10*np.log10(np.mean(speech**2)/np.mean(noise**2)))
            assert abs(measured-pair['effective_snr_db'])<1e-10
            assert abs(measured-5)<0.05
            assert np.max(np.abs(y.astype(np.float64)/32768))<0.981
            snr.append(measured)
        else:
            packets=math.ceil(len(x)/320);count=math.floor(0.2*packets+0.5)
            seed=int.from_bytes(hashlib.sha256(
                f'tye-public-eval-stress-v1:packet_loss_20:{bid}'.encode()).digest()[:8],'big')
            selected=sorted(np.random.Generator(np.random.PCG64(seed)).choice(packets,size=count,replace=False).tolist())
            assert pair['dropped_packet_indices']==selected
            assert pair['lost_packets']==count and pair['packets']==packets
            mask=np.zeros(len(x),dtype=bool)
            for packet in selected:mask[packet*320:min((packet+1)*320,len(x))]=True
            assert pair['lost_samples']==int(mask.sum())
            assert pair['lost_sample_fraction']==float(mask.mean())
            assert np.all(y[mask]==0) and np.array_equal(y[~mask],x[~mask])
            assert digest(target)!=digest(original)
    new=load_inputs(probe/'inference/eval/inputs.json')
    assert len(new)==expected_rows*2
    assert {r['id'] for r in new}=={r['id'] for r in rows if pairs[r['id']]['condition']!='original'}
    byid={r['id']:r for r in rows}
    for r in new:
        assert r['draft']==byid[r['id']]['draft']
        assert (probe/'inference/eval'/r['audio']).resolve()==(probe/'eval'/byid[r['id']]['audio']).resolve()
    return {'dataset':plan['name'],'scope':'all_public_eval_pairs_and_waveforms',
        'unique_recordings':len(base),'derived_audio_rows':len(rows),'new_audio_rows':len(new),
        'all_drafts_and_references_unchanged':True,'all_original_wav_bytes_unchanged':True,
        'all_packet_masks_and_preserved_samples_verified':True,
        'effective_snr_db_min':min(snr),'effective_snr_db_max':max(snr),
        'metadata_sha256':digest(probe/'metadata.json'),'plan_sha256':digest(probe/'plan.json'),
        'private_test_used':False,'human_listening_review':'not_performed',
        'model_difficulty_established':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['public','probe','output']:parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    result=validate(args.public,args.probe)
    write_json(args.output,result)
    print(json.dumps(result))
