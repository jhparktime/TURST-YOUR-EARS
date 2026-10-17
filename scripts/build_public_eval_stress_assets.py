"""Export public stress references, pairing and measured aggregates for Pages."""
import argparse
import csv
import json
from pathlib import Path
import shutil

from scripts.build_dataset import digest, write_json
from scripts.score_public_eval_stress import LABELS, CONDITIONS
from server.scoring_v2 import score, validate_manifest

ROOT=Path(__file__).resolve().parent.parent


def build(probe,results,output):
    metadata=json.loads((probe/'metadata.json').read_text())
    validation=json.loads((probe/'validation.json').read_text())
    assert validation['metadata_sha256']==digest(probe/'metadata.json') and validation['derived_audio_rows']==1227
    manifest=json.loads((probe/'eval/references.json').read_text());refs=validate_manifest(manifest)
    pairs=json.loads((probe/'pairs.json').read_text())['items'];index={r['id']:r for r in pairs}
    entries=[]
    comparison=results/'comparison.json'
    if comparison.exists():
        aggregate=json.loads(comparison.read_text())
        assert aggregate['metadata_sha256']==digest(probe/'metadata.json')
        assert len(aggregate['entries'])==15 and not aggregate['pending'] and aggregate['private_test_used'] is False
        entries=aggregate['entries']
    else:
        for condition in CONDITIONS:
            subset=[r for r in refs if index[r['id']]['condition']==condition]
            entries.append({'baseline':'Copy draft','condition':condition,
                'metrics':score({r['id']:r['draft'] for r in subset},subset)})
        aggregate={'dataset':metadata['name'],'scope':'public_eval_development_only','entries':entries,
            'pending':[{'baseline':label,'condition':c} for c in CONDITIONS for label in LABELS if label!='Copy draft'],
            'human_listening_review':'not_performed','private_test_used':False,
            'model_difficulty_established':False}
    def public_aggregates(value):
        if isinstance(value,dict):
            assert not ({'id','draft','reference','prediction','audio','base_id'} & value.keys())
            for v in value.values():public_aggregates(v)
        elif isinstance(value,list):
            for v in value:public_aggregates(v)
    public_aggregates(aggregate)
    output.mkdir(parents=True,exist_ok=True)
    write_json(output/'eval.json',manifest)
    write_json(output/'pair-index.json',{'dataset':metadata['name'],'items':[
        {k:r[k] for k in ['id','base_id','condition','draft_correct']} for r in pairs]})
    with (output/'eval-copy.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['id','prediction']);writer.writerows((r['id'],r['draft']) for r in refs)
    write_json(output/'baselines.json',aggregate)
    write_json(output/'metadata.json',metadata)
    write_json(output/'receipt.json',{'dataset':metadata['name'],'scope':'public_eval_only',
        'files':{f:digest(output/f) for f in ['eval.json','pair-index.json','eval-copy.csv','baselines.json','metadata.json']}})
    measurement=ROOT/'docs/measurements/public-eval-stress'
    measurement.mkdir(parents=True,exist_ok=True)
    for name in ['plan.json','metadata.json','validation.json','frozen-specification.md']:
        shutil.copyfile(probe/name,measurement/name)
    print(json.dumps({'dataset':metadata['name'],'measurements':len(entries),'pending':len(aggregate['pending']),
        'unique_recordings':409,'derived_audio_rows':1227,'private_test_used':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ['probe','results']:parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'web/data-stress')
    args=parser.parse_args();build(args.probe,args.results,args.output)
