"""Validity-audit safeguards: frozen sampling, answer isolation, honest coverage."""
import json
import wave
import zipfile

import pytest

from scripts.audit_public_eval import (LABELS, build, content_digest, digest,
                                      numeric_notation_candidate, rescore, sample_rows)


def fixtures(tmp_path):
    public, omni = tmp_path/'public', tmp_path/'omni'
    root = public/'eval'
    (root/'audio').mkdir(parents=True)
    (omni/'eval').mkdir(parents=True)
    rows, inputs = [], []
    for source in ('qwen-omni', 'whisper-turbo'):
        for clean in (True, False):
            for index in range(12):
                ident = f'{source}-{clean}-{index}'
                row = dict(id=ident, reference='원천정답비밀', draft='원천정답비밀' if clean else '초안', source=source)
                rows.append(row)
                inputs.append(dict(id=ident, audio=f'audio/{ident}.wav', draft=row['draft']))
                with wave.open(str(root/f'audio/{ident}.wav'), 'wb') as wav:
                    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
                    wav.writeframes(b'\0\0'*160)
    refs = root/'references.json'; inp = root/'inputs.json'
    refs.write_text(json.dumps(dict(name='tye-ko-asr-v2-eval', protocol='ko-correction-v2', items=rows)))
    inp.write_text(json.dumps(dict(name='tye-ko-asr-v2-eval', protocol='ko-correction-v2', items=inputs)))
    paths = [root/'copy-draft.csv', root/'whisper-audio-only.csv', root/'qwen-audio-only.csv',
             omni/'eval/text-only.csv', omni/'eval/audio-draft.csv']
    for path in paths:
        path.write_text('id,prediction\n'+''.join(f'{r["id"]},{r["draft"]}\n' for r in rows))
    comparison = tmp_path/'comparison.json'
    comparison.write_text(json.dumps(dict(public_eval_reuse=dict(inputs_sha256=digest(inp),
        references_sha256=digest(refs), predictions_sha256=dict(zip(LABELS, map(digest, paths)))))))
    return rows, public, omni, comparison


def test_sampling_is_order_independent_and_balanced(tmp_path):
    rows, *_ = fixtures(tmp_path)
    first, strata = sample_rows(rows)
    second, _ = sample_rows(list(reversed(rows)))
    assert [r['id'] for r in first] == [r['id'] for r in second]
    assert len(first) == len({r['id'] for r in first}) == 40
    assert [s['sampled'] for s in strata] == [10]*4


@pytest.mark.parametrize('reference,prediction,expected', [
    ('오 년 이하', '5년 이하', True), ('여덟 척', '8척', True),
    ('이천 일 년', '2010년', False), ('일산화탄소', '일상화탄소', False),
    ('이주 후', '2주 후', True),  # lexical ambiguity remains a LISTENING question
    ('오 년 이하', '5년 이상', False), ('오 년 이하', '오년이하', False)])
def test_numeric_flag_is_limited_full_string_match(reference, prediction, expected):
    assert numeric_notation_candidate(reference, prediction) is expected


def test_reviewer_packet_has_no_answer_keys_or_model_predictions(tmp_path):
    _, public, omni, comparison = fixtures(tmp_path)
    target = tmp_path/'audit'
    build(public, omni, comparison, target)
    text = (target/'reviewer/index.html').read_text()
    payload = json.loads(text.split('<script id="audit-data" type="application/json">')[1].split('</script>')[0])
    assert len(payload['items']) == 40
    assert all(set(r)=={'id','draft','audio'} for r in payload['items'])
    assert all(r['id'].startswith('A') and r['audio']==f'audio/{r["id"]}.wav' for r in payload['items'])
    options = text.split('<select id="utterance">')[1].split('</select>')[0]
    assert options.count('<option ') == 40  # present even before JavaScript starts
    with zipfile.ZipFile(target/'reviewer-only.zip') as archive:
        assert len(archive.namelist()) == 42
        assert all(f'audio/A{i:03d}.wav' in archive.namelist() for i in range(1,41))
        assert all('organizer' not in name for name in archive.namelist())
    assert 'reference' not in payload and 'predictions' not in payload
    plan = json.loads((target/'organizer/plan.json').read_text())
    assert plan['independent_human_review_completed'] == 0
    with pytest.raises(ValueError, match='overwrite'):
        build(public, omni, comparison, target)


def review_fixture(target, tmp_path):
    plan = json.loads((target/'organizer/plan.json').read_text())
    path = tmp_path/'simulated-unit-test-review.json'
    review = dict(audit_id=plan['audit_id'], plan_sha256=plan['plan_sha256'], reviewer='UNIT_TEST_ONLY',
        independent_self_declaration=True, items=[dict(id='A001', heard_text_before_draft='독립전사',
        error_status='genuine_asr_error', audio_needed='yes', evidence='unit-test cue'),
        dict(id='A002', heard_text_before_draft='[불명료]', error_status='uncertain', audio_needed='uncertain')])
    path.write_text(json.dumps(review))
    return path, review


def test_rescore_excludes_unclear_for_all_models_and_reports_partial(tmp_path):
    _, public, omni, comparison = fixtures(tmp_path)
    target = tmp_path/'audit'; build(public, omni, comparison, target)
    path, review = review_fixture(target, tmp_path)
    output = tmp_path/'sensitivity.json'
    rescore(target, path, output)
    result = json.loads(output.read_text())
    assert result['reviewed']==2 and result['usable']==1 and result['total_selected']==40
    assert result['excluded_audit_ids']==['A002']
    for m in result['measurements'].values():
        assert m['original_references_same_subset']['utterances']==1
        assert m['audio_first_human_references']['utterances']==1
    assert result['reference_disagreements'][0]['status']=='disagreement_not_adjudicated_source_error'
    review['independent_self_declaration']=False; path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match='independent reviewer'):
        rescore(target, path, output)
    review['independent_self_declaration']=True; review['items'] *= 2; path.write_text(json.dumps(review))
    with pytest.raises(ValueError, match='Duplicate'):
        rescore(target, path, output)


def test_modified_packet_and_changed_baseline_are_rejected(tmp_path):
    _, public, omni, comparison = fixtures(tmp_path)
    target = tmp_path/'audit'; build(public, omni, comparison, target)
    path, _ = review_fixture(target, tmp_path)
    packet = target/'organizer/items.json'; data=json.loads(packet.read_text())
    data['items'][0]['reference']='변경'; packet.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='organizer items were modified'):
        rescore(target, path, tmp_path/'out.json')
    (omni/'eval/text-only.csv').write_text('id,prediction\nchanged,changed\n')
    with pytest.raises(ValueError, match='Changed baseline'):
        build(public, omni, comparison, tmp_path/'another-audit')
