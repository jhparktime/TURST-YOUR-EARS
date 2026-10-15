"""Pool both Zeroth correction deliveries and repartition without speaker/text leakage.

All source recordings are retained in the private source-pool. The experimental
splits use one recording per sentence and quarantine unused/overlapping readings.
Selection never reads ASR predictions, human quality ratings, or model scores.
"""
import argparse
import csv
import difflib
import hashlib
import json
import os
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from scripts.baseline import load_inputs
from scripts.build_dataset import digest, write_json
from scripts.build_five_hour_dataset import noun_tokens, variants_for
from scripts.import_pilot160 import write_csv
from server.scoring import VERSION, normalize, score, validate_manifest

NAME = 'tye-ko-merged-v1'
SEED = 20261016
LABELS = ['clean', 'single', 'multiple']


def priority(value):
    return hashlib.sha256(f'{NAME}:{SEED}:{value}'.encode()).hexdigest()


def near(a, b):
    if 2 * min(len(a), len(b)) / (len(a) + len(b)) < .85:
        return False
    m = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return m.quick_ratio() >= .85 and m.ratio() >= .85


def select_duration(rows, target):
    """One reader per sentence; deterministic whole-utterance selection."""
    groups = defaultdict(list)
    for row in rows:
        groups[normalize(row['reference'])].append(row)
    chosen, speakers = [], Counter()
    for text in sorted(groups, key=priority):
        row = min(groups[text], key=lambda r: (speakers[r['speaker_id']], priority(r['source_id'])))
        chosen.append(row)
        speakers[row['speaker_id']] += 1
    if sum(r['samples'] for r in chosen) < target * 16000:
        raise ValueError('Not enough unique whole speech for the requested target.')
    chosen.sort(key=lambda r: priority(r['source_id']))
    selected, samples = [], 0
    while samples < target * 16000:
        remaining = target * 16000 - samples
        pos = (min(range(len(chosen)), key=lambda i: abs(chosen[i]['samples'] - remaining))
               if remaining < 30 * 16000 else 0)
        row = chosen.pop(pos)
        selected.append(row)
        samples += row['samples']
        if abs(samples - target * 16000) < .3 * 16000:
            break
    return selected


def balanced_conditions(rows, split):
    result = []
    ordered = sorted(rows, key=lambda r: (r['samples'], priority(r['source_id'])))
    for i in range(0, len(ordered), 3):
        labels = LABELS.copy()
        random.Random(f'{NAME}:{SEED}:{split}:{i}').shuffle(labels)
        result.extend(zip(ordered[i:i + 3], labels))
    return result


def link_audio(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copyfile(source, target)


def lock(folder):
    write_json(folder / 'release-lock.json', {'name': NAME, 'sha256': {
        str(p.relative_to(folder)): digest(p) for p in sorted(folder.rglob('*'))
        if p.is_file() and p.name != 'release-lock.json'}})


def load_delivery(public, private, tag):
    provenance = json.loads((private / 'provenance.json').read_text())
    indexed = {r['id']: r for r in provenance}
    if len(indexed) != len(provenance):
        raise ValueError('Duplicate delivery provenance ID.')
    result = []
    splits = ('eval', 'test') if tag == 'five-hour' else ('train', 'eval')
    for split in splits:
        folder = (private if split == 'test' else public) / split
        refpath = (private / 'test-references.json' if split == 'test' else
                   private / 'eval-references.json' if tag == 'incoming' and split == 'eval' else
                   folder / 'references.json')
        refs = {r['id']: r for r in validate_manifest(json.loads(refpath.read_text()))}
        inputs = load_inputs(folder / 'inputs.json')
        checksums = json.loads((folder / 'audio-checksums.json').read_text())
        if {r['id'] for r in inputs} != set(refs):
            raise ValueError('Delivery input/reference coverage mismatch.')
        for row in inputs:
            p = indexed[row['id']]
            ref = refs[row['id']]
            path = (folder / row['audio']).resolve()
            if (row['draft'] != ref['draft'] or p['reference'] != ref['reference'] or
                    p['split'] != split or digest(path) != p['audio_sha256'] or
                    checksums[row['id']] != p['audio_sha256']):
                raise ValueError('Delivery content changed.')
            result.append(p | ref | {'origin': tag, 'origin_split': split,
                'origin_id': row['id'], '_audio': str(path)})
    if len(result) != len(provenance):
        raise ValueError('Incomplete delivery coverage.')
    return result


def merge(old_public, old_private, incoming_public, incoming_private, public, private):
    from kiwipiepy import Kiwi

    public, private = public.resolve(), private.resolve()
    if public == private or public in private.parents or private in public.parents:
        raise ValueError('Public/private outputs must be separate non-nested folders.')
    if public.exists() or private.exists():
        raise ValueError('Refusing to overwrite an existing merged delivery.')
    old = load_delivery(old_public, old_private, 'five-hour')
    incoming = load_delivery(incoming_public, incoming_private, 'incoming')
    pool = old + incoming
    for field in ('id', 'source_id', 'pcm_sha256'):
        if len({r[field] for r in pool}) != len(pool):
            raise ValueError(f'The two input deliveries repeat a {field}.')
    print(f'Pooled {len(pool)} verified source recordings', flush=True)

    # Public 5h eval and incoming labelled pilot train are already exposed.
    # Their speakers cannot be assigned to private test in the new release.
    public_rows = [r for r in pool if (r['origin'], r['origin_split']) in
                   {('five-hour', 'eval'), ('incoming', 'train')}]
    eval_speakers = {r['speaker_id'] for r in old if r['origin_split'] == 'eval'}
    exposed_speakers = {r['speaker_id'] for r in public_rows}
    test_speakers = {r['speaker_id'] for r in pool} - exposed_speakers
    previous = json.loads((old_private / 'previous-exposures.json').read_text())
    exposed_texts = sorted({normalize(r['reference']) for r in previous + public_rows})
    neighbors = {
        'five-hour': json.loads((old_private / 'private-neighbors.json').read_text()),
        'incoming': json.loads((incoming_private / 'private-neighbors.json').read_text())}
    kiwi = Kiwi(num_workers=2)
    variant_cache = {}

    def variants(row):
        key = (row['origin'], row['reference'])
        if key not in variant_cache:
            variant_cache[key] = variants_for(row['reference'],
                noun_tokens(row['reference'], kiwi), neighbors[row['origin']])
        return variant_cache[key]

    test_candidates = []
    for r in pool:
        if r['speaker_id'] not in test_speakers:
            continue
        text = normalize(r['reference'])
        if any(near(text, t) for t in exposed_texts):
            continue
        if variants(r):
            test_candidates.append(r)
    test = select_duration(test_candidates, 14400)
    test_texts = {normalize(r['reference']) for r in test}
    evaluation = select_duration([r for r in pool if r['speaker_id'] in eval_speakers
        and variants(r) and not any(near(normalize(r['reference']), t) for t in test_texts)], 3600)
    blocked = test_texts | {normalize(r['reference']) for r in evaluation}
    selected_source = {r['source_id'] for r in test + evaluation}
    train, reserved = [], []
    train_texts = set()
    for index, row in enumerate(sorted(pool, key=lambda r: priority(r['source_id']))):
        if row['source_id'] in selected_source:
            continue
        text = normalize(row['reference'])
        if row['speaker_id'] in test_speakers | eval_speakers:
            reason = 'heldout_speaker_surplus_or_alternate_reading'
        elif text in blocked:
            reason = 'exact_sentence_in_eval_or_test'
        elif any(near(text, t) for t in blocked):
            reason = 'near_sentence_in_eval_or_test'
        elif text in train_texts:
            reason = 'alternate_reading_in_train'
        else:
            train.append(row); train_texts.add(text)
            continue
        reserved.append({'source_id': row['source_id'], 'origin_id': row['origin_id'],
                         'reason': reason})
    selected = {'train': [(r, r['condition']) for r in train],
                'eval': balanced_conditions(evaluation, 'eval'),
                'test': balanced_conditions(test, 'test')}
    if not train:
        raise ValueError('Repartition left no leakage-free training data.')
    public.mkdir(parents=True); private.mkdir(parents=True)
    # Keep every input, including alternate readers and time surplus, intact.
    pool_receipt = []
    for row in pool:
        ident = row['origin_id']
        path = private / 'source-pool' / 'audio' / f'{ident}.wav'
        link_audio(Path(row['_audio']), path)
        pool_receipt.append({k: v for k, v in row.items() if not k.startswith('_')} |
            {'audio': f'source-pool/audio/{ident}.wav'})
    write_json(private / 'source-pool.json', pool_receipt)
    write_json(private / 'reserved.json', reserved)
    write_json(private / 'previous-exposures.json', previous)
    provenance, summary = [], {}
    for split, assignments in selected.items():
        refs, inputs, checksums = [], [], {}
        folder = (private if split == 'test' else public) / split
        for row, condition in assignments:
            ident = priority(split + ':' + row['source_id'])[:16]
            # Training keeps the incoming draft unchanged. Held-out conditions
            # are balanced on length triples using the same corruption recipe.
            v = ({k: row[k] for k in ('reference', 'draft', 'edits', 'condition')}
                 if split == 'train' else variants(row)[condition])
            ref = v | {'id': ident}
            target = folder / 'audio' / f'{ident}.wav'
            link_audio(Path(row['_audio']), target)
            refs.append(ref)
            inputs.append({'id': ident, 'audio': f'audio/{ident}.wav', 'draft': ref['draft']})
            checksums[ident] = digest(target)
            provenance.append({k: v for k, v in row.items() if not k.startswith('_')} |
                ref | {'split': split, 'origin_id': row['origin_id'], 'audio_sha256': checksums[ident]})
        refs.sort(key=lambda r: r['id']); inputs.sort(key=lambda r: r['id'])
        manifest = {'name': f'{NAME}-{split}', 'protocol': VERSION,
                    'conditions': LABELS, 'items': refs}
        validate_manifest(manifest)
        refpath = private / 'test-references.json' if split == 'test' else folder / 'references.json'
        write_json(refpath, manifest)
        write_json(folder / 'inputs.json', {'name': f'{NAME}-{split}', 'items': inputs})
        write_json(folder / 'audio-checksums.json', dict(sorted(checksums.items())))
        write_csv(folder / 'copy-draft.csv', ['id', 'prediction'],
                  [{'id': r['id'], 'prediction': r['draft']} for r in refs])
        copied = score({r['id']: r['draft'] for r in refs}, refs)
        oracle = score({r['id']: r['reference'] for r in refs}, refs)
        if copied['restoration_rate'] != 0 or copied['harmful_edit_rate'] != 0 or oracle['macro_cer'] != 0:
            raise ValueError('Merged scoring controls failed.')
        write_json(folder / 'copy-draft.scores.json', copied)
        summary[split] = {'visibility': 'private' if split == 'test' else 'public',
            'utterances': len(refs), 'duration_seconds': sum(r['samples'] for r, _ in assignments) / 16000,
            'speakers': len({r['speaker_id'] for r, _ in assignments}),
            'conditions': dict(Counter(r['condition'] for r in refs)),
            'copy_macro_cer': copied['macro_cer'],
            'inputs_sha256': digest(folder / 'inputs.json'), 'references_sha256': digest(refpath)}
        print(f'{split}: {summary[split]}', flush=True)
    report = {'name': NAME, 'protocol': VERSION, 'seed': SEED,
        'status': 'pilot_pending_independent_listening', 'human_listening_review': 'not_performed',
        'source': 'kresnik/zeroth_korean', 'source_revision': '1fe937899f828af822293d05e086200946088bdf',
        'license': 'CC-BY-4.0', 'gold_policy': 'unchanged_upstream_text_NFC_only',
        'pool': {'recordings': len(pool), 'seconds': sum(r['samples'] for r in pool) / 16000,
                 'speakers': len({r['speaker_id'] for r in pool})},
        'splits': summary, 'reserved': {'recordings': len(reserved),
            'reasons': dict(Counter(r['reason'] for r in reserved))},
        'selection_used_asr_predictions': False, 'target_duration_seconds': {'eval': 3600, 'test': 14400},
        'policy': 'Expose old public/pilot speakers only in train/eval; select private test from the remaining speakers; exclude identical/near sentences across splits; archive every unused reading.',
        'limitations': ['Independent listening pending.', 'Public-source pretraining/search contamination remains.',
            'Synthetic noun substitutions are not measured ASR confusions.',
            'Training condition counts need not be balanced; held-out counts differ by at most one.',
            'Source-pool and reserved recordings must not be used for training or prompt tuning.'],
        'input_manifest_sha256': {f'{tag}-{name}': digest(root / name) for tag, root in
            [('old-public', old_public), ('old-private', old_private),
             ('incoming-public', incoming_public), ('incoming-private', incoming_private)]
            for name in ['metadata.json', 'release-lock.json']}}
    write_json(private / 'provenance.json', sorted(provenance, key=lambda r: r['id']))
    write_csv(private / 'listening-review.csv', ['id', 'split', 'upstream_transcript',
        'reviewer_a_transcript', 'reviewer_b_transcript', 'status'],
        [{'id': r['id'], 'split': r['split'], 'upstream_transcript': r['reference'],
          'reviewer_a_transcript': '', 'reviewer_b_transcript': '', 'status': 'pending'} for r in provenance])
    for root in (public, private):
        write_json(root / 'metadata.json', report)
        (root / 'NOTICE').write_bytes((old_public / 'NOTICE').read_bytes())
    (public / 'README.md').write_text(card(report), encoding='utf-8')
    (private / 'README.md').write_text('# 운영자 전용 · 공개 금지\n\n'
        '`test-references.json`은 새 평가 정답입니다. 기존 버전 점수와 섞지 않습니다. '
        '`source-pool/`은 원본 전체 보존용이고 train이 아닙니다. '
        '`reserved.json`의 제외 사유를 참고하세요. test 및 source-pool 정답을 학습에 쓰지 마세요.\n', encoding='utf-8')
    # Seal only after every file has been written, including the documentation.
    lock(public); lock(private)
    return report


def card(report):
    lines = ['# TYE Korean Correction · merged v1', '',
        '기존 5시간 자료와 추가 train/eval 묶음 전체를 통합해 다시 분할했습니다. '
        '**독립 청취 미검수** 상태입니다. 음성 + 초안 → 전체 전사 교정 규격은 그대로입니다.', '',
        '| Split | 녹음 | 시간(초) | 화자 | Clean / Single / Multiple |',
        '|---|---:|---:|---:|---|']
    for split in ('train', 'eval', 'test'):
        x = report['splits'][split]
        lines.append(f"| {split} | {x['utterances']} | {x['duration_seconds']:.6f} | {x['speakers']} | " +
            ' / '.join(str(x['conditions'].get(c, 0)) for c in LABELS) + ' |')
    lines += ['', 'train과 eval은 음성·초안·정답 공개용이며 test 정답은 운영자 전용입니다. '
        '전체 입력 풀은 4,081개·약 9시간 42분입니다. 같은 문장의 다른 화자 녹음을 중복 점수로 '
        '계산하지 않으며, 중복·화자 겹침·목표 시간 초과 녹음은 운영자 예비 풀에 보존합니다.', '',
        '이미 공개된 eval/pilot 정답과 화자는 test에서 제외했습니다. 세 split 사이 화자·세션·'
        '동일/근접 문장(SequenceMatcher ≥0.85)·PCM 중복을 허용하지 않습니다. '
        '분할은 ASR 결과나 정답 오류율을 보고 고르지 않았습니다.', '',
        '원천 전사는 NFC만 적용하고 음성은 원본 PCM을 보존합니다. 희소 명사 치환으로 '
        'Clean 0곳 / Single 1곳 / Multiple 2곳을 생성했습니다. train은 기존 초안을 유지하며 '
        'eval/test는 같은 생성 규칙으로 길이별 세 발화 묶음에 조건을 다시 배정했습니다.', '',
        '`source-pool`과 reserved는 학습·개발용이 아닙니다. 새 test의 원본·정답·다른 화자 녹음이 '
        '포함되어 있으므로 운영자만 보관합니다. 기존 5시간 버전·추가 ZIP의 점수와 새 점수를 섞지 않습니다.', '',
        '이전 test의 일부가 새 train으로 이동했습니다. 새 train 정답을 공개하면 이전 test는 '
        '종료된 버전의 재현 기록으로만 취급하고 공식 평가에 계속 사용하지 않습니다.', '',
        'CC BY 4.0 출처는 NOTICE, 실제 분량·해시는 metadata.json 및 release-lock.json을 확인하세요. '
        '공개 원천 검색·사전학습 오염, 원천 전사 오류 및 합성 치환의 한계는 남습니다.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('old-public', 'old-private', 'incoming-public', 'incoming-private', 'public', 'private'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    report = merge(args.old_public, args.old_private, args.incoming_public,
                   args.incoming_private, args.public, args.private)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
