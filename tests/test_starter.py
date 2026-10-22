import json
from pathlib import Path

import pytest
from scripts.train_starter import fit, correct, predict


def write_split(tmp_path, split='train'):
    rows = [{'id': f'{n}', 'audio': 'unused.wav', 'draft': '일상화탄소는 위험하다.'} for n in range(3)]
    gold = [{'id': r['id'], 'draft': r['draft'], 'reference': '일산화탄소는 위험하다'} for r in rows]
    inputs, refs = tmp_path/'inputs.json', tmp_path/'refs.json'
    for path, items in [(inputs, rows), (refs, gold)]:
        path.write_text(json.dumps({'name': 'tye-ko-asr-v2-'+split, 'protocol':'ko-correction-v2', 'items':items}))
    return inputs, refs


def test_train_and_predict_unseen_id_without_references(tmp_path):
    inputs, refs = write_split(tmp_path)
    model = fit(inputs, refs)
    assert model['training_rows'] == 3
    assert model['rules']['일상화탄소는']['support'] == 3
    assert correct('일상화탄소는,  위험하다!', model) == '일산화탄소는,  위험하다!'
    assert correct('앞일상화탄소는', model) == '앞일상화탄소는'
    model_path = tmp_path/'model.json'
    model_path.write_text(json.dumps(model))
    refs.unlink()  # Inference must be independent of reference availability.
    inputs.write_text(json.dumps({'name':'tye-ko-asr-v2-eval','protocol':'ko-correction-v2','items':[
        {'id':'unseen','audio':'unused.wav','draft':'일상화탄소는 위험하다.'}]}))
    output = tmp_path/'predictions.csv'
    assert predict(inputs, model_path, output)['rows'] == 1
    assert 'unseen,일산화탄소는 위험하다.' in output.read_text()


def test_eval_cannot_be_fitted(tmp_path):
    inputs, refs = write_split(tmp_path, 'eval')
    with pytest.raises(ValueError, match='Train split only'):
        fit(inputs, refs)


def test_correct_token_exposure_prevents_overconfident_rule(tmp_path):
    inputs, refs = write_split(tmp_path)
    data = json.loads(refs.read_text())
    data['items'][0]['reference'] = '일상화탄소는 위험하다'
    refs.write_text(json.dumps(data))
    assert fit(inputs, refs, min_support=2, min_confidence=0.9)['rules'] == {}
