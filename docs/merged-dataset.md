# 전체 자료 통합과 새 분할

데이터 버전은 `tye-ko-merged-v1`, 평가 규격은 기존 `ko-correction-v1`입니다.
기존 5시간 자료 2,079개와 추가 train/eval 자료 2,002개를 모두 읽어
4,081개·34,927.3378125초·115명의 원본 풀로 통합했습니다.
음성은 재합성하지 않고 기존 원본 PCM을 그대로 보존했습니다.

| Split | 녹음 | 실제 재생 시간 | 화자 | Clean / Single / Multiple |
|---|---:|---|---:|---|
| train | 472 | 1시간 13분 15.9708125초 | 63 | 157 / 150 / 165 |
| eval | 409 | 1시간 0.0348125초 | 20 | 137 / 136 / 136 |
| test | 1,750 | 3시간 59분 59.81675초 | 32 | 583 / 583 / 584 |

활성 분할은 총 2,631개·22,395.822375초입니다. train과 eval의 정답은 공개용,
test 정답은 운영자 전용입니다. 모든 분할은 독립 청취 미검수 상태입니다.

## 모든 원본을 보존하면서 중복을 처리하는 방법

같은 문장을 다른 화자가 읽은 녹음은 시간·화자·PCM이 다르지만 정답 문장이 같습니다.
무작위로 분할하면 학습 정답이 평가에 그대로 나타날 수 있습니다. 반대로 화자와 동일 문장을
모두 하나의 연결 그룹으로 묶으면 3,607개·약 8시간 32분이 한 그룹이 되어
공개 eval 1시간·비공개 test 4시간 목표를 맞출 수 없습니다.

따라서 모든 4,081개 녹음과 원래 초안·정답·출처를 운영자 `source-pool`에 보존한 뒤
실제 실험용 분할에는 독립적인 문장 하나당 녹음 하나만 배정했습니다.

1. 기존 공개 eval의 화자 그룹을 새 eval 후보로 유지합니다. 해당 그룹 안에서 전체 풀을
   다시 선정해 공개 eval 약 1시간을 구성합니다.
2. 기존 공개 eval 및 추가 정답 포함 train의 화자는 새 test에서 제외합니다.
   남은 32명의 후보에서 이미 노출된 정답과 동일·유사한 문장도 제외한 뒤 test 약 4시간을 뽑습니다.
3. eval/test의 화자 그룹과 겹치지 않고 정답 문장도 겹치지 않는 나머지를 train에 배정합니다.
   정상·단일·복수 오류 분포를 위해 일부 녹음을 임의로 버리지는 않습니다.
4. eval/test 조건은 동일한 두 곳 치환 가능 후보 안에서 문장 길이 순 세 개씩 묶어 다시 배정합니다.
   train은 원래 초안을 유지합니다. 음성인식 결과나 모델 점수는 선정에 사용하지 않았습니다.

예비 풀 1,450개는 삭제하지 않았습니다. 선택한 eval/test와 동일한 문장 1,281개,
근접 문장 1개, 평가 화자의 대체 녹음·시간 초과 168개입니다.
예비 풀도 평가 정답을 포함하므로 학습·프롬프트 튜닝에 사용하면 안 됩니다.

**이전 비공개 test 일부가 새 train으로 이동했습니다. 새 train 정답을 공개하면
이전 test 버전은 종료해야 하며, 이전 점수와 새 점수를 같은 리더보드에서 비교하지 않습니다.**

## 전달 구조

```text
public/
  README.md, NOTICE, metadata.json, release-lock.json
  train/{inputs.json,references.json,audio-checksums.json,copy-draft.csv,copy-draft.scores.json,audio/}
  eval/{inputs.json,references.json,audio-checksums.json,copy-draft.csv,copy-draft.scores.json,audio/}
private/
  README.md, NOTICE, metadata.json, release-lock.json
  test/{inputs.json,audio-checksums.json,copy-draft.csv,copy-draft.scores.json,audio/}
  test-references.json
  provenance.json, listening-review.csv, previous-exposures.json
  reserved.json, source-pool.json, source-pool/audio/
```

원천 대응표·기존 분할·예비 사유는 private에만 있습니다. 참가자에게 test 입력을 전달할 때는
`test/inputs.json`, `test/audio-checksums.json`, `test/audio/`만 별도로 묶습니다.
운영자 폴더 전체나 source-pool은 공개하지 않습니다.

## 재생성과 검증

첨부 실행 코드를 사용하지 않고 저장소의 병합·검증 코드로 생성했습니다.
입력 묶음은 수정하지 않으며, 출력 폴더가 있으면 덮어쓰기를 거부합니다.
분할 seed는 `20261016`이고 모든 선정은 고정된 우선순위로 재현합니다.

```sh
python -m scripts.merge_correction_datasets \
  --old-public /data/5h-public --old-private /data/5h-private \
  --incoming-public /data/incoming-participant --incoming-private /data/incoming-organizer \
  --public /data/merged-public --private /data/merged-private

python -m scripts.validate_merged_dataset \
  --public /data/merged-public --private /data/merged-private \
  --output /data/merged-validation.json
```

독립 검증은 보관한 4,081개 전체를 복호화해 WAV/PCM 해시를 확인하고,
활성 2,631개 입력·정답·주석·분량·조건·대조군 점수를 재검사합니다.
세 split 사이 화자·세션·원문·PCM 및 SequenceMatcher 유사도 0.85 이상 문장 겹침을 검사합니다.
test와 이미 노출된 전사도 같은 기준으로 비교합니다.

## 베이스라인 실행

Copy 기준점은 전체 train/eval/test에서 완료했습니다.
Whisper large-v3-turbo는 새 eval 409개와 test 1,750개, 총 2,159개를 대상으로
음성만 입력해 추론 완료했습니다. 초안·정답·조건·원천 전사는 모델 입력에 넣지 않습니다.
이 실행은 README의 Qwen2.5-Omni 세 입력 비교 실험과 별도입니다.

| 모델/대조군 | train Macro CER | eval Macro CER | test Macro CER |
|---|---:|---:|---:|
| Copy draft | 2.504184% | 2.626332% | 2.721091% |
| Whisper audio-only | 미실행 | 6.186411% | 5.342357% |

```sh
pip install -r requirements-asr-mlx.txt
python -m scripts.run_merged_baselines \
  --public /data/merged-public --private /data/merged-private \
  --work /data/private-baseline-results --model-cache /data/whisper-turbo
```

Apple Silicon 환경에서 실행합니다. 모델은 고정 커밋
`mlx-community/whisper-large-v3-turbo@a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb`을 사용합니다.
언어 ko, temperature 0, initial prompt 없음, 이전 발화 문맥 재사용 없음으로 고정했습니다.
모델 다운로드를 제외한 음성 추론은 로컬에서 수행합니다.

`status.json`은 실행 상태, `audio-only/audio-only.json`은 중단 후 재개할 체크포인트입니다.
완료하면 eval/test 각각의 예측 CSV와 채점 결과를 저장합니다.
기존 블라인드 음성인식 결과는 같은 모델·설정·정확히 같은 WAV 해시일 때만 재사용하며,
재사용한 파일 해시·행 수를 `reuse.json`에 기록합니다.
모든 예측과 test 점수는 운영자 작업 폴더에 보관합니다.

숫자의 한글/아라비아 표기 차이가 CER에 반영되는 기존 정규화 규칙을 유지합니다.
좋거나 나쁜 ASR 결과를 보고 정답·표기·분할을 바꾸지 않습니다.
독립 청취 검수, text-only 및 audio+draft 모델 비교, 외부 채점 서버 연결은 별도 검증 단계입니다.

실측 전체 지표는 [베이스라인 결과](baseline-results.md), 난이도 한계는 [난이도 점검](difficulty-audit.md)을 확인하세요. 공개 eval은 사이트에서 CSV를 외부로 보내지 않고 채점할 수 있습니다.
