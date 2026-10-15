"""Convert the supplied context pilot to the existing transcript-correction protocol.

The archive is data: its Python/shell files are never imported or executed.
All gold uses source_transcript, not the unreviewed number/acronym rewrite.
"""
import argparse
import csv
import difflib
import hashlib
import io
import itertools
import json
import re
import stat
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

from scripts.baseline import load_inputs
from scripts.build_dataset import digest, write_json
from server.scoring import VERSION, normalize, score, validate_manifest

ARCHIVE_SHA256 = '4f92cf785aa29e1cdb034deb28d98d85a56b0b144e579dc1276b1367dabfd8ff'
NAME = 'tye-zeroth-correction-pilot-v1'
SEED = 'tye-zeroth-correction-20261015'
CONDITIONS = ['clean', 'single', 'multiple']


def order(ident):
    return hashlib.sha256(f'{SEED}:{ident}'.encode()).hexdigest()


def check_archive(archive):
    """Check the independently supplied digest, safe paths, CRC and inner manifest."""
    if digest(archive) != ARCHIVE_SHA256:
        raise ValueError('Unexpected source archive SHA256; this importer is version pinned.')
    z = zipfile.ZipFile(archive)
    names = z.namelist()
    if len(names) != len(set(names)) or sum(x.file_size for x in z.infolist()) > 200_000_000:
        raise ValueError('Duplicate entries or excessive expanded archive size.')
    for entry in z.infolist():
        path = PurePosixPath(entry.filename)
        if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or stat.S_ISLNK(entry.external_attr >> 16):
            raise ValueError('Unsafe archive entry.')
    if z.testzip():
        raise ValueError('Source archive CRC failure.')
    prefixes = {n.split('/')[0] for n in names}
    if len(prefixes) != 1:
        raise ValueError('Expected one source archive root.')
    base = next(iter(prefixes)) + '/release/pilot160/'
    manifest = z.read(base + 'MANIFEST.sha256').decode('utf-8')
    covered = set()
    for line in manifest.splitlines():
        expected, filename = line.split('  ', 1)
        if PurePosixPath(filename).is_absolute() or '..' in PurePosixPath(filename).parts:
            raise ValueError('Unsafe inner manifest entry.')
        if filename in covered or hashlib.sha256(z.read(base + filename)).hexdigest() != expected:
            raise ValueError('Inner manifest digest mismatch or duplicate entry.')
        covered.add(filename)
    required = {'sources.csv', 'gold_annotations.csv', 'entities.csv', 'corruption_annotations.csv'}
    if not required <= covered:
        raise ValueError('Source tables are not covered by the inner manifest.')
    return z, base, covered


def read_table(z, base, name):
    rows = list(csv.DictReader(io.StringIO(z.read(base + name).decode('utf-8-sig'), newline='')))
    return [{k: unicodedata.normalize('NFC', v) for k, v in row.items()} for row in rows]


def make_variant(ident, reference, edits):
    edits = sorted(edits, key=lambda e: e['start'])
    draft = reference
    for edit in reversed(edits):
        draft = draft[:edit['start']] + edit['replacement'] + draft[edit['end']:]
    return {'id': ident, 'condition': CONDITIONS[min(len(edits), 2)],
            'reference': reference, 'draft': draft, 'edits': edits}


def correction_options(ident, reference, entities, corruptions):
    """Use only explicitly located original spellings; never guess an alias span.

    Aliases from the old context scorer are not accepted by ko-correction-v1.
    In particular, an acronym rewrite is not silently used to locate an entity
    in the unchanged source transcript.
    """
    options, rejected = [], []
    by_id = {e['entity_id']: e for e in entities}
    for annotation in corruptions:
        if annotation['context_condition'] != 'misleading' or annotation['is_corrupted'] != 'True':
            continue
        entity = by_id[annotation['entity_id']]
        if annotation['gold_name'] != entity['name'] or annotation['occurrence'] != entity['occurrence']:
            raise ValueError('Entity and corruption annotation disagree.')
        hits = list(re.finditer(re.escape(entity['name']), reference))
        occurrence = int(entity['occurrence'])
        if not entity['name'] or occurrence < 1 or len(hits) < occurrence:
            rejected.append({'reason': 'name_not_in_unchanged_source', 'entity_id': entity['entity_id']})
            continue
        match = hits[occurrence - 1]
        edit = {'start': match.start(), 'end': match.end(), 'replacement': annotation['distractor']}
        if edit not in options:
            options.append(edit)
    variants = {'clean': make_variant(ident, reference, [])}
    for count, condition in ((1, 'single'), (2, 'multiple')):
        for edits in itertools.combinations(options, count):
            row = make_variant(ident, reference, edits)
            try:
                result = score({ident: row['draft']}, [row])
            except ValueError as exc:
                rejected.append({'reason': str(exc), 'edits': list(edits)})
                continue
            if result['restoration_rate'] != 0 or result['harmful_edit_rate'] != 0:
                raise ValueError('Copy control unexpectedly gains credit or damages untouched text.')
            variants[condition] = row
            break
    return variants, rejected


def allocate(rows, quota):
    """Assign one condition per original, restricting scarce Multiple first."""
    selected, used = [], set()
    for condition in reversed(CONDITIONS):
        candidates = sorted((r for r in rows if r['original_id'] not in used and condition in r['variants']),
                            key=lambda r: order(r['original_id']))
        if len(candidates) < quota:
            raise ValueError(f'Not enough valid {condition} candidates for balanced quota {quota}.')
        for row in candidates[:quota]:
            selected.append((row, condition))
            used.add(row['original_id'])
    return sorted(selected, key=lambda pair: order(pair[0]['original_id'])), [r for r in rows if r['original_id'] not in used]


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build(archive, public, private):
    import numpy as np
    import soundfile as sf
    public, private = public.resolve(), private.resolve()
    if public == private or public in private.parents or private in public.parents:
        raise ValueError('Participant and organizer folders must be separate, non-nested paths.')
    if any(p.exists() for p in (public, private)):
        raise ValueError('Refusing to overwrite an existing import.')
    with check_archive(archive)[0] as z:
        base = next(iter({n.split('/')[0] for n in z.namelist()})) + '/release/pilot160/'
        sources = read_table(z, base, 'sources.csv')
        gold = read_table(z, base, 'gold_annotations.csv')
        gold_by_id = {r['original_id']: r for r in gold}
        if len(sources) != 160 or len(gold_by_id) != 160 or {r['original_id'] for r in sources} != set(gold_by_id):
            raise ValueError('Expected exactly 160 distinct originals in both source and gold tables.')
        entities, corruptions = defaultdict(list), defaultdict(list)
        for row in read_table(z, base, 'entities.csv'): entities[row['original_id']].append(row)
        for row in read_table(z, base, 'corruption_annotations.csv'): corruptions[row['original_id']].append(row)
        pools, audio, hashes, texts = defaultdict(list), {}, set(), set()
        provenance, decisions = [], []
        for source in sources:
            ident = source['original_id']
            reference = gold_by_id[ident]['source_transcript']
            filename = source['audio_file']
            if filename != f'audio/{ident}.wav':
                raise ValueError('Unexpected audio path in source table.')
            payload = z.read(base + filename)
            checksum = hashlib.sha256(payload).hexdigest()
            if checksum != source['audio_sha256'] or checksum in hashes or normalize(reference) in texts:
                raise ValueError('Invalid source audio digest or duplicate audio/transcript.')
            samples, rate = sf.read(io.BytesIO(payload), dtype='float64', always_2d=True)
            if rate != 16000 or samples.shape[1] != 1 or not np.isfinite(samples).all() or not np.any(samples):
                raise ValueError('Audio must be finite, non-silent 16 kHz mono.')
            duration = len(samples) / rate
            if abs(duration - float(source['duration_s'])) > .001:
                raise ValueError('Source audio duration mismatch.')
            variants, rejected = correction_options(ident, reference, entities[ident], corruptions[ident])
            row = source | {'variants': variants, 'duration_seconds': duration}
            pools[source['source_split']].append(row)
            audio[ident] = payload
            hashes.add(checksum); texts.add(normalize(reference))
            decisions.append({'original_id': ident, 'valid_conditions': list(variants), 'rejected_options': rejected})
        if set(pools) != {'train', 'test'}:
            raise ValueError('Expected train/test source partitions.')
        train, test = pools['train'], pools['test']
        if {r['speaker_id'] for r in train} & {r['speaker_id'] for r in test}:
            raise ValueError('Speakers overlap across the proposed split.')
        if {r['session_id'] for r in train} & {r['session_id'] for r in test}:
            raise ValueError('Sessions overlap across the proposed split.')
        near = [(a['original_id'], b['original_id']) for a in train for b in test
                if difflib.SequenceMatcher(None, normalize(gold_by_id[a['original_id']]['source_transcript']),
                    normalize(gold_by_id[b['original_id']]['source_transcript']), autojunk=False).ratio() >= .85]
        if near:
            raise ValueError('Near-duplicate source transcripts cross partitions.')
        dev, dev_reserve = allocate(train, 41)
        evaluation, eval_reserve = allocate(test, 9)
        public.mkdir(parents=True); private.mkdir(parents=True)
        report = {'name': NAME, 'status': 'pilot_pending_independent_listening', 'protocol': VERSION,
            'source_archive_sha256': ARCHIVE_SHA256, 'source_originals': 160,
            'source_context_variants': 665, 'human_listening_review': 'not_performed',
            'blind_asr_crosscheck': 'not_performed', 'gold_policy': 'source_transcript_NFC_only',
            'aliases_accepted': False, 'speaker_disjointness': 'checked_from_supplied_source_ids',
            'splits': {}, 'reserved_originals': len(dev_reserve) + len(eval_reserve),
            'eligible_conditions': {split: dict(Counter(c for r in rows for c in r['variants']))
                for split, rows in pools.items()},
            'cross_split_near_duplicates_at_0_85': 0,
            'limitations': [
                'Not a replacement for the released FLEURS v2; scores belong to a separate dataset.',
                'No independent listening or ASR audit; source labels may contain errors/omit fillers.',
                'Supplied gold number/acronym rewrites and homophone aliases are deliberately not used.',
                'Distractors are reused from unreviewed annotations; acoustic distinguishability is unverified.',
                'Clean/Single/Multiple differ in eligible entity populations; no causal condition comparison.',
                'Public upstream corpus may be searchable or present in model pretraining.',
                'Only archive/provided hashes are verified; original upstream raw bytes were not redownloaded.',
                'Names may overlap across splits; exact audio, normalized source text, speaker/session IDs do not.'
            ]}
        for split, selected in [('dev', dev), ('eval', evaluation)]:
            refs, inputs, checksums = [], [], {}
            folder = public / split
            (folder / 'audio').mkdir(parents=True)
            for source, condition in selected:
                original = source['original_id']
                ident = hashlib.sha256(f'{NAME}:{original}'.encode()).hexdigest()[:16]
                row = source['variants'][condition] | {'id': ident}
                refs.append(row)
                inputs.append({'id': ident, 'audio': f'audio/{ident}.wav', 'draft': row['draft']})
                (folder / 'audio' / f'{ident}.wav').write_bytes(audio[original])
                checksums[ident] = hashlib.sha256(audio[original]).hexdigest()
                provenance.append({k: v for k, v in source.items() if k != 'variants'} |
                    {'id': ident, 'split': split, 'condition': condition, 'reference': row['reference'],
                     'source_review_status': gold_by_id[original]['review_status']})
            manifest = {'name': NAME + '-' + split, 'protocol': VERSION, 'conditions': CONDITIONS, 'items': refs}
            validate_manifest(manifest)
            write_json(folder / 'inputs.json', {'name': NAME + '-' + split, 'items': inputs})
            write_json(folder / 'references.json' if split == 'dev' else private / 'eval-references.json', manifest)
            write_json(folder / 'audio-checksums.json', checksums)
            write_csv(folder / 'copy-draft.csv', ['id', 'prediction'], [{'id': r['id'], 'prediction': r['draft']} for r in refs])
            result = score({r['id']: r['draft'] for r in refs}, refs)
            oracle = score({r['id']: r['reference'] for r in refs}, refs)
            if oracle['macro_cer'] != 0 or oracle['restoration_rate'] != 100 or oracle['harmful_edit_rate'] != 0:
                raise ValueError('Oracle scorer integration failed.')
            write_json(folder / 'copy-draft.scores.json', result)
            load_inputs(folder / 'inputs.json')
            report['splits'][split] = {'utterances': len(refs), 'conditions': dict(Counter(r['condition'] for r in refs)),
                'duration_seconds': round(sum(r['duration_seconds'] for r, _ in selected), 6),
                'speakers': len({r['speaker_id'] for r, _ in selected}),
                'inputs_sha256': digest(folder / 'inputs.json'), 'copy_macro_cer': result['macro_cer'],
                'oracle_macro_cer': oracle['macro_cer']}
        write_json(private / 'provenance.json', provenance)
        write_json(private / 'conversion-decisions.json', decisions)
        reserve = dev_reserve + eval_reserve
        write_json(private / 'reserve.json', [{k: v for k, v in r.items() if k != 'variants'} for r in reserve])
        for row in reserve:
            path = private / 'reserve-audio' / f"{row['original_id']}.wav"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(audio[row['original_id']])
        # Preserve the supplied review evidence without executing any supplied code.
        for filename in ['sources.csv', 'gold_annotations.csv', 'entities.csv', 'corruption_annotations.csv',
                         'condition_inputs.csv', 'NOTICE.md', 'run_meta.json', 'validation_report.md',
                         'review/blind_listening_sheet.csv', 'review/context_review.md']:
            target = private / 'source-records' / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(base + filename))
        review_rows = [{'id': r['id'], 'split': r['split'], 'original_id': r['original_id'],
            'participant_relative_audio': f"{r['split']}/audio/{r['id']}.wav",
            'source_transcript': r['reference'], 'reviewer_a_transcript': '', 'reviewer_b_transcript': '',
            'agreed_transcript': '', 'status': 'pending'} for r in provenance]
        write_csv(private / 'listening-review.csv', list(review_rows[0]), review_rows)
        report['evaluation_references_sha256'] = digest(private / 'eval-references.json')
        write_json(public / 'metadata.json', report)
        write_json(private / 'import-report.json', report)
        notice = ('Zeroth-Korean (OpenSLR SLR40), Lucas Jo (Atlas Guide) & Wonkyum Lee (Gridspace).\n'
            'CC BY 4.0: https://creativecommons.org/licenses/by/4.0/\n'
            'Original: https://www.openslr.org/40/\n'
            'Mirror: https://huggingface.co/datasets/kresnik/zeroth_korean\n'
            'Audio: supplied 16 kHz mono WAV bytes preserved. Transcripts: supplied source_transcript, NFC only.\n'
            'Changes: one transcript draft per recording, sparse name substitutions, opaque IDs, new splits.\n'
            'Upstream authors do not endorse this derivative. Independent listening has not been performed.\n')
        (public / 'NOTICE').write_text(notice, encoding='utf-8')
        (public / 'README.md').write_text(dataset_card(report), encoding='utf-8')
        (private / 'README.md').write_text(
            '# 운영자 전용 · 공개 업로드 금지\n\n'
            'eval-references.json은 기존 웹 채점기의 REFERENCE_PATH에 지정합니다. '
            'source-records는 평가 정답과 원천 ID를 포함합니다. 참가자 배포물과 분리하세요.\n\n'
            'listening-review.csv의 participant_relative_audio는 참가자 폴더 기준 경로입니다. '
            '두 청취 전사와 합의 결과를 채우세요. 검수로 정답이 바뀌면 '
            '현재 파일을 덮어쓰지 말고 새 데이터 버전으로 초안·오프셋·점수를 다시 생성해야 합니다.\n'
            'reserve.json / reserve-audio는 본 평가에 포함하지 않은 10개 원본입니다.\n', encoding='utf-8')
        write_json(public / 'release-lock.json', {'name': NAME, 'sha256': {
            str(p.relative_to(public)): digest(p) for p in sorted(public.rglob('*')) if p.is_file()}})
        return report


def dataset_card(report):
    dev, evaluation = report['splits']['dev'], report['splits']['eval']
    return f'''# TYE Zeroth 한국어 전사 교정 파일럿 v1

상태: **청취 미검수 파일럿**. 기존 FLEURS v2와 별도 데이터셋이며 결과를 혼합하지 않습니다.

| 분할 | 실제 음성 | Clean | Single | Multiple | 화자 | 길이(초) |
|---|---:|---:|---:|---:|---:|---:|
| 개발 | 123 | 41 | 41 | 41 | {dev['speakers']} | {dev['duration_seconds']:.3f} |
| 평가 | 27 | 9 | 9 | 9 | {evaluation['speakers']} | {evaluation['duration_seconds']:.3f} |

원본 160개 중 150개를 사용하고 10개는 운영자 예비 자료로 보관합니다.
첨부 자료의 665개는 같은 음성을 반복한 참고자료 변형 수입니다. 이번 데이터에서는
음성 하나에 초안 하나만 배정하며 참고자료·조건 라벨·이름 주석을 모델에 제공하지 않습니다.

개발은 원천 train, 평가는 원천 test입니다. 제공된 화자·세션 ID, 오디오 SHA256,
정규화 전사 중복을 점검했으며 분할 사이 SequenceMatcher 유사도 0.85 이상 문장이 없습니다.
개인 신원 또는 서로 다른 원천 ID가 같은 사람인지 독립 확인하지는 않았습니다.

## 입력과 정답

`dev/inputs.json`, `eval/inputs.json`은 `id`, `audio`, `draft`만 제공합니다.
`dev/references.json`은 공개 개발 정답입니다. 평가 정답·원천 대응표·검수표는 운영자 폴더에 있습니다.
초안을 그대로 제출하는 `copy-draft.csv`를 각 split에 제공합니다.

정답은 제공된 `source_transcript`에 NFC만 적용합니다. 숫자·약어를 자동 변환한
`gold_transcript`는 청취 확인 전이므로 사용하지 않습니다. 영문 이름의 한글 읽기,
동음 철자 alias도 추가 정답으로 인정하지 않습니다. 숫자·간투사 표기는 원천 전사와 같습니다.

초안에만 첨부 자료의 오답 이름을 0/1/2곳 치환합니다. 원천 전사에서 이름과 등장 순서를
정확히 찾고, 원문 문자 오프셋·재구성·최소 편집 정렬 검사를 통과한 주석만 사용합니다.
두 오류 사이에는 정규화 후 정상 문자 한 개 이상이 있어야 합니다.
서로 붙어 있는 이름들을 억지로 두 오류로 세지 않아 평가 Multiple 후보가 9개입니다.

## 채점과 실행

기존 `ko-correction-v1`을 그대로 사용합니다. 공백 제거·NFC·영문 소문자·지정 문장부호 제거 후
한글 음절 문자 단위 CER를 구하고 Clean/Single/Multiple을 1/3씩 평균합니다.
복원률·정상 구간 훼손률·Clean 변경률도 기존 채점 코드와 같습니다.
이 파일럿의 숫자/약어 읽기와 아라비아/라틴 표기는 자동 동치화하지 않습니다.

Copy draft Macro CER: 개발 **{dev['copy_macro_cer']:.6f}%**, 평가 **{evaluation['copy_macro_cer']:.6f}%**.
정답 제출 통합 검사: 양쪽 CER 0%, 복원률 100%, 훼손률 0%.
이 값은 채점기 점검 결과이며 모델 추론 성능이 아닙니다.

저장소 루트에서 `<participant>`와 `<organizer>`를 실제 폴더 경로로 바꿉니다.

```sh
python -m scripts.baseline --mode copy --inputs <participant>/eval/inputs.json --output /tmp/zeroth-copy.csv
python -m scripts.evaluate --references <organizer>/eval-references.json --predictions /tmp/zeroth-copy.csv
REFERENCE_PATH=/absolute/organizer/eval-references.json uvicorn server.app:create_app --factory
```

## 검수와 해석의 한계

150개 모두 독립 청취 및 블라인드 ASR 검증을 수행하지 않았습니다. 원천 전사 오류,
누락된 간투사, 잘린 음성, 오답의 청각적 구별 가능성을 사람 2명이 확인해야 합니다.
첨부 검증 보고서의 ‘통과’는 이전 참고자료 과제에 대한 소프트웨어 검사이며 청취 인증이 아닙니다.
조건별 이름 수·문장 난이도가 동일하지 않아 조건 차이를 순수한 오류 개수 효과로 해석할 수 없습니다.
본 과제의 오답은 합성 이름 치환이며 실제 ASR 오류 분포를 대표하지 않습니다.
원천 자료는 공개되어 원문 검색·사전학습 오염 가능성이 있습니다.
첨부 ZIP과 내부 manifest, 개별 음성 해시는 확인했지만 원천 대용량 파일을 재다운로드하지 않았습니다.

출처·저작자·라이선스·변경 사항은 `NOTICE`에 기록했습니다.
원본 ZIP SHA256: `{ARCHIVE_SHA256}`.
`release-lock.json`은 이 파일을 포함한 참가자 배포물의 해시를 고정합니다.
'''


def validate(public, private):
    """Re-open delivered bytes and check their source agreement and scorer contract."""
    import numpy as np
    import soundfile as sf
    report = json.loads((public / 'metadata.json').read_text())
    if report['source_archive_sha256'] != ARCHIVE_SHA256 or report['status'] != 'pilot_pending_independent_listening':
        raise ValueError('Unexpected dataset provenance or review status.')
    lock = json.loads((public / 'release-lock.json').read_text())['sha256']
    actual = {str(p.relative_to(public)): digest(p) for p in public.rglob('*')
              if p.is_file() and p.name != 'release-lock.json'}
    if actual != lock:
        raise ValueError('Participant files differ from the release lock.')
    provenance = json.loads((private / 'provenance.json').read_text())
    by_id = {r['id']: r for r in provenance}
    sources = {r['original_id']: r for r in csv.DictReader(
        (private / 'source-records/sources.csv').open(encoding='utf-8-sig'))}
    source_gold = {r['original_id']: r for r in csv.DictReader(
        (private / 'source-records/gold_annotations.csv').open(encoding='utf-8-sig'))}
    seen, checks = set(), {}
    split_texts, split_speakers, split_sessions = {}, {}, {}
    for split in ('dev', 'eval'):
        inputs = load_inputs(public / split / 'inputs.json')
        manifest_path = public / split / 'references.json' if split == 'dev' else private / 'eval-references.json'
        refs = validate_manifest(json.loads(manifest_path.read_text()))
        refs_by_id = {r['id']: r for r in refs}
        if {r['id'] for r in inputs} != set(refs_by_id) or len(refs) != report['splits'][split]['utterances']:
            raise ValueError('Public inputs and references have different ID coverage.')
        if dict(Counter(r['condition'] for r in refs)) != report['splits'][split]['conditions']:
            raise ValueError('Condition counts do not match metadata.')
        checksums = json.loads((public / split / 'audio-checksums.json').read_text())
        expected_files = {f"{r['id']}.wav" for r in inputs}
        if {p.name for p in (public / split / 'audio').iterdir()} != expected_files:
            raise ValueError('Audio files do not exactly cover public inputs.')
        duration = 0
        for row in inputs:
            ident = row['id']
            origin = by_id[ident]
            if origin['split'] != split or origin['source_split'] != {'dev': 'train', 'eval': 'test'}[split]:
                raise ValueError('Source partitions were mixed.')
            if row['draft'] != refs_by_id[ident]['draft'] or row['audio'] != f'audio/{ident}.wav':
                raise ValueError('Draft or audio path differs from the scored item.')
            source = sources[origin['original_id']]
            raw_gold = unicodedata.normalize('NFC', source_gold[origin['original_id']]['source_transcript'])
            if refs_by_id[ident]['reference'] != raw_gold or origin['reference'] != raw_gold:
                raise ValueError('Scored gold differs from unchanged source transcript.')
            path = public / split / row['audio']
            if digest(path) != source['audio_sha256'] or digest(path) != checksums[ident]:
                raise ValueError('Source audio bytes changed.')
            samples, rate = sf.read(path, dtype='float64', always_2d=True)
            if rate != 16000 or samples.shape[1] != 1 or not np.isfinite(samples).all() or not np.any(samples):
                raise ValueError('Invalid delivered audio.')
            duration += len(samples) / rate
            if ident in seen:
                raise ValueError('Repeated ID across splits.')
            seen.add(ident)
        if abs(duration - report['splits'][split]['duration_seconds']) > .000001:
            raise ValueError('Delivered duration differs from metadata.')
        copy = score({r['id']: r['draft'] for r in inputs}, refs)
        if copy != json.loads((public / split / 'copy-draft.scores.json').read_text()):
            raise ValueError('Saved copy control is not reproducible.')
        from server.scoring import parse_submission
        if parse_submission((public / split / 'copy-draft.csv').read_bytes()) != {r['id']: r['draft'] for r in inputs}:
            raise ValueError('Copy submission differs from participant drafts.')
        checks[split] = {'audio': len(inputs), 'copy_macro_cer': copy['macro_cer']}
        selected = [by_id[r['id']] for r in inputs]
        split_texts[split] = [normalize(r['reference']) for r in refs]
        split_speakers[split] = {r['speaker_id'] for r in selected}
        split_sessions[split] = {r['session_id'] for r in selected}
    if seen != set(by_id) or len(by_id) != len(provenance):
        raise ValueError('Private provenance does not exactly cover participant audio.')
    if split_speakers['dev'] & split_speakers['eval'] or split_sessions['dev'] & split_sessions['eval']:
        raise ValueError('Speaker or session overlap.')
    if any(difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() >= .85
           for a in split_texts['dev'] for b in split_texts['eval']):
        raise ValueError('Cross-split near-duplicate transcript.')
    if digest(private / 'eval-references.json') != report['evaluation_references_sha256']:
        raise ValueError('Private evaluation references changed.')
    if (public / 'eval/references.json').exists():
        raise ValueError('Evaluation gold was placed in the participant split.')
    reserve = json.loads((private / 'reserve.json').read_text())
    used_originals = {r['original_id'] for r in provenance}
    reserve_originals = {r['original_id'] for r in reserve}
    if used_originals & reserve_originals or used_originals | reserve_originals != set(sources):
        raise ValueError('Selected and reserve items do not partition all source originals.')
    for original in reserve_originals:
        if digest(private / 'reserve-audio' / f'{original}.wav') != sources[original]['audio_sha256']:
            raise ValueError('Reserve audio differs from the source.')
    return {'status': 'software_validated_human_review_pending', 'source_originals_accounted_for': len(sources),
            'human_listening_review': 'not_performed', 'splits': checks, 'reserve': len(reserve)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--private', type=Path, required=True)
    parser.add_argument('--validate', action='store_true')
    args = parser.parse_args()
    if not args.validate and not args.archive:
        parser.error('--archive is required when building an import.')
    result = validate(args.public, args.private) if args.validate else build(args.archive, args.public, args.private)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
