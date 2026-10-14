import json
from pathlib import Path

import pytest

from scripts.build_dataset import digest, write_json
from scripts.build_final_dataset import accepted_candidates, disjoint_pools, supported_edits
from scripts.transcribe_audio import MODEL, REVISION
from scripts.validate_dataset import validate
from server.app import ROOT


def candidate_fixture(tmp_path):
    rows = [{'id':source,'source_split':source,'source_filename':source+'.wav','reference':'정부는 미국의 정책을 확인합니다',
             'audio_sha256':source,'source_id':source} for source in ('train','dev','test')]
    write_json(tmp_path/'candidate-provenance.json',rows)
    write_json(tmp_path/'substitutions.json',{'pairs':[['정부','기구'],['미국','영국'],['정책','대책']]})
    write_json(tmp_path/'candidate-plan.json',{'provenance_sha256':digest(tmp_path/'candidate-provenance.json'),
        'lexicon_sha256':digest(tmp_path/'substitutions.json')})
    for row in rows:
        prediction = '정부는미국의 정책을 확인합니다.' if row['id']!='test' else '외국어 음성 자료를 확인합니다.'
        write_json(tmp_path/f"asr-{row['id']}/audio-only.json",{'model':MODEL,'revision':REVISION,
            'items':[{'id':row['id'],'audio_sha256':row['audio_sha256'],'prediction':prediction}]})
    return rows


def test_qa_disagreement_excludes_candidate_without_rewriting_upstream_gold(tmp_path):
    original = candidate_fixture(tmp_path)
    accepted, counts, _, _ = accepted_candidates(tmp_path)
    assert {r['id'] for r in accepted}=={'train','dev'}
    assert counts['test']['excluded_qa']==1
    assert json.loads((tmp_path/'candidate-provenance.json').read_text())==original


def test_qa_rejects_missing_audio_or_different_model(tmp_path):
    candidate_fixture(tmp_path)
    path=tmp_path/'asr-dev/audio-only.json'
    state=json.loads(path.read_text());state['items'][0]['audio_sha256']='other-recording'
    write_json(path,state)
    with pytest.raises(ValueError,match='checksum'):accepted_candidates(tmp_path)
    state['revision']='another-model'
    write_json(path,state)
    with pytest.raises(ValueError,match='model'):accepted_candidates(tmp_path)


def test_a_low_asr_error_rate_cannot_corroborate_a_wrong_injection_target():
    reference='정부는 정책을 확인합니다'
    cer, options=supported_edits(reference,'정부는 대책을 확인합니다',{'정부':'기구','정책':'대책'})
    assert cer<10
    assert [(reference[e['start']:e['end']],e['replacement']) for e in options]==[('정부','기구')]


def test_holdout_pool_deduplicates_source_sentence_across_official_dev_test():
    common={'reference':'중복 문장을 제외합니다','source_id':'same','audio_sha256':'a'}
    rows=[common|{'id':'dev','source_split':'dev'},common|{'id':'test','source_split':'test','audio_sha256':'b'},
          {'id':'train','source_split':'train','reference':'개발에는 다른 화자 집합을 사용합니다','source_id':'train','audio_sha256':'c'}]
    pools=disjoint_pools(rows)
    assert len(pools['eval'])==1
    assert pools['dev'][0]['source_split']=='train'


def test_final_public_release_is_sealed_and_balanced():
    report=validate(ROOT/'datasets/tye-ko-v2')
    assert report['status']=='frozen_release_validated'
    assert report['human_listening_review']=='not_performed'
    assert report['private_qa_checked'] is False
    assert report['splits']['dev']['utterances']==60
    assert report['splits']['eval']['utterances']==60


def test_seal_detects_modified_document_before_trusting_counts(tmp_path):
    # Integrity gate must cover documentation and limits as well as audio.
    write_json(tmp_path/'metadata.json',{'status':'frozen_automatic_crosscheck'})
    (tmp_path/'README.md').write_text('Original evidence limits')
    write_json(tmp_path/'release-lock.json',{'sha256':{str(p.relative_to(tmp_path)):digest(p)
        for p in tmp_path.iterdir() if p.name!='release-lock.json'}})
    (tmp_path/'README.md').write_text('Incorrectly claims human review')
    with pytest.raises(ValueError,match='Frozen public release'):validate(tmp_path)
