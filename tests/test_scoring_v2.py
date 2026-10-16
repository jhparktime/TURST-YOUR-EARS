"""Real-ASR error operations and independently specified correction outcomes."""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from server.scoring import distance, normalize
from server.scoring_v2 import aligned_slots, condition, score, validate_manifest

ROOT = Path(__file__).resolve().parent.parent


def fixture():
    return {'name': 'real-asr-unit', 'protocol': 'ko-correction-v2', 'items': [
        {'id': 'sub', 'reference': '가나다', 'draft': '가마 다', 'source': 'a'},
        {'id': 'del', 'reference': '가나다', 'draft': '가다', 'source': 'b'},
        {'id': 'ins', 'reference': '가나다', 'draft': '가하나다', 'source': 'a'},
        {'id': 'clean', 'reference': '가나다', 'draft': '가 나 다!', 'source': 'b'},
        {'id': 'empty', 'reference': '가나다', 'draft': '', 'source': 'a'},
    ]}


@pytest.mark.parametrize('draft,expected', [
    ('가마다', (1, 0, 0, 'substitution')), ('가다', (0, 1, 0, 'deletion')),
    ('가하나다', (0, 0, 1, 'insertion')), ('', (0, 3, 0, 'deletion')),
    ('가나다', (0, 0, 0, 'clean'))])
def test_known_error_operations(draft, expected):
    value = aligned_slots('가나다', draft)
    assert (value['substitutions'], value['deletions'], value['insertions'], condition(value)) == expected
    assert value['errors'] == sum(expected[:3])


def test_gold_copy_and_empty_have_known_outcomes():
    refs = validate_manifest(fixture())
    copied = score({r['id']:r['draft'] for r in refs}, refs)
    assert copied['counts']['errors'] == 6
    assert copied['micro_cer'] == 40
    assert copied['slot_restoration_rate'] == 0
    assert copied['harmful_edit_rate'] == copied['unwanted_insertion_rate'] == copied['clean_change_rate'] == 0
    assert copied['correction_precision'] is None and copied['correction_f1'] == 0
    gold = score({r['id']:r['reference'] for r in refs}, refs)
    assert gold['micro_cer'] == 0 and gold['slot_restoration_rate'] == 100
    assert gold['correction_precision'] == gold['correction_f1'] == 100
    assert gold['harmful_edit_rate'] == gold['unwanted_insertion_rate'] == 0
    empty = score({r['id']:'' for r in refs}, refs)
    assert empty['micro_cer'] == 100


def test_new_insertions_are_not_hidden_in_character_preservation():
    refs = [{'id':'a','reference':'가나다','draft':'가나다','source':'a'}]
    value = score({'a':'가하나다'}, refs)
    assert value['harmful_edit_rate'] == 0
    assert value['unwanted_insertion_rate'] == 25
    assert value['clean_change_rate'] == 100 and value['correction_precision'] == 0


def test_alignment_conserves_strings_and_edit_distance():
    rng = random.Random(1821)
    for _ in range(150):
        reference = ''.join(rng.choices('가나다😀', k=rng.randrange(1, 10)))
        hypothesis = ''.join(rng.choices('가나다😀', k=rng.randrange(0, 12)))
        value = aligned_slots(reference, hypothesis)
        reconstructed = value['gaps'][0] + ''.join(c + value['gaps'][i+1]
            for i, c in enumerate(value['characters']))
        assert reconstructed == hypothesis
        assert value['errors'] == distance(reference, hypothesis)
        assert sum(value[k] for k in ('substitutions','deletions','insertions')) == value['errors']


@pytest.mark.skipif(not shutil.which('node'), reason='Node required')
def test_python_browser_parity_real_asr_slots_and_unicode():
    manifest = fixture()
    rng = random.Random(19)
    for i in range(25):
        manifest['items'].append({'id':str(i),'reference': ''.join(rng.choices('가나다😀',k=8)),
            'draft': ''.join(rng.choices('가나다😀',k=rng.randrange(0,12))), 'source':'a'})
    for predictions in [{r['id']:r[key] for r in manifest['items']} for key in ('reference','draft')] + [
            {r['id']:'더한' + r['draft'][:-1] for r in manifest['items']}]:
        result = subprocess.run(['node','-e', '''
const fs=require('node:fs'),s=require('./web/scorer-v2.js');
const p=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(s.score(new Map(Object.entries(p.predictions)),p.manifest)));
'''],input=json.dumps({'predictions':predictions,'manifest':manifest}),text=True,
            capture_output=True,check=True,cwd=ROOT)
        assert json.loads(result.stdout) == score(predictions,manifest['items'])


def test_protocol_and_reference_validation():
    manifest = fixture()
    with pytest.raises(ValueError, match='protocol'):
        validate_manifest(manifest | {'protocol':'ko-correction-v1'})
    with pytest.raises(ValueError, match='exactly'):
        validate_manifest(manifest | {'items':[manifest['items'][0] | {'edits':[]}]})
    with pytest.raises(ValueError, match='IDs'):
        score({'wrong':'가나다'},manifest['items'])
    assert normalize('세 시') != normalize('3시')
