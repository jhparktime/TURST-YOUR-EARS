"""Build one public eval hour and four private test hours of Korean correction.

Gold is always external upstream text. Tokenization and real-word phonetic
neighbors construct synthetic drafts, not certified ASR confusions.
"""
import argparse
import hashlib
import io
import itertools
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from scripts.build_dataset import digest, write_json
from scripts.import_pilot160 import make_variant, write_csv
from scripts.zeroth_source import DATASET, REVISION, FILES, batches
from server.scoring import VERSION, normalize, score, validate_manifest

NAME = 'tye-ko-5h-v1'
SEED = 20261015
LABELS = ['clean', 'single', 'multiple']
TARGETS = {'eval': 3600, 'test': 14400}


def key(value):
    return hashlib.sha256(f'{SEED}:{value}'.encode()).hexdigest()


def jamo(word):
    values = []
    for char in word:
        n = ord(char) - 0xAC00
        if not 0 <= n < 11172:
            raise ValueError('Only precomposed Hangul words are eligible.')
        values.extend([n // 588, n // 28 % 21, n % 28])
    return tuple(values)


def pronunciation_key(word):
    # Conservative homophone exclusions, not a complete Korean G2P model.
    values = list(jamo(word))
    for i in range(1, len(values), 3):
        if values[i] in (1, 5): values[i] = 1  # ae/e
        if values[i] in (9, 10, 15): values[i] = 10  # wae/oe/we
    coda = values[-1]
    if coda in (1, 2, 24): values[-1] = 1
    if coda in (7, 19, 20, 22, 23, 25, 27): values[-1] = 7
    if coda in (17, 26): values[-1] = 17
    return tuple(values)


def particle_class(word):
    coda = (ord(word[-1]) - 0xAC00) % 28
    return 'vowel' if coda == 0 else 'rieul' if coda == 8 else 'other_coda'


def noun_tokens(text, kiwi):
    return [{'word': t.form, 'start': t.start, 'end': t.start + t.len, 'tag': t.tag}
        for t in kiwi.tokenize(text)
        if t.tag in ('NNG', 'NNP') and 2 <= len(t.form) <= 6
        and re.fullmatch('[가-힣]+', t.form) and text[t.start:t.start + t.len] == t.form]


def build_neighbors(frequencies):
    """Nearest attested nouns differing in one, or at most two, Hangul components."""
    vocab = sorted(word for word, count in frequencies.items() if count >= 2)
    neighbors = defaultdict(set)
    for radius in (1, 2):
        buckets = defaultdict(list)
        for word in vocab:
            parts = jamo(word)
            for positions in itertools.combinations(range(len(parts)), radius):
                masked = list(parts)
                for position in positions: masked[position] = -1
                buckets[(positions, tuple(masked))].append(word)
        additions = defaultdict(set)
        for words in buckets.values():
            for a, b in itertools.combinations(words, 2):
                if particle_class(a) == particle_class(b) and pronunciation_key(a) != pronunciation_key(b):
                    additions[a].add(b); additions[b].add(a)
        for word, values in additions.items():
            if not neighbors[word]: neighbors[word].update(values)
    return {word: sorted(values, key=lambda v: (-frequencies[v], v))[:20]
            for word, values in neighbors.items()}


def variants_for(text, tokens, neighbors):
    options = []
    for token in tokens:
        choices = neighbors.get(token['word'], [])
        if choices:
            replacement = choices[int(key(f"{text}:{token['start']}"), 16) % len(choices)]
            options.append({'start': token['start'], 'end': token['end'], 'replacement': replacement})
    random.Random(key(text)).shuffle(options)
    variants = {}
    for count, label in ((1, 'single'), (2, 'multiple')):
        for chosen in itertools.islice(itertools.combinations(options, count), 100):
            row = make_variant('candidate', text, chosen)
            try:
                result = score({'candidate': row['draft']}, [row])
            except ValueError:
                continue
            if result['restoration_rate'] == 0 and result['harmful_edit_rate'] == 0:
                variants[label] = row
                break
    if len(variants) == 2:
        variants['clean'] = make_variant('candidate', text, [])
        return variants
    return None


def prepare(index_path, exposed_path, work):
    from kiwipiepy import Kiwi
    index = json.loads(index_path.read_text())
    if (index['dataset'], index['revision']) != (DATASET, REVISION):
        raise ValueError('Wrong upstream index revision.')
    exposed = json.loads(exposed_path.read_text())
    exposed_texts = {normalize(r['reference']) for r in exposed}
    all_text, eligible_audio = {}, []
    for row in index['items']:
        text = row['reference']
        if not 4 <= row['duration_seconds'] <= 22 or not 20 <= len(normalize(text)) <= 180:
            continue
        if sum('가' <= c <= '힣' for c in text) / max(1, sum(c.isalpha() for c in text)) < .9:
            continue
        # Avoid padding the five-hour claim with long source silences.
        if row.get('active_fraction', 1) < .45 or max(row.get('leading_silence', 0), row.get('trailing_silence', 0)) > 3:
            continue
        all_text[text] = None
        eligible_audio.append(row)
    kiwi = Kiwi(num_workers=2)
    tokenized, frequencies, words_by_sentence = {}, Counter(), defaultdict(set)
    for i, text in enumerate(sorted(all_text)):
        tokens = noun_tokens(text, kiwi)
        tokenized[text] = tokens
        words_by_sentence[normalize(text)].update(t['word'] for t in tokens)
        if i and i % 1000 == 0: print(f'Tokenized {i} source texts', flush=True)
    for words in words_by_sentence.values(): frequencies.update(words)
    neighbors = build_neighbors(frequencies)
    write_json(work / 'private-neighbors.json', neighbors)
    variants, excluded = {}, Counter()
    for i, (text, tokens) in enumerate(tokenized.items()):
        if normalize(text) in exposed_texts:
            excluded['previously_exposed_text'] += 1; continue
        found = variants_for(text, tokens, neighbors)
        if found: variants[text] = found
        else: excluded['no_two_valid_real_word_spans'] += 1
        if i and i % 1000 == 0: print(f'Checked {i} source-text corruption plans', flush=True)
    candidates = [r for r in eligible_audio if r['reference'] in variants]
    write_json(work / 'candidate-variants.json', variants)
    write_json(work / 'candidate-recordings.json', candidates)
    write_json(work / 'previous-exposures.json', exposed)
    write_json(work / 'plan.json', {'name': NAME, 'seed': SEED, 'source_revision': REVISION,
        'source_files': index['source_files'],
        'targets_seconds': TARGETS, 'index_sha256': digest(index_path),
        'candidates_sha256': digest(work / 'candidate-recordings.json'),
        'variants_sha256': digest(work / 'candidate-variants.json'),
        'neighbors_sha256': digest(work / 'private-neighbors.json'),
        'exposures_sha256': digest(work / 'previous-exposures.json'),
        'eligible_texts': len(variants), 'eligible_recordings': len(candidates), 'excluded_texts': dict(excluded)})
    print(json.dumps({'eligible_texts': len(variants), 'recordings': len(candidates), 'excluded': dict(excluded)}), flush=True)


def duration_select(rows, target):
    """Unique sentences, diversified speakers, whole utterances; never pad audio."""
    by_text = defaultdict(list)
    for row in rows: by_text[normalize(row['reference'])].append(row)
    used_speakers = Counter()
    unique = []
    for text in sorted(by_text, key=key):
        best = min(by_text[text], key=lambda r: (used_speakers[r['speaker_id']], key(r['source_id'])))
        unique.append(best); used_speakers[best['speaker_id']] += 1
    if sum(r['duration_seconds'] for r in unique) < target:
        raise ValueError(f'Only {sum(r["duration_seconds"] for r in unique):.1f}s of unique eligible speech for {target}s target.')
    # Random deterministic priority, then use the closest remaining duration near the endpoint.
    unique.sort(key=lambda r: key(r['source_id']))
    selected, duration = [], 0
    while duration < target:
        remaining = target - duration
        if remaining < 30:
            pos = min(range(len(unique)), key=lambda i: abs(unique[i]['duration_seconds'] - remaining))
            row = unique.pop(pos)
            selected.append(row); duration += row['duration_seconds']
            if duration >= target or abs(duration - target) < .3: break
        else:
            row = unique.pop(0)
            selected.append(row); duration += row['duration_seconds']
    return selected


def assign_conditions(rows, split):
    """All labels share the two-error-eligible pool; balance duration in triples."""
    rows = sorted(rows, key=lambda r: (r['samples'], key(r['source_id'])))
    assigned = []
    for i in range(0, len(rows), 3):
        labels = LABELS.copy()
        random.Random(f'{SEED}:{split}:{i}').shuffle(labels)
        assigned.extend((row, label) for row, label in zip(rows[i:i + 3], labels))
    return sorted(assigned, key=lambda pair: key(pair[0]['source_id']))


def select(work):
    import difflib
    rows = json.loads((work / 'candidate-recordings.json').read_text())
    previous = json.loads((work / 'previous-exposures.json').read_text())
    exposed = [normalize(r['reference']) for r in previous]
    speakers = sorted({r['speaker_id'] for r in rows}, key=key)
    # Entire speaker groups stay in one split. Keep enough alternate readers for a text.
    eval_speakers = set(speakers[:max(20, len(speakers) // 4)])
    evaluation = duration_select([r for r in rows if r['speaker_id'] in eval_speakers], TARGETS['eval'])
    eval_texts = [normalize(r['reference']) for r in evaluation]
    blocked = eval_texts + exposed
    accepted_text = {}
    for row in rows:
        if row['speaker_id'] in eval_speakers: continue
        text = normalize(row['reference'])
        if text in accepted_text: continue
        accepted_text[text] = not any(
            difflib.SequenceMatcher(None, text, t, autojunk=False).quick_ratio() >= .85 and
            difflib.SequenceMatcher(None, text, t, autojunk=False).ratio() >= .85 for t in blocked)
    test = duration_select([r for r in rows if r['speaker_id'] not in eval_speakers
                           and accepted_text.get(normalize(r['reference']), False)], TARGETS['test'])
    selection = {s: [{'source_id': r['source_id'], 'condition': c} for r, c in assign_conditions(chosen, s)]
                 for s, chosen in [('eval', evaluation), ('test', test)]}
    write_json(work / 'selection.json', selection)
    print(json.dumps({s: {'utterances': len(chosen), 'seconds': sum(r['duration_seconds'] for r in chosen),
        'speakers': len({r['speaker_id'] for r in chosen})} for s, chosen in [('eval', evaluation), ('test', test)]}), flush=True)
    return selection


def export(cache, work, public, private):
    import numpy as np
    import soundfile as sf
    if public.resolve() == private.resolve() or public.resolve() in private.resolve().parents or private.resolve() in public.resolve().parents:
        raise ValueError('Public and private folders must be non-nested.')
    if public.exists() or private.exists(): raise ValueError('Refusing to overwrite an existing release.')
    plan = json.loads((work / 'plan.json').read_text())
    for name, field in [('candidate-recordings.json', 'candidates_sha256'), ('candidate-variants.json', 'variants_sha256'),
                        ('private-neighbors.json', 'neighbors_sha256'), ('previous-exposures.json', 'exposures_sha256')]:
        if digest(work / name) != plan[field]: raise ValueError('Prepared candidate data changed.')
    selection = select(work)
    candidates = {r['source_id']: r for r in json.loads((work / 'candidate-recordings.json').read_text())}
    variants = json.loads((work / 'candidate-variants.json').read_text())
    selected = {r['source_id']: (split, r['condition']) for split, rows in selection.items() for r in rows}
    public.mkdir(parents=True); private.mkdir(parents=True)
    refs, inputs, checksums = defaultdict(list), defaultdict(list), defaultdict(dict)
    provenance = []
    for filename, offset, source in batches(cache, names=plan['source_files']):
        if source['id'] not in selected: continue
        split, condition = selected[source['id']]
        candidate = candidates[source['id']]
        payload = source['audio']['bytes']
        if (filename, offset) != (candidate['source_file'], candidate['source_row']) or hashlib.sha256(payload).hexdigest() != candidate['source_audio_sha256']:
            raise ValueError('Selected upstream audio does not match its source index.')
        samples, rate = sf.read(io.BytesIO(payload), dtype='int16', always_2d=True)
        if rate != 16000 or samples.shape != (candidate['samples'], 1) or not np.any(samples):
            raise ValueError('Invalid selected source audio.')
        ident = key(NAME + ':' + source['id'])[:16]
        folder = (public if split == 'eval' else private) / split
        path = folder / 'audio' / f'{ident}.wav'; path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(path, samples, rate, subtype='PCM_16')
        recovered, rr = sf.read(path, dtype='int16', always_2d=True)
        if rr != rate or not np.array_equal(samples, recovered): raise ValueError('PCM audio changed during WAV export.')
        row = variants[candidate['reference']][condition] | {'id': ident}
        refs[split].append(row)
        inputs[split].append({'id': ident, 'audio': f'audio/{ident}.wav', 'draft': row['draft']})
        checksums[split][ident] = digest(path)
        provenance.append(candidate | {'id': ident, 'split': split, 'condition': condition,
            'audio_sha256': digest(path), 'pcm_sha256': hashlib.sha256(samples.astype('<i2').tobytes()).hexdigest()})
        if len(provenance) % 300 == 0: print(f'Exported {len(provenance)} unique recordings', flush=True)
    report = {'name': NAME, 'protocol': VERSION, 'status': 'pilot_pending_independent_listening',
        'source': DATASET, 'source_revision': REVISION, 'license': 'CC-BY-4.0',
        'source_files': {name: {'bytes': size, 'sha256': checksum} for name, size, checksum in FILES if name in plan['source_files']},
        'human_listening_review': 'not_performed', 'blind_asr_crosscheck': 'not_performed',
        'gold_policy': 'unchanged_upstream_text_NFC_only', 'speaker_disjointness': 'checked_upstream_speaker_ids',
        'draft_recipe': 'attested_noun_nearest_one_or_two_jamo_component_substitutions',
        'splits': {}, 'target_duration_seconds': TARGETS,
        'limitations': ['Source transcripts and phonetic distinguishability are not independently human audited.',
            'Synthetic real-word substitutions do not represent measured ASR confusion probabilities.',
            'Simplified homophone exclusions do not implement full Korean phonology.',
            'Public upstream audio/text may be searchable or present in model pretraining.',
            'Official train/test partitions are pooled then repartitioned by speaker and sentence.',
            'Durations include natural source silences; no padding, cropping, or speed changes.',
            'Test answers and source mappings remain private; public source data cannot be made secret.']}
    for split in ('eval', 'test'):
        folder = (public if split == 'eval' else private) / split
        rows = sorted(refs[split], key=lambda r: r['id'])
        input_rows = sorted(inputs[split], key=lambda r: r['id'])
        if len(rows) != len(selection[split]): raise ValueError('Missing selected source recordings.')
        manifest = {'name': NAME + '-' + split, 'protocol': VERSION, 'conditions': LABELS, 'items': rows}
        validate_manifest(manifest)
        refpath = folder / 'references.json' if split == 'eval' else private / 'test-references.json'
        write_json(refpath, manifest)
        write_json(folder / 'inputs.json', {'name': NAME + '-' + split, 'items': input_rows})
        write_json(folder / 'audio-checksums.json', checksums[split])
        write_csv(folder / 'copy-draft.csv', ['id', 'prediction'], [{'id': r['id'], 'prediction': r['draft']} for r in rows])
        scores = score({r['id']: r['draft'] for r in rows}, rows)
        oracle = score({r['id']: r['reference'] for r in rows}, rows)
        if scores['restoration_rate'] != 0 or scores['harmful_edit_rate'] != 0 or oracle['macro_cer'] != 0 or oracle['restoration_rate'] != 100:
            raise ValueError('Copy/oracle controls failed.')
        write_json(folder / 'copy-draft.scores.json', scores)
        part = [r for r in provenance if r['split'] == split]
        report['splits'][split] = {'visibility': 'public' if split == 'eval' else 'private',
            'utterances': len(rows), 'duration_seconds': sum(r['samples'] for r in part) / 16000,
            'speakers': len({r['speaker_id'] for r in part}), 'conditions': dict(Counter(r['condition'] for r in rows)),
            'copy_macro_cer': scores['macro_cer'], 'inputs_sha256': digest(folder / 'inputs.json'),
            'references_sha256': digest(refpath)}
    write_json(public / 'metadata.json', report)
    write_json(private / 'metadata.json', report)
    write_json(private / 'provenance.json', sorted(provenance, key=lambda r: r['id']))
    for name in ('plan.json', 'selection.json', 'private-neighbors.json', 'previous-exposures.json'):
        (private / name).write_bytes((work / name).read_bytes())
    review = [{'id': r['id'], 'split': r['split'], 'audio': f"{r['split']}/audio/{r['id']}.wav",
        'upstream_transcript': r['reference'], 'reviewer_a_transcript': '', 'reviewer_b_transcript': '',
        'agreement': '', 'target_audibility': '', 'status': 'pending'} for r in provenance]
    write_csv(private / 'listening-review.csv', list(review[0]), review)
    notice = ('Zeroth-Korean (OpenSLR SLR40), Lucas Jo (Atlas Guide) & Wonkyum Lee (Gridspace).\n'
        'CC BY 4.0: https://creativecommons.org/licenses/by/4.0/\n'
        'Original: https://www.openslr.org/40/\n'
        f'Mirror: https://huggingface.co/datasets/{DATASET}/tree/{REVISION}\n'
        'Changes: lossless FLAC decoding to mono 16 kHz PCM16 WAV; identical PCM samples; '
        'NFC-only reference text; new speaker/sentence splits; sparse synthetic draft substitutions.\n'
        'Upstream authors do not endorse this derivative. Independent listening has not been performed.\n')
    for folder in (public, private): (folder / 'NOTICE').write_text(notice, encoding='utf-8')
    (public / 'README.md').write_text(card(report), encoding='utf-8')
    (private / 'README.md').write_text('# 비공개 test · 운영자 전용\n\n'
        '`test-references.json`을 채점 서버 REFERENCE_PATH에 지정하세요. '
        '`test/`는 음성·초안 입력, 루트의 정답·대응표·오류 사전·검수표는 운영자 전용입니다. '
        '이 묶음 전체를 공개 저장소에 올리지 마세요. 검수 상태는 미검수입니다.\n', encoding='utf-8')
    for folder in (public, private):
        write_json(folder / 'release-lock.json', {'name': NAME, 'sha256': {
            str(p.relative_to(folder)): digest(p) for p in sorted(folder.rglob('*')) if p.is_file()}})
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return report


def card(report):
    e, t = report['splits']['eval'], report['splits']['test']
    return f'''# Trust Your Ears · Korean 5-hour correction v1

**독립 청취 미검수 데이터셋**. 모델 입력은 한국어 음성 + 전사 초안이며 출력은 전체 교정 전사입니다.

| 분할 | 공개 범위 | 음성 수 | 실제 시간(초) | 화자 수 | 조건 수 |
|---|---|---:|---:|---:|---|
| eval | 음성·초안·정답 공개 | {e['utterances']} | {e['duration_seconds']:.3f} | {e['speakers']} | {e['conditions']} |
| test | 운영자 비공개 | {t['utterances']} | {t['duration_seconds']:.3f} | {t['speakers']} | {t['conditions']} |

공개 eval은 개발·튜닝·재현용, 비공개 test는 최종 리더보드용입니다.
원본 발화 하나당 초안 하나를 배정합니다. 같은 문장의 다른 화자 녹음도 중복 계산하지 않습니다.
자연 무음은 포함하지만 재생 시간을 늘리는 패딩·반복·속도 변경·새 합성 음성은 사용하지 않습니다.

원천 Zeroth-Korean의 공식 train/test를 합친 뒤 화자와 문장 기준으로 새로 분할했습니다.
test에는 공개 eval 및 이전 공개 파일럿과 겹치거나 유사도 0.85 이상인 문장을 넣지 않습니다.
원천 화자 ID를 따르며 실제 신원을 별도로 확인한 것은 아닙니다.

정답은 고정 버전 원천의 text 필드를 NFC 정규화한 값입니다. 숫자·약어·간투사를 자동으로
고쳐 쓰거나, ASR/LLM 출력으로 정답을 대체하지 않습니다. 음성은 원천 FLAC에서 복호화한
PCM16 샘플을 그대로 WAV에 저장합니다. 원천 파일 해시와 PCM 일치를 검사합니다.

초안만 0/1/2곳 치환합니다. Kiwi가 찾은 명사 중 원문 구간이 정확히 일치하고 원천에
두 문장 이상 등장하는 단어를 사용합니다. 같은 길이, 같은 조사 결합 유형(무받침/ㄹ/그 외 받침)이고 한글 자모 성분
하나가 다른 실제 명사를 우선 사용하고, 없으면 두 성분까지 허용합니다. ㅐ/ㅔ 등 일부 동음 후보는 제외하지만 완전한
한국어 발음 모델은 아니므로 사람의 청각적 구별 검수가 필요합니다.
Clean·Single·Multiple 모두 두 오류를 만들 수 있는 동일 후보 집합에서 배정합니다.
문장 길이 순으로 묶어 조건별 길이 편향을 줄이며, 정상 문자가 사이에 남는 독립 구간만 씁니다.

이것은 실제 ASR 혼동 확률을 관측한 데이터가 아닌 **합성 실단어 치환**입니다.
문맥만으로 고칠 수 있는 경우도 있으며 text-only와 audio-only를 함께 비교해야 합니다.
원천 전사 오류·누락 간투사·발화 잘림 여부와 치환 단어 식별 가능성을 청취로 검수해야 합니다.
공개 원천 자료이므로 원문 검색·사전학습 오염 가능성이 있고 비공개 정답만으로 해결되지 않습니다.

채점은 `ko-correction-v1`: NFC·영문 소문자·공백 및 지정 문장부호 제거 후 한글 음절 CER,
세 조건 동일 비중 Macro CER를 사용합니다. 숫자 읽기·alias를 자동 동치화하지 않습니다.
복원률·정상 구간 훼손률·Clean 변경률을 함께 보고합니다.
Copy draft Macro CER는 eval {e['copy_macro_cer']:.6f}%, test {t['copy_macro_cer']:.6f}%입니다.
정답 제출 CER 0%는 채점기 검사이며 음성 모델의 실험 결과가 아닙니다.

`eval/inputs.json`은 id/audio/draft만 포함하고 audio는 해당 JSON 기준 상대 경로입니다.
`eval/references.json`, `eval/copy-draft.csv`와 점수를 제공합니다.
비공개 test 정답·원천 대응표·검수표는 별도 운영자 묶음에만 있습니다.
출처·CC BY 4.0 저작자 표시·변경 사항은 NOTICE를 확인하세요.
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'export'])
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--index', type=Path)
    parser.add_argument('--exposures', type=Path)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--public', type=Path)
    parser.add_argument('--private', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        if not args.index or not args.exposures: parser.error('prepare needs --index and --exposures')
        prepare(args.index, args.exposures, args.work)
    else:
        if not args.cache or not args.public or not args.private: parser.error('export needs --cache, --public and --private')
        export(args.cache, args.work, args.public, args.private)


if __name__ == '__main__': main()
