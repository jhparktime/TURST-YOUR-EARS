import json
import pytest

from scripts.run_omni_baselines import load_jobs, validate_checkpoint


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


def test_resume_rejects_changed_contract_or_duplicate_records():
    contract = {'mode': 'text-only', 'input_sha256': 'first'}
    with pytest.raises(ValueError, match='differ'):
        validate_checkpoint({'contract': contract, 'items': []}, contract | {'input_sha256': 'changed'})
    with pytest.raises(ValueError, match='duplicate'):
        validate_checkpoint({'contract': contract, 'items': [
            {'split': 'eval', 'id': 'a'}, {'split': 'eval', 'id': 'a'}]}, contract)
