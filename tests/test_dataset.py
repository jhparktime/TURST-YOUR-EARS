import json
import random
from pathlib import Path

import pytest
from scripts.build_dataset import candidates, choose, load_pairs, valid_edits
from scripts.validate_dataset import validate
from server.app import ROOT


def test_substitutions_respect_word_boundaries_particles_and_numeric_values():
    text='정부는 행정부의 정책을 확인했다 3명과 3.5% 및 -3을 비교했다'
    found=candidates(text, {'정부':'기구','정책':'대책'})
    assert [(text[e['start']:e['end']],e['replacement']) for e in found] == [('정부','기구'),('정책','대책'),('3','2')]


def test_injected_edits_are_auditable_and_copy_cannot_restore_them():
    reference='정부는 미국의 정책을 연구합니다'
    options=candidates(reference,{'정부':'기구','미국':'영국','정책':'대책'})
    first=valid_edits(reference,options,2,random.Random(3))
    assert first == valid_edits(reference,options,2,random.Random(3))
    assert len(first[0]) == 2
    draft=reference
    for edit in reversed(first[0]):
        draft=draft[:edit['start']]+edit['replacement']+draft[edit['end']:]
    assert draft == first[1]


def test_condition_assignment_balanced_in_local_duration_blocks():
    rows=[{'samples':number} for number in range(12)]
    selected=choose(rows,12,random.Random(4))
    assert sorted(label for _,label in selected).count('clean') == 4
    for block in range(4):
        labels={label for row,label in selected if row['samples']//3==block}
        assert labels == {'clean','single','multiple'}


def test_released_dataset_audio_and_dev_scores():
    pytest.importorskip('soundfile')
    report=validate(ROOT/'datasets/tye-fleurs-ko-v1')
    assert report['splits']['dev']['references_checked'] is True
    assert report['splits']['eval']['references_checked'] is False
    assert report['splits']['dev']['utterances'] == 30
    assert report['splits']['eval']['utterances'] == 75


def test_public_eval_has_no_reference_condition_or_source_mapping():
    root=ROOT/'datasets/tye-fleurs-ko-v1'
    data=json.loads((root/'eval/inputs.json').read_text())
    assert all(set(row)=={'id','audio','draft'} for row in data['items'])
    assert not (root/'eval/references.json').exists()
    assert not list(root.rglob('*provenance*'))
    assert not list(root.rglob('*review*.json'))
    assert len({row['id'] for row in data['items']})==75


def test_lexicon_has_no_duplicate_sources_and_preserves_particle_class():
    path=ROOT/'datasets/tye-fleurs-ko-v1/substitutions.json'
    raw=json.loads(path.read_text())['pairs']
    assert len({a for a,b in raw})==len(raw)
    selected=load_pairs(path)
    assert selected['미국']=='영국'
    assert all(a != b and len(a)==len(b) for a,b in selected.items())
