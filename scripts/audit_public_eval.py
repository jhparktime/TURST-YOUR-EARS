"""Freeze a small PUBLIC Eval validity audit; never opens private Test data.

Build produces an answer-free, self-contained reviewer packet and a separate
organizer record. Generating either is not human review. Score reuses existing
predictions against audio-first HUMAN transcriptions, only on reviewed items.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata
import wave
import zipfile

from server.scoring import normalize, parse_submission
from server.scoring_v2 import score, validate_manifest

SEED = 'tye-eval-validity-audit-40-v1-20261022'
LABELS = ('Copy draft', 'Whisper audio-only', 'Qwen audio-only',
          'Qwen text-only', 'Qwen audio+draft')
ERROR_STATUSES = {'genuine_asr_error', 'notation_only', 'error_and_notation',
                  'correct_draft', 'uncertain'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def content_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def render_reviewer(payload):
    safe = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    options = ''.join(f'<option value="{i}">{html.escape(row["id"])}</option>' for i,row in enumerate(payload['items']))
    template = Path(__file__).with_name('templates') / 'public_eval_audit.html'
    return template.read_text().replace('__PAYLOAD__', safe).replace('__OPTIONS__', options)


def sample_rows(rows, per_stratum=10, seed=SEED):
    """Only generator and ORIGINAL normalized clean/error status affect selection."""
    buckets = defaultdict(list)
    for row in rows:
        state = 'clean' if normalize(row['reference']) == normalize(row['draft']) else 'error'
        buckets[(row['source'], state)].append(row)
    if set(buckets) != {(s, c) for s in ('qwen-omni', 'whisper-turbo') for c in ('clean', 'error')}:
        raise ValueError('Expected the four fixed generator × clean/error strata.')
    selected, strata = [], []
    for (source, state), bucket in sorted(buckets.items()):
        if len(bucket) < per_stratum:
            raise ValueError('Insufficient items in a frozen stratum.')
        ordered = sorted(bucket, key=lambda row: hashlib.sha256(
            f'{seed}:select:{source}:{state}:{row["id"]}'.encode()).hexdigest())
        selected.extend(ordered[:per_stratum])
        strata.append(dict(source=source, original_state=state,
                           population=len(bucket), sampled=per_stratum))
    # Interleave neither source nor correctness labels in the reviewer interface.
    selected.sort(key=lambda row: hashlib.sha256(f'{seed}:order:{row["id"]}'.encode()).hexdigest())
    return selected, strata


def sino(number):
    if number == 0:
        return '영'
    if not 0 < number < 10000:
        return None
    digits = '영일이삼사오육칠팔구'
    text = ''
    for value, unit in ((1000, '천'), (100, '백'), (10, '십'), (1, '')):
        digit, number = divmod(number, value)
        if digit:
            text += ('' if digit == 1 and unit else digits[digit]) + unit
    return text


def native(number):
    if not 1 <= number <= 99:
        return None
    tens = ('', '열', '스물', '서른', '마흔', '쉰', '예순', '일흔', '여든', '아흔')
    ones = ('', '한', '두', '세', '네', '다섯', '여섯', '일곱', '여덟', '아홉')
    if number == 20:
        return '스무'
    return tens[number // 10] + ones[number % 10]


def numeric_notation_candidate(reference, prediction):
    """Exact full-string matches under LIMITED numeral renderings, NOT equivalence.

    The reference chooses whether a permitted rendering matches, so this is an
    oracle diagnostic flag, never a replacement scorer or a model improvement.
    '2주' versus '이주' may differ semantically. Listening remains necessary.
    """
    left, right = normalize(reference), normalize(prediction)
    if left == right or not re.search(r'\d', right):
        return False
    chunks, start = [], 0
    for match in re.finditer(r'\d+(?:\.\d+)?', right):
        chunks.append(re.escape(right[start:match.start()]))
        token = match.group()
        choices = {token}
        if '.' not in token and len(token) <= 4:
            number = int(token)
            choices.add(sino(number))
            choices.add(''.join('영일이삼사오육칠팔구'[int(c)] for c in token))
            if right[match.end():].startswith(('개', '명', '시', '시간', '살', '번', '척', '마리', '권', '주', '달', '가지')):
                choices.add(native(number))
        if token == '0':
            choices.add('공')
        chunks.append('(?:' + '|'.join(re.escape(c) for c in sorted(choices - {None})) + ')')
        start = match.end()
    chunks.append(re.escape(right[start:]))
    return re.fullmatch(''.join(chunks), left) is not None


def load_public(public, omni, comparison):
    root = public / 'eval'
    ref_path, input_path = root / 'references.json', root / 'inputs.json'
    manifest = json.loads(ref_path.read_text())
    if manifest.get('name') != 'tye-ko-asr-v2-eval':
        raise ValueError('This audit is restricted to public Eval.')
    rows = validate_manifest(manifest)
    inputs = {r['id']: r for r in json.loads(input_path.read_text())['items']}
    if len(inputs) != len(rows) or set(inputs) != {r['id'] for r in rows}:
        raise ValueError('Input/reference ID mismatch.')
    paths = dict(zip(LABELS, [root / 'copy-draft.csv', root / 'whisper-audio-only.csv',
                             root / 'qwen-audio-only.csv', omni / 'eval/text-only.csv',
                             omni / 'eval/audio-draft.csv']))
    frozen = json.loads(comparison.read_text())['public_eval_reuse']
    if digest(ref_path) != frozen['references_sha256'] or digest(input_path) != frozen['inputs_sha256']:
        raise ValueError('Public inputs/references differ from completed measurements.')
    predictions = {}
    for label, path in paths.items():
        if digest(path) != frozen['predictions_sha256'][label]:
            raise ValueError(f'Changed baseline output: {label}')
        predictions[label] = parse_submission(path.read_bytes())
        if set(predictions[label]) != set(inputs):
            raise ValueError('Incomplete baseline predictions.')
    if any(inputs[r['id']]['draft'] != r['draft'] for r in rows):
        raise ValueError('Draft mismatch.')
    return rows, inputs, predictions, frozen


def build(public, omni, comparison, output):
    if output.exists():
        raise ValueError('Use a fresh output directory; do not overwrite a frozen audit.')
    rows, inputs, predictions, hashes = load_public(public, omni, comparison)
    selected, strata = sample_rows(rows)
    reviewer_items, organizer_items, audio_files = [], [], {}
    seconds = 0
    for index, row in enumerate(selected, 1):
        ident = row['id']
        audio = (public / 'eval' / inputs[ident]['audio']).resolve()
        if not audio.is_relative_to((public / 'eval/audio').resolve()):
            raise ValueError('Audio must be a local public Eval WAV.')
        with wave.open(str(audio)) as wav:
            duration = wav.getnframes() / wav.getframerate()
        seconds += duration
        alias = f'A{index:03d}'
        audio_files[alias] = audio.read_bytes()
        reviewer_items.append(dict(id=alias, draft=row['draft'], audio=f'audio/{alias}.wav'))
        organizer_items.append(dict(row, audit_id=alias, duration_seconds=duration,
            audio_sha256=digest(audio), predictions={k: v[ident] for k, v in predictions.items()}))
    plan = dict(audit_id=SEED, dataset='tye-ko-asr-v2', split='eval', seed=SEED,
        selection='SHA256(seed:select:source:original_state:id); first 10 per stratum',
        order='SHA256(seed:order:id)', selected_ids=[r['id'] for r in selected],
        selected_utterances=len(selected), population_utterances=len(rows), strata=strata,
        audio_seconds=seconds, frozen_public_hashes=hashes, organizer_items_sha256=content_digest(organizer_items),
        selection_uses_model_outputs=False, independent_human_review_completed=0,
        limitations=['Balanced strata are not the natural Eval distribution.',
                    'Small screening audit; not a significance test or new leaderboard.',
                    'Audio necessity is a reviewer judgment, not a randomized input ablation.',
                    'Numeral flags do not certify acoustic or semantic equivalence.'])
    plan_hash = content_digest(plan)
    plan['plan_sha256'] = plan_hash
    output.mkdir(parents=True)
    (output / 'reviewer').mkdir()
    (output / 'reviewer/audio').mkdir()
    (output / 'organizer').mkdir()
    write_json(output / 'organizer/plan.json', plan)
    write_json(output / 'organizer/items.json', dict(plan_sha256=plan_hash, items=organizer_items))
    payload = dict(audit_id=SEED, plan_sha256=plan_hash, items=reviewer_items)
    (output / 'reviewer/index.html').write_text(render_reviewer(payload))
    for alias, data in audio_files.items():
        (output / f'reviewer/audio/{alias}.wav').write_bytes(data)
    (output / 'reviewer/읽어주세요.txt').write_text(
        'ZIP 압축을 모두 푼 뒤 index.html을 Chrome 또는 Safari에서 여세요. 미리보기에서는 동작하지 않을 수 있습니다. 인터넷·설치가 필요 없습니다.\n'
        '원천 정답·모델 결과·생성기는 이 묶음에 없습니다. 음성을 듣고 먼저 전사한 뒤 초안을 확인하세요.\n'
        '숫자는 들린 발음을 한글로 적고 어미를 임의로 바꾸지 마세요. 불명료 구간은 [불명료]로 표시하세요.\n'
        '검수는 약 40문장입니다. 저장 후 JSON을 내려받아 운영자에게 전달하세요.\n'
        '자료 제작에 참여했거나 기존 정답을 봤다면 독립 검수라고 확인하지 마세요.\n'
        '음성: Zeroth Korean, CC BY 4.0, https://www.openslr.org/40/\n')
    with zipfile.ZipFile(output / 'reviewer-only.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((output / 'reviewer').rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(output / 'reviewer'))
    auto = dict(status='automated_screening_only_human_review_pending',
        independent_human_review_completed=0, scope='public Eval only; no private Test opened',
        plan_sha256=plan_hash, sample_metrics={}, population_metrics={}, numeric_flags={})
    for label in LABELS:
        auto['population_metrics'][label] = score(predictions[label], rows)
        auto['sample_metrics'][label] = score({r['id']:predictions[label][r['id']] for r in selected}, selected)
        flagged = [r['id'] for r in rows if numeric_notation_candidate(r['reference'], predictions[label][r['id']])]
        auto['numeric_flags'][label] = dict(count=len(flagged), ids=flagged,
            interpretation='Exact numeral-rendering match candidates only; not verified errors or corrected scores.')
    write_json(output / 'organizer/automated-screening.json', auto)
    numeric_ids = set(auto['numeric_flags']['Copy draft']['ids'])
    lines = ['# 공개 Eval 40개 타당성 감사', '',
        '상태: 자동 사전 점검 완료 · 독립 청취 검수 0/40. 공식 데이터와 순위는 변경하지 않았다.', '',
        f'고정 seed: `{SEED}`. 생성기 2종 × 기존 clean/error 2종 × 10개. 모델 출력·오류 크기는 추출에 쓰지 않았다.',
        f'서로 다른 원본 40개, 청취 길이 {seconds/60:.2f}분. 균등 층화 표본이므로 전체 Eval 비율을 직접 추정하지 않는다.', '',
        '## 기존 출력 재사용 결과', '',
        '| 방법 | 전체 409개 Micro CER | 고정 40개 Micro CER | 숫자 표기 일치 후보(전체) |',
        '|---|---:|---:|---:|']
    for label in LABELS:
        lines.append(f'| {label} | {auto["population_metrics"][label]["micro_cer"]:.4f}% | '
                     f'{auto["sample_metrics"][label]["micro_cer"]:.4f}% | {auto["numeric_flags"][label]["count"]} |')
    lines += ['', '숫자 후보는 숫자를 제한된 한글 수사로 바꿨을 때 문장 전체가 원천 정답과 일치하는 경우다. '
        '정답을 보고 일치 여부를 검사한 진단값이며 모델 성능 향상으로 해석하지 않는다. '
        '“2주/이주”처럼 의미가 다를 수 있어 청취 없이 동등 처리하지 않는다.', '', '## Copy 숫자 표기 후보 예시', '']
    for row in sorted(rows, key=lambda r:r['id']):
        if row['id'] in numeric_ids:
            lines += [f'- `{row["id"]}` · 초안: {row["draft"]}', f'  원천 전사: {row["reference"]}']
            if sum(1 for line in lines if line.startswith('- `')) == 5:
                break
    lines += ['', '## 다음 판정', '',
        'reviewer-only.zip만 독립 검수자에게 전달한다. organizer 폴더는 전달하지 않는다. '
        '검수자는 원천 정답과 모델 결과를 보지 않고 전사하고, 이후 초안의 실제 오류·표기 차이·판별 불가와 음성 단서를 기록한다.', '',
        'JSON을 돌려받으면 score 명령으로 동일한 검수 완료·판별 가능 문장에 한해 기존 다섯 출력을 다시 비교한다. '
        '독립 전사와 원천 정답의 불일치는 검토 후보이며 자동으로 원천 정답 오류로 확정하지 않는다. '
        '표본 순위 변동은 전체 리더보드 순위 변동이 아니다. 소표본에서 새 순위를 만들거나 Test에 맞추지 않는다.']
    (output / '사전점검결과.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(dict(output=str(output), sampled=40, seconds=seconds,
        copy_numeric_candidates=len(numeric_ids), human_review_completed=0), ensure_ascii=False))


def rescore(audit, reviews, output):
    plan = json.loads((audit / 'organizer/plan.json').read_text())
    packet = json.loads((audit / 'organizer/items.json').read_text())
    review = json.loads(reviews.read_text())
    if content_digest({k:v for k,v in plan.items() if k!='plan_sha256'}) != plan['plan_sha256']:
        raise ValueError('Frozen plan was modified.')
    if review.get('audit_id') != plan['audit_id'] or review.get('plan_sha256') != plan['plan_sha256']:
        raise ValueError('Review belongs to another frozen sample.')
    if packet['plan_sha256'] != plan['plan_sha256']:
        raise ValueError('Organizer packet mismatch.')
    if content_digest(packet['items']) != plan['organizer_items_sha256']:
        raise ValueError('Frozen organizer items were modified.')
    if not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip():
        raise ValueError('Reviewer identity is required.')
    if review.get('independent_self_declaration') is not True:
        raise ValueError('This audit requires an independent reviewer self-declaration; it is not automatic certification.')
    source = {r['audit_id']: r for r in packet['items']}
    records = review.get('items')
    if not isinstance(records, list) or not records:
        raise ValueError('No human review records. Templates are not completed reviews.')
    seen, usable, excluded, disagreements = set(), [], [], []
    for record in records:
        ident = record.get('id')
        if ident not in source or ident in seen:
            raise ValueError('Duplicate or unknown review ID.')
        seen.add(ident)
        heard = record.get('heard_text_before_draft')
        if not isinstance(heard, str) or not heard.strip() or len(heard)>4000:
            raise ValueError('An audio-first transcript is required.')
        heard = unicodedata.normalize('NFC', heard.strip())
        if record.get('error_status') not in ERROR_STATUSES or record.get('audio_needed') not in ('yes','no','uncertain'):
            raise ValueError('Missing reviewer judgments.')
        if record.get('audio_needed') == 'yes' and not str(record.get('evidence', '')).strip():
            raise ValueError('Audio-needed judgments require a concrete audio cue.')
        row = source[ident]
        if '[불명료]' in heard or record['error_status']=='uncertain' or not normalize(heard):
            excluded.append(ident)
            continue
        usable.append(dict(id=row['id'], reference=heard, draft=row['draft'], source=row['source']))
        if normalize(heard) != normalize(row['reference']):
            disagreements.append(dict(audit_id=ident, id=row['id'], source_reference=row['reference'],
                independent_transcription=heard, status='disagreement_not_adjudicated_source_error'))
    if not usable:
        raise ValueError('No clear, reviewed items to score.')
    old = [dict(id=r['id'], reference=r['reference'], draft=r['draft'], source=r['source'])
           for r in packet['items'] if r['id'] in {item['id'] for item in usable}]
    by_id = {r['id']:r for r in packet['items']}
    result = dict(status='provisional_human_reference_sensitivity_not_official_ranking',
        plan_sha256=plan['plan_sha256'], review_sha256=digest(reviews), reviewer=review['reviewer'],
        independence='self_declared_not_automatically_verified', reviewed=len(seen), usable=len(usable),
        total_selected=40, excluded_audit_ids=excluded, reference_disagreements=disagreements,
        judgments=dict(Counter(r['error_status'] for r in records)),
        audio_needed_judgments=dict(Counter(r['audio_needed'] for r in records)), measurements={})
    for label in LABELS:
        predictions = {r['id']:by_id[r['id']]['predictions'][label] for r in usable}
        result['measurements'][label] = dict(original_references_same_subset=score(predictions, old),
                                           audio_first_human_references=score(predictions, usable))
    result['limitations'] = ['Partial/stratified sample is not the full Eval leaderboard.',
        'Single human transcript is provisional, not adjudicated ground truth.',
        'Audio-needed judgments do not prove a causal input effect.',
        'No private Test, official references, or official scores were changed.']
    write_json(output, result)
    print(json.dumps(dict(reviewed=len(seen), usable=len(usable), disagreements=len(disagreements),
        output=str(output)), ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build_parser = sub.add_parser('build')
    for arg in ('public','omni','comparison','output'):
        build_parser.add_argument('--'+arg, type=Path, required=True)
    score_parser = sub.add_parser('score')
    for arg in ('audit','reviews','output'):
        score_parser.add_argument('--'+arg, type=Path, required=True)
    args = vars(parser.parse_args())
    command = args.pop('command')
    (build if command=='build' else rescore)(**args)


if __name__ == '__main__':
    main()
