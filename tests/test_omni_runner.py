import json
import pytest

from scripts.run_omni_baselines import generated_prediction, load_jobs, validate_checkpoint


def test_inputs_never_accept_reference_or_condition(tmp_path):
    folder = tmp_path / 'eval'
    folder.mkdir()
    for extra in ({'reference': '정답'}, {'condition': 'single'}):
        (folder / 'inputs.json').write_text(json.dumps({'items': [
            {'id': 'a', 'audio': 'a.wav', 'draft': '초안'} | extra]}))
        with pytest.raises(ValueError, match='only id, audio, draft'):
            load_jobs(tmp_path, tmp_path / 'private', ['eval'], None)


def test_only_requested_manifests_are_opened(tmp_path):
    folder = tmp_path / 'eval'
    folder.mkdir()
    (folder / 'inputs.json').write_text(json.dumps({'items': [
        {'id': 'a', 'audio': 'a.wav', 'draft': '초안'}]}))
    jobs, hashes = load_jobs(tmp_path, tmp_path / 'nonexistent-private', ['eval'], None)
    assert len(jobs) == 1 and set(hashes) == {'eval'}


def test_real_asr_train_jobs_allow_empty_draft_without_private_access(tmp_path):
    folder = tmp_path / 'train'
    folder.mkdir()
    (folder / 'inputs.json').write_text(json.dumps({'protocol':'ko-correction-v2','items':[
        {'id':'empty-asr','audio':'a.wav','draft':''}]}))
    jobs, hashes = load_jobs(tmp_path,tmp_path/'nonexistent-private',['train'],None)
    assert jobs[0]['row']['draft'] == '' and set(hashes) == {'train'}


def test_resume_rejects_changed_contract_or_duplicate_records():
    contract = {'mode': 'text-only', 'input_sha256': 'first'}
    with pytest.raises(ValueError, match='differ'):
        validate_checkpoint({'contract': contract, 'items': []}, contract | {'input_sha256': 'changed'})
    with pytest.raises(ValueError, match='duplicate'):
        validate_checkpoint({'contract': contract, 'items': [
            {'split': 'eval', 'id': 'a'}, {'split': 'eval', 'id': 'a'}]}, contract)


def test_length_limited_model_output_is_kept_without_fallback():
    prediction, flags = generated_prediction('  반복된 생성 결과  ', [7] * 512, 512, 151645)
    assert prediction == '반복된 생성 결과'
    assert flags == {'finish_reason': 'length', 'at_token_limit': True, 'empty_output': False}


def test_empty_model_output_is_a_valid_deletion_prediction():
    import csv
    import io
    from server.scoring import parse_submission, score, validate_manifest
    from pathlib import Path
    refs = validate_manifest(json.loads((Path(__file__).resolve().parent.parent /
        'examples/demo-references.json').read_text()))
    prediction, flags = generated_prediction('', [151645], 512, [151645, 151643])
    assert prediction == '' and flags['empty_output'] and flags['finish_reason'] == 'eos'
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(['id', 'prediction'])
    writer.writerows((row['id'], prediction) for row in refs)
    metrics = score(parse_submission(stream.getvalue().encode()), refs)
    assert metrics['utterances'] == len(refs) and metrics['micro_cer'] == 100


def test_eos_at_exact_limit_is_distinct_from_truncation():
    _, flags = generated_prediction('전사', [7] * 511 + [151645], 512, 151645)
    assert flags['at_token_limit'] is True and flags['finish_reason'] == 'eos'
