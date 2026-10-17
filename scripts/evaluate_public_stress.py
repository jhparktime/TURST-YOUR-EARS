"""Participant-facing public stress grading, identical to the browser groups."""
import argparse
import json
from pathlib import Path

from server.scoring import normalize, parse_submission
from server.scoring_v2 import score, validate_manifest

CONDITIONS=('original','gaussian_5db','packet_loss_20')


def evaluate(predictions,manifest,pairing):
    refs=validate_manifest(manifest)
    if (manifest['name']!='tye-public-eval-stress-v1-eval' or len(refs)!=1227 or
        pairing.get('dataset',pairing.get('name'))!='tye-public-eval-stress-v1'):
        raise ValueError('Wrong public stress dataset.')
    pair_rows=pairing['items'];pairs={r['id']:r for r in pair_rows}
    if len(pair_rows)!=1227 or len(pairs)!=1227 or set(pairs)!={r['id'] for r in refs}:
        raise ValueError('Incomplete or duplicate pairing IDs.')
    score(predictions,refs)
    originals={r['base_id'] for r in pair_rows if r['condition']=='original'}
    for ref in refs:
        pair=pairs[ref['id']]
        if (pair['condition'] not in CONDITIONS or ref['id']!=pair['base_id']+'--'+pair['condition'] or
            type(pair['draft_correct']) is not bool or
            pair['draft_correct']!=(normalize(ref['reference'])==normalize(ref['draft']))):
            raise ValueError('Invalid public pairing metadata.')
    result={}
    for condition in CONDITIONS:
        rows=[r for r in refs if pairs[r['id']]['condition']==condition]
        if len(rows)!=409 or {pairs[r['id']]['base_id'] for r in rows}!=originals or len(originals)!=409:
            raise ValueError('Incomplete paired condition.')
        groups={'all':rows,'original_draft_correct':[r for r in rows if pairs[r['id']]['draft_correct']],
            'original_draft_error':[r for r in rows if not pairs[r['id']]['draft_correct']]}
        result[condition]={name:score({r['id']:predictions[r['id']] for r in selected},selected)
            for name,selected in groups.items()}
    return {'dataset':'tye-public-eval-stress-v1','protocol':'ko-correction-v2',
        'scope':'public_eval_development_only','unique_recordings':409,'derived_audio_rows':1227,
        'private_test_used':False,'by_condition':result}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--predictions',type=Path,required=True)
    args=parser.parse_args()
    try:
        result=evaluate(parse_submission(args.predictions.read_bytes()),
            json.loads((args.probe/'eval/references.json').read_text()),json.loads((args.probe/'pairs.json').read_text()))
    except (ValueError,KeyError,OSError,TypeError) as exc:parser.error(str(exc))
    print(json.dumps(result,ensure_ascii=False,indent=2))
