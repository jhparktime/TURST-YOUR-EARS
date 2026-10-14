"""Prepare candidates, then freeze a Korean correction release with blind-ASR QA.

The QA recognizer never defines or rewrites gold. Upstream labels remain the
reference; gross disagreement or unsupported targets exclude a candidate.
QA selection introduces model bias.
"""
import argparse
import csv
import difflib
import hashlib
import json
import random
import shutil
from collections import Counter
from pathlib import Path

from scripts.build_dataset import (ARCHIVE_HASHES, TSV_HASHES, REVISION, choose,
    candidates, digest, extract_audio, fetch, load_pairs, source_rows, valid_edits, write_json, write_review_materials)
from scripts.transcribe_audio import MODEL, REVISION as MODEL_REVISION
from server.scoring import VERSION, alignment, normalize, score, validate_manifest

NAME = 'tye-ko-v2'
SEED = 20261015
SOURCES = ('train', 'dev', 'test')
EXCLUDE = {'보통','가능','전문','전원','태양','토양','중심','관심','공룡','공원','온도','속도','정도'}
MAX_QA_CER = 10.0


def supported_edits(reference, prediction, mapping):
    gold, hypothesis = normalize(reference),normalize(prediction)
    aligned, _, errors = alignment(gold,hypothesis)
    cer = 100*errors/len(gold)
    options=[]
    for edit in candidates(reference,mapping,avoid_zero=True):
        start=len(normalize(reference[:edit['start']]))
        end=start+len(normalize(reference[edit['start']:edit['end']]))
        if ''.join(aligned[start:end]) == gold[start:end]:
            options.append(edit)
    return cer, options


def prepare(cache, work, pilot_lexicon, previous):
    lexicon = json.loads(pilot_lexicon.read_text(encoding='utf-8'))
    lexicon['pairs'] = [pair for pair in lexicon['pairs'] if pair[0] not in EXCLUDE]
    known={pair[0] for pair in lexicon['pairs']}
    extra=json.loads((Path(__file__).resolve().parents[1]/'datasets/recipes/korean-extra-pairs.json').read_text())
    lexicon['pairs'].extend(pair for pair in extra if pair[0] not in known)
    lexicon['description'] = ('Curated semantic/numeric substitutions for Korean transcript correction; '
        'not empirical ASR confusion probabilities. Particle class and word boundaries preserved.')
    write_json(work/'substitutions.json', lexicon)
    mapping = load_pairs(work/'substitutions.json')
    old=json.loads(previous.read_text())
    if not old:raise ValueError('Previous-release provenance is required to exclude exposed sentences.')
    old_ids={r['source_id'] for r in old}
    old_text=[normalize(r['reference']) for r in old]
    old_hashes={r['audio_sha256'] for r in old}
    write_json(work/'previous-release-exclusions.json',old)
    all_rows, pool_counts, rejected = [], {}, {}
    for source in SOURCES:
        rows, rejected[source] = source_rows(fetch(cache,source),mapping,SEED,relaxed=True)
        pool_counts[source] = len(rows)
        if source!='train':
            before=len(rows)
            rows=[r for r in rows if r['source_id'] not in old_ids and
                  all(difflib.SequenceMatcher(None,normalize(r['reference']),t,autojunk=False).ratio()<0.85 for t in old_text)]
            rejected[source]['previous_release_sentence']=before-len(rows)
        if source == 'train':
            random.Random(SEED).shuffle(rows)
            rows = rows[:180]
        for row in rows:
            row['source_split'] = source
            row['id'] = hashlib.sha256(f"tye-v2:{source}:{row['source_filename']}".encode()).hexdigest()[:16]
        extract_audio(fetch(cache,source,audio=True), [(r,'clean') for r in rows],work/'candidates')
        if source!='train' and any(r['audio_sha256'] in old_hashes for r in rows):
            raise ValueError('An evaluation candidate repeats a previously exposed recording.')
        write_json(work/f'{source}-inputs.json', {'items':[{'id':r['id'],
            'audio':f"candidates/audio/{r['id']}.wav",'draft':r['reference']} for r in rows]})
        all_rows.extend(rows)
    write_json(work/'candidate-provenance.json',all_rows)
    write_json(work/'candidate-plan.json',{'seed':SEED,'source_revision':REVISION,
        'provenance_sha256':digest(work/'candidate-provenance.json'),
        'lexicon_sha256':digest(work/'substitutions.json'),
        'previous_exclusions_sha256':digest(work/'previous-release-exclusions.json'),
        'eligible_pool':pool_counts,'text_duration_edit_exclusions':rejected})
    return Counter(r['source_split'] for r in all_rows)


def accepted_candidates(work):
    plan = json.loads((work/'candidate-plan.json').read_text())
    if digest(work/'candidate-provenance.json') != plan['provenance_sha256']:
        raise ValueError('Prepared source candidates changed.')
    if digest(work/'substitutions.json') != plan['lexicon_sha256']:
        raise ValueError('Prepared lexicon changed.')
    if 'previous_exclusions_sha256' in plan and digest(work/'previous-release-exclusions.json') != plan['previous_exclusions_sha256']:
        raise ValueError('Previous-release exclusion records changed.')
    rows = json.loads((work/'candidate-provenance.json').read_text())
    mapping = load_pairs(work/'substitutions.json')
    accepted, qa_summary, predictions = [], {}, {}
    for source in SOURCES:
        state = json.loads((work/f'asr-{source}/audio-only.json').read_text())
        if (state['model'],state['revision']) != (MODEL,MODEL_REVISION):
            raise ValueError('QA model or revision mismatch.')
        source_rows_ = [r for r in rows if r['source_split']==source]
        states = state['items']
        by_id = {r['id']:r for r in states}
        if len(by_id) != len(states) or set(by_id) != {r['id'] for r in source_rows_}:
            raise ValueError('QA predictions must cover exactly all prepared candidates.')
        count, exact = 0, 0
        for row in source_rows_:
            prediction = by_id[row['id']]
            if prediction['audio_sha256'] != row['audio_sha256']:
                raise ValueError('QA audio checksum does not match source audio.')
            predictions[row['id']] = prediction
            cer, options = supported_edits(row['reference'],prediction['prediction'],mapping)
            exact += cer==0
            variants={}
            for size in (1,2):
                variant=valid_edits(row['reference'],options,size,random.Random(f'{SEED}:{row["source_filename"]}:{size}'))
                if variant:variants[str(size)]=variant
            if cer<=MAX_QA_CER and len(variants)==2:
                accepted.append(row|{'variants':variants,'qa_cer':cer,'qa_supported_options':options})
                count += 1
        qa_summary[source] = {'candidates':len(source_rows_), 'exact_agreement':exact,'admitted':count,
            'excluded_qa':len(source_rows_)-count}
    return accepted, qa_summary, predictions, plan


def disjoint_pools(accepted):
    pools = {'dev':[], 'eval':[]}
    for split in pools:
        seen_ids, seen_text, seen_hash = set(),set(),set()
        source_rows_ = [r for r in accepted if (r['source_split']=='train') == (split=='dev')]
        random.Random(SEED+(split=='eval')).shuffle(source_rows_)
        for row in source_rows_:
            key = normalize(row['reference'])
            if row['source_id'] in seen_ids or key in seen_text or row['audio_sha256'] in seen_hash:
                continue
            seen_ids.add(row['source_id']);seen_text.add(key);seen_hash.add(row['audio_sha256'])
            pools[split].append(row)
    return pools


def freeze(work, output, private, dev_count=60, eval_count=60):
    if output.exists() and any(output.iterdir()):
        raise ValueError('A frozen release must use a new, empty output directory.')
    accepted, qa_summary, predictions, plan = accepted_candidates(work)
    pools = disjoint_pools(accepted)
    selected = {'dev':choose(pools['dev'],dev_count,random.Random(SEED))}
    dev = [r for r,_ in selected['dev']]
    dev_ids = {r['source_id'] for r in dev}
    dev_hashes = {r['audio_sha256'] for r in dev}
    dev_text = [normalize(r['reference']) for r in dev]
    filtered = [r for r in pools['eval'] if r['source_id'] not in dev_ids and r['audio_sha256'] not in dev_hashes
        and all(difflib.SequenceMatcher(None,normalize(r['reference']),t,autojunk=False).ratio()<0.85 for t in dev_text)]
    selected['eval'] = choose(filtered,eval_count,random.Random(SEED+1))
    provenance, summary = [], {}
    for split, chosen in selected.items():
        inputs, refs = [], []
        for row, condition in chosen:
            edits,draft,types = ([],row['reference'],[]) if condition=='clean' else row['variants'][str(1 if condition=='single' else 2)]
            inputs.append({'id':row['id'],'audio':f"audio/{row['id']}.wav",'draft':draft})
            refs.append({'id':row['id'],'condition':condition,'reference':row['reference'],'draft':draft,'edits':edits})
            path = output/split/'audio'/f"{row['id']}.wav"
            path.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(work/'candidates/audio'/path.name,path)
            if digest(path) != row['source_audio_sha256']:
                raise ValueError('Released source audio bytes changed.')
            provenance.append({k:row[k] for k in ('id','source_id','source_filename','reference','raw_transcription',
                'gender','samples','audio_sha256','source_audio_sha256','pcm_sha256','source_split')} |
                {'split':split,'condition':condition,'edit_types':types,'speaker_id':None,
                 'review_status':'blind_asr_span_corroboration','human_reviewer':None,'qa_cer':row['qa_cer']})
        manifest = {'name':f'{NAME}-{split}','protocol':VERSION,'conditions':['clean','single','multiple'],'items':refs}
        validate_manifest(manifest)
        write_json(output/split/'inputs.json',{'name':manifest['name'],'items':inputs})
        write_json(output/split/'references.json' if split=='dev' else private/'eval-references.json',manifest)
        write_json(output/split/'audio-checksums.json',{r['id']:r['audio_sha256'] for r,_ in chosen})
        result = score({r['id']:r['draft'] for r in refs},refs)
        write_json(output/split/'copy-draft.scores.json',result)
        with (output/split/'copy-draft.csv').open('w',encoding='utf-8',newline='') as stream:
            writer=csv.writer(stream,lineterminator='\n');writer.writerow(['id','prediction'])
            writer.writerows((r['id'],r['draft']) for r in inputs)
        summary[split]={'utterances':len(refs),'conditions':dict(Counter(r['condition'] for r in refs)),
            'duration_seconds':sum(r['samples']/16000 for r,_ in chosen),
            'source_splits':dict(Counter(r['source_split'] for r,_ in chosen)),
            'gender':dict(Counter(r['gender'] for r,_ in chosen)),
            'inputs_sha256':digest(output/split/'inputs.json'),'copy_macro_cer':result['macro_cer']}
        write_json(private/f'{split}-qa.json',{'model':MODEL,'revision':MODEL_REVISION,
            'items':[predictions[r['id']] for r,_ in chosen]})
        write_json(output/split/'audio-only-qa.scores.json',score({r['id']:predictions[r['id']]['prediction'] for r,_ in chosen},refs))
    write_json(private/'provenance.json',provenance)
    shutil.copyfile(work/'previous-release-exclusions.json',private/'previous-release-exclusions.json')
    write_review_materials(output,private,provenance)
    shutil.copyfile(work/'substitutions.json',output/'substitutions.json')
    write_json(output/'quality-report.json',{'method':'Upstream references unchanged; blind ASR CER <=10%; at least two eligible injection spans corroborated verbatim by aligned ASR.',
        'model':MODEL,'revision':MODEL_REVISION,'initial_prompt':None,'draft_access':False,'reference_access':False,
        'max_candidate_asr_cer':MAX_QA_CER,'source_candidate_counts':qa_summary,'selected_span_corroboration':{'dev':dev_count,'eval':eval_count},
        'human_listening_review':'not_performed',
        'selection_bias':'Candidates were screened using this ASR model. Audio-only scores are measured diagnostics, not unbiased benchmark performance or human listening certification.'})
    metadata={'name':NAME,'status':'frozen_automatic_crosscheck','protocol':VERSION,'seed':SEED,
        'source':'google/fleurs','source_revision':REVISION,'language':'ko_kr','license':'CC-BY-4.0',
        'source_tsv_sha256':TSV_HASHES,'source_archive_sha256':ARCHIVE_HASHES,
        'lexicon_sha256':digest(output/'substitutions.json'),'splits':summary,
        'speaker_disjointness':'Inherited train vs dev/test speaker separation stated by the upstream dataset card; not independently identity-verified.',
        'speaker_policy_source':'https://huggingface.co/datasets/google/fleurs/blob/70bb2e84b976b7e960aa89f1c648e09c59f894dd/README.md',
        'reference_policy':'Upstream normalized transcription, NFC only, unchanged. Blind ASR corroborates injected spans; candidate ASR CER <=10%; human listening not performed.',
        'audio_policy':'Original 16 kHz mono WAV copied byte-for-byte.',
        'split_policy':'Source train -> development; source dev/test -> evaluation; one recording per source sentence; IDs/text/audio disjoint; cross-split text similarity <0.85.',
        'corruption_policy':'Clean=0, Single=1, Multiple=2 annotated substitutions; balanced duration blocks; same two-edit-eligible population.',
        'human_listening_review':'not_performed','qa_selection_bias':True,
        'previous_release_overlap':'Evaluation excludes all v1 source sentence IDs, audio hashes and text similarity >=0.85.',
        'candidate_plan_sha256':digest(work/'candidate-plan.json'),
        'evaluation_references_sha256':digest(private/'eval-references.json')}
    write_json(output/'metadata.json',metadata)
    total_seconds=sum(s['duration_seconds'] for s in summary.values())
    (output/'README.md').write_text(f'''# Trust Your Ears · Korean Correction v2

**최종 배포본: 실제 한국어 음성 + 합성 오류 전사 초안.** 개발 {dev_count}개·평가 {eval_count}개이며 음성은 약 {int(total_seconds//60)}분 {total_seconds%60:.2f}초입니다. 고정된 배포 파일의 목록과 SHA-256은 `release-lock.json`에 있습니다. v1 파일럿과 ID·정답·분할이 다르므로 결과를 혼합하지 마세요.

## 과제와 구성

음성과 전사 초안을 받아 실제 발화에 맞는 전체 전사문을 출력합니다. 원본 WAV와 정답 전사는 변경하지 않았으며, **초안의 명사 또는 숫자 값만 치환**했습니다. TTS 합성 음성이나 실제 ASR 출력 오류를 수집한 데이터가 아닙니다.

| 조건 | 개발 | 평가 | 주입 오류 |
|---|---:|---:|---:|
| Clean | {dev_count//3} | {eval_count//3} | 0곳 |
| Single | {dev_count//3} | {eval_count//3} | 1곳 |
| Multiple | {dev_count//3} | {eval_count//3} | 정확히 2곳 |

- `dev/inputs.json`, `dev/audio/`: 공개 개발 입력과 실제 16 kHz mono WAV.
- `dev/references.json`: 개발 정답·조건·NFC 문자 기준 오류 위치.
- `eval/inputs.json`, `eval/audio/`: 평가 입력. 각 행의 필드는 `id,audio,draft`만 포함합니다.
- 각 split의 `copy-draft.csv`, `copy-draft.scores.json`: 초안을 그대로 제출하는 채점 기준점. 모델 교정 성능이 아닙니다.
- `quality-report.json`: 음성 전사 교차 검사 기준과 원천별 포함·제외 수. 평가 전사와 샘플별 모델 출력은 포함하지 않습니다.
- `metadata.json`, `audio-checksums.json`, `release-lock.json`: 버전·분할·음성·파일 무결성 기록.

운영자용 `private-data/{NAME}/`에는 평가 정답, 원천 대응표, 샘플별 음성 전사 검사 결과, 추가 청취 검수표가 있습니다. 공개 저장소나 GitHub Pages에 올리지 마세요. 평가 정답 manifest의 전체 SHA-256은 공개 metadata에 고정해 두었습니다.

## 출처와 이용 조건

원천은 [Google FLEURS](https://huggingface.co/datasets/google/fleurs), 한국어 `ko_kr`, 고정 revision [`{REVISION}`](https://huggingface.co/datasets/google/fleurs/tree/{REVISION})입니다. 원천 및 파생 데이터는 **CC BY 4.0**이며 출처·저자·초안 치환 사실을 표시해야 합니다. 저자의 후원이나 제휴를 의미하지 않습니다. 세부 출처 표시는 `NOTICE`를 따릅니다.

Conneau et al. (2022), [FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech](https://arxiv.org/abs/2205.12446).

## 선별과 분할

1. 원천 음성 압축 파일과 전사 TSV의 고정 해시를 검사합니다. WAV는 바이트 단위 그대로 복사합니다. 정답은 원천 `transcription` 열에 NFC만 적용합니다.
2. 한글 중심(문자 중 한글 비율 80% 이상, 숫자 제외), 4–20초, 정규화 25–180자, 유효한 치환 후보 두 곳 이상을 가진 같은 모집단에서 모든 조건을 선별합니다. 제한적인 영문 혼용·원천 구두점을 허용합니다. 이 기준 때문에 전체 한국어 발화를 대표하지 않습니다.
3. 개발 후보는 **원천 train**에서 seed {SEED}로 180개를 선택하고, 평가 후보는 원천 dev/test의 조건 충족 발화를 사용합니다. **v1에 공개한 문장은 평가 후보에서 전부 제외**하고, v1 전사와 문자 유사도 0.85 이상인 후보·동일 음성도 제외합니다. FLEURS는 train 화자가 dev/test 화자와 다르다고 명시합니다. 이 보장은 원천에 의존하며, 우리가 화자 신원을 직접 확인한 것은 아닙니다. TSV에는 개별 화자·세션 ID가 없습니다.
4. 고정 Whisper 체크포인트로 **음성만** 전사합니다. 초안·정답·정답 힌트·이전 발화 문맥을 모델에 제공하지 않습니다. 원천 전사 대비 CER 10% 이하이고, 치환 후보 단어 두 곳 이상이 정렬된 음성 전사에서 원문 그대로 확인되는 후보만 사용합니다. 주입 위치는 이 확인된 후보에서 선택합니다. 모델 출력으로 정답을 덮어쓰지 않습니다. 전체 전사의 일치를 강제하지 않으므로 검증 모델의 0% CER을 보장하지 않습니다.
5. 동일 문장 ID·정규화 전사·음성은 중복하지 않습니다. 개발·평가 간 문자 SequenceMatcher 유사도 0.85 이상인 전사도 제외합니다. 모든 의미적 중복을 판정하는 방법은 아닙니다.
6. 음성 길이 순 세 개씩 묶어 Clean/Single/Multiple을 하나씩 배정합니다. 치환은 어간·조사 경계를 확인하고, 같은 글자 수·받침 유무를 유지합니다. 소수·음수·자릿수 변경은 주입 대상에서 제외합니다. 일부 치환은 의미가 비슷하거나 문맥으로 유추할 수 있습니다. 실제 ASR 혼동 확률이나 균일한 발음 유사성을 주장하지 않습니다.

## 검증 범위와 해석

**사람의 독립 청취 검수는 수행하지 않았습니다.** 원천 공식 전사를 정답으로 사용하고, 주입할 단어를 블라인드 음성 전사와 교차 확인한 자동 검증 배포본입니다. 교차 확인이 참조 전사 전체의 절대적 정확성이나 음성 이해 능력을 증명하지는 않습니다. 원천과 검증 모델의 공통 오류·사전학습 오염 가능성이 남습니다.

선별에 사용한 Whisper에 유리한 선택 편향이 있습니다. `audio-only-qa.scores.json`은 실제 실행 출력의 진단값이며, 공정한 모델 비교 결과나 독립적인 일반화 증거로 제시하지 마세요. 음성 전사에는 주입 위치 밖의 오류가 남을 수 있어 초안을 전체 음성 전사로 대체하면 정상 구간을 훼손할 수 있습니다. 교정 실험에서는 같은 모델·생성 설정의 Audio only / Text only / Audio + draft를 비교하여 텍스트 문맥만으로 풀리는 비율을 함께 보고하세요.

원천 전사·생성 코드가 공개되어 정답을 복원할 수 있습니다. 원문 조회 금지 규칙만으로 완전히 비밀인 테스트셋이 되지는 않습니다. 이 데이터는 **공개 코퍼스에서 구성한 수업용 고정 교정 벤치마크**이며 새로운 비공개 한국어 음성 이해 성능의 증명으로 해석하지 않습니다. 별도 사람 검수가 필요할 때 운영자 검수표를 사용하고 변경 사항은 새 버전으로 배포하세요.

## 평가와 실행

주지표는 Clean/Single/Multiple 조건 CER의 동일 비중 평균인 Macro CER ↓입니다. 오류 구간 복원률 ↑, 정상 구간 훼손률 ↓, Clean 변경률 ↓, 초안 대비 개선폭(%p)도 기록합니다. 공백과 지정 문장부호는 제외하고 숫자 읽기·동의어를 정답으로 자동 치환하지 않습니다. 규격은 `server/scoring.py`의 `ko-correction-v1`입니다.

```sh
python -m scripts.validate_dataset --dataset datasets/{NAME}
python -m scripts.validate_dataset --dataset datasets/{NAME} --private private-data/{NAME} --source-cache /path/to/fleurs-cache
python -m scripts.baseline --mode copy --inputs datasets/{NAME}/eval/inputs.json --output /tmp/tye-v2-copy.csv
python -m scripts.evaluate --references private-data/{NAME}/eval-references.json --predictions /tmp/tye-v2-copy.csv
```

웹 평가 서버에는 `REFERENCE_PATH=/absolute/path/private-data/{NAME}/eval-references.json`을 설정합니다. 외부 채점 서버의 배포 완료를 뜻하지는 않습니다.

## 재현

Apple Silicon에서 사용한 검증 모델·revision·패키지는 `scripts/transcribe_audio.py`와 `requirements-audio-qa.txt`에 고정했습니다. 다른 환경에서 모델 전사 결과가 달라질 수 있으므로 배포 파일의 `release-lock.json`을 최종 파일 판정 기준으로 사용하세요. 원천 전체 음성 다운로드는 약 1.76 GB입니다.

```sh
pip install -r requirements-audio-qa.txt
python -m scripts.build_final_dataset prepare --cache /path/to/fleurs-cache --work /path/to/new-candidate-work --previous-provenance /path/to/v1-private/provenance.json
python -m scripts.transcribe_audio --inputs /path/to/new-candidate-work/train-inputs.json --output /path/to/new-candidate-work/asr-train --model-cache /path/to/whisper-model
python -m scripts.transcribe_audio --inputs /path/to/new-candidate-work/dev-inputs.json --output /path/to/new-candidate-work/asr-dev --model-cache /path/to/whisper-model
python -m scripts.transcribe_audio --inputs /path/to/new-candidate-work/test-inputs.json --output /path/to/new-candidate-work/asr-test --model-cache /path/to/whisper-model
python -m scripts.build_final_dataset freeze --work /path/to/new-candidate-work --output /path/to/new-public-release --private /path/to/new-private-release
python -m scripts.build_final_dataset seal --output /path/to/new-public-release
```

후보·모델 출력·정답 대응표는 비공개 작업 폴더에 두세요. 고정 출력과 같은 원천·seed·사전이면 최종 파일 선택·초안·주석을 재현합니다. 기존 봉인된 버전은 덮어쓰지 않습니다.
''',encoding='utf-8')
    (output/'NOTICE').write_text('''Trust Your Ears Korean Correction v2
Source: Google FLEURS, Korean ko_kr, Conneau et al. (2022).
Authors: Alexis Conneau, Min Ma, Simran Khanuja, Yu Zhang, Vera Axelrod,
Siddharth Dalmia, Jason Riesa, Clara Rivera, Ankur Bapna.
Source: https://huggingface.co/datasets/google/fleurs
Paper: https://arxiv.org/abs/2205.12446
License: Creative Commons Attribution 4.0 International (CC BY 4.0)
https://creativecommons.org/licenses/by/4.0/
Changes: selected recordings; retained original audio/reference; synthesized
transcript draft substitutions and annotations; added split and QA metadata.
No endorsement by the source authors is implied.
''',encoding='utf-8')
    return metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['prepare','freeze','seal'])
    parser.add_argument('--cache',type=Path)
    parser.add_argument('--work',type=Path,default=Path('private-data/final-build'))
    parser.add_argument('--lexicon',type=Path,default=Path('datasets/tye-fleurs-ko-v1/substitutions.json'))
    parser.add_argument('--previous-provenance',type=Path,default=Path('private-data/tye-fleurs-ko-v1/provenance.json'))
    parser.add_argument('--output',type=Path,default=Path('datasets/tye-ko-v2'))
    parser.add_argument('--private',type=Path,default=Path('private-data/tye-ko-v2'))
    parser.add_argument('--dev-count',type=int,default=60)
    parser.add_argument('--eval-count',type=int,default=60)
    args=parser.parse_args()
    if args.stage=='prepare':
        if args.cache is None:parser.error('--cache required for prepare')
        print(prepare(args.cache,args.work,args.lexicon,args.previous_provenance))
    elif args.stage=='freeze':
        print(json.dumps(freeze(args.work,args.output,args.private,args.dev_count,args.eval_count)['splits'],ensure_ascii=False,indent=2))
    else:
        if (args.output/'release-lock.json').exists():
            raise ValueError('A sealed release cannot be resealed; create a new version.')
        for name in ('README.md','NOTICE','metadata.json','quality-report.json'):
            if not (args.output/name).is_file():raise ValueError(f'Missing release document: {name}')
        write_json(args.output/'release-lock.json',{'name':NAME,'sha256':{
            str(p.relative_to(args.output)):digest(p) for p in sorted(args.output.rglob('*')) if p.is_file()}})
        print('Public release sealed.')


if __name__=='__main__':main()
