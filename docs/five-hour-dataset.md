# 한국어 전사 교정 5시간 데이터

분할 이름은 **eval(공개, 약 1시간)**과 **test(비공개, 약 4시간)**입니다.
eval은 프롬프트·설정 개발과 공개 재현용, test는 최종 리더보드용입니다.
여기서 eval은 비공개 테스트를 뜻하지 않습니다. 실제 발화 수·초 단위 시간·조건별 수량은
배포물 `metadata.json`을 기준으로 합니다. 원본 발화를 자르지 않아 목표 시간과 수 초 차이가 날 수 있습니다.

## 구축 결과

| Split | 발화 | 시간(초) | 화자 | Clean / Single / Multiple |
|---|---:|---:|---:|---|
| public eval | 421 | 3,600.001375 | 20 | 140 / 141 / 140 |
| private test | 1,658 | 14,400.0070625 | 46 | 553 / 552 / 553 |

합계 2,079개, 18,000.0084375초입니다. [공개 다운로드·검증 보고서](../datasets/tye-ko-5h-v1/README.md)를 제공합니다. 전체 재생성의 파일별 SHA256이 일치했고, test 전체의 Copy/정답 제출을 로컬 production 모드 API로 검사했습니다. 온라인 서버 연결이나 실제 모델 실험을 뜻하지 않습니다.

## 전달 구조

```text
public/
  README.md, NOTICE, metadata.json, release-lock.json
  eval/
    audio/*.wav
    inputs.json
    references.json
    audio-checksums.json
    copy-draft.csv
    copy-draft.scores.json

private/
  README.md, NOTICE, metadata.json, release-lock.json
  test/
    audio/*.wav
    inputs.json
    audio-checksums.json
    copy-draft.csv
    copy-draft.scores.json
  test-references.json
  provenance.json
  listening-review.csv
  previous-exposures.json
  private-neighbors.json
  plan.json, selection.json
```

공개 묶음에 test 음성·초안·정답·대응표를 넣지 않습니다. Test의 음성·초안을 참가자에게
제공할 때는 `private/test/`에서 입력과 음성만 별도 배포합니다. 운영자 묶음 전체를 공개하지 않습니다.
채점 서버는 공개 입력과 분리된 `test-references.json`을 읽습니다.

## 원천과 분할

원천은 [Zeroth-Korean / OpenSLR SLR40](https://www.openslr.org/40/)의
[고정 버전 미러](https://huggingface.co/datasets/kresnik/zeroth_korean/tree/1fe937899f828af822293d05e086200946088bdf)입니다.
CC BY 4.0 저작자와 변형 사항을 NOTICE에 기록합니다.

원천 공식 train/test는 이번 연구의 공개/비공개 구분과 다릅니다. 원천을 합친 뒤 전체 화자를
그룹 단위로 나누고, 같은 문장의 다른 화자 녹음은 발화 하나로 취급합니다.
공개 eval과 이전 파일럿에 노출된 문장에 대해 비공개 test의 정규화 문장 유사도
0.85 이상을 제외합니다. 화자·세션·동일 문장·오디오·PCM 중복을 최종 배포물에서 다시 검사합니다.

공개 원천에 이미 포함된 음성이므로 비공개 test도 원문 검색이나 모델 사전학습 오염 가능성이
있습니다. 참가자는 test 원문을 조회하거나 test 정답으로 학습·튜닝하지 않는다는 운영 규칙을 따릅니다.
원천 화자 ID를 사용하는 것이며 개인 신원을 독립 확인한 것은 아닙니다.

## 전사와 합성 오류

정답은 원천 `text`의 NFC 정규화만 적용합니다. 숫자·약어·간투사를 자동 재작성하지 않고
음성인식 모델의 출력으로 바꾸지 않습니다. 원천 FLAC의 PCM16 샘플을 동일하게 WAV로 내보내며
패딩·반복·속도 변경으로 시간을 늘리지 않습니다. 자연스럽게 포함된 무음은 총 재생 시간에 포함합니다.

Kiwi가 원문과 정확히 같은 구간으로 분석한 명사에서 후보를 찾습니다. 원천의 서로 다른
문장에 두 번 이상 등장하는 명사 중 같은 길이·같은 조사 결합 유형(무받침/ㄹ/그 외 받침)이고 자모 성분 하나가 다른
실제 단어를 우선 치환합니다. 그런 단어가 없으면 두 성분 차이까지 허용합니다.
단순 동음 후보 일부를 제외하지만 완전한 표준발음 변환을 구현한 것은 아닙니다.

모든 조건은 두 곳의 독립 오류를 주입할 수 있는 같은 후보 집합에서 뽑습니다.
Clean은 정답 그대로, Single은 한 곳, Multiple은 정상 문자가 사이에 남는 두 곳을 치환합니다.
길이별 세 발화 묶음에 조건을 섞어 배정하고, 조건별 수량 차이를 최대 1개로 제한합니다.

실제 ASR 오류에서 관측한 확률 분포가 아닌 **합성 실단어 치환**입니다. 문맥만으로 복원되는
오류도 있으므로 text-only·audio-only·audio+draft와 비교해야 합니다.
합성 오류 사전과 원본 대응표는 test 정답 역추적을 줄이기 위해 운영자 묶음에 보관합니다.
공개 생성 코드가 있다고 test 오염 문제가 해결되는 것은 아닙니다.

## 재생성

저장소 루트에서 전용 환경과 원천 캐시를 준비합니다. 모델 추론 서버에는 이 의존성이 필요하지 않습니다.

```sh
pip install -r requirements-build-5h.txt
python -m scripts.zeroth_source fetch --cache /data/zeroth-source \
  --files test-00000-of-00001.parquet train-00000-of-00006.parquet train-00001-of-00006.parquet train-00002-of-00006.parquet
python -m scripts.zeroth_source index --cache /data/zeroth-source --output /data/source-index.json \
  --files test-00000-of-00001.parquet train-00000-of-00006.parquet train-00001-of-00006.parquet train-00002-of-00006.parquet

python -m scripts.build_five_hour_dataset prepare \
  --index /data/source-index.json \
  --exposures /data/organizer/previous-exposures.json \
  --work /data/build-plan

python -m scripts.build_five_hour_dataset export \
  --cache /data/zeroth-source --work /data/build-plan \
  --public /data/public --private /data/private

python -m scripts.validate_five_hour_dataset \
  --public /data/public --private /data/private \
  --source-cache /data/zeroth-source --output /data/validation-report.json
```

`previous-exposures.json`은 운영자 묶음에 있습니다. 원천 ZIP pilot160의 전사와 이전
FLEURS 배포 자료를 보수적으로 제외한 목록이며, 비공개 배포물에서 재현에 사용합니다.
생성 코드는 기존 배포 폴더를 덮어쓰지 않습니다. 정답·치환·분할을 바꾸면 새 버전으로 생성합니다.

## 평가와 웹 서버

```sh
python -m scripts.baseline --mode copy --inputs /data/public/eval/inputs.json --output /tmp/eval-copy.csv
python -m scripts.evaluate --references /data/public/eval/references.json --predictions /tmp/eval-copy.csv
REFERENCE_PATH=/data/private/test-references.json uvicorn server.app:create_app --factory
```

팀별 제출 CSV는 test 입력 ID 전체를 포함해야 합니다. 기존 한국어 `ko-correction-v1`의
Macro CER·오류 구간 복원률·정상 구간 훼손률·Clean 변경률을 그대로 사용합니다.
대규모 제출을 수용하도록 계산량 상한만 늘렸으며 지표 정의와 순위 계산은 변경하지 않습니다.
서로 다른 정답 파일은 서버가 내용 해시로 구분해 같은 리더보드에 섞지 않습니다.

## 검수 상태

배포 시점은 **독립 청취 미검수**입니다. 소프트웨어 검증과 Copy/정답 제출 검사는 실제 음성의
정확성이나 모델 성능을 증명하지 않습니다. 자동 음성인식 결과를 정답 검수로 간주하지 않습니다.
최종 운영 전 청취 검수표에서 원천 전사·오류 단어의 식별 가능성·발화 잘림을 확인해야 합니다.
검수로 데이터가 바뀌면 해당 버전의 점수와 리더보드도 분리합니다.
