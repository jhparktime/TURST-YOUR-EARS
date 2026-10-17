# Trust Your Ears

**한국어 음성 + 전사 초안 → 실제 발화에 맞게 교정한 전체 전사문.**

음성을 근거로 초안의 오류를 복원하면서 원래 맞던 부분을 보존하는 **Audio-grounded Transcript Correction** 챌린지입니다. 음성과 원천 정답 전사는 바꾸지 않습니다.

**현재 제출 후보: 실제 ASR v2.** Whisper·Qwen의 실제 음성인식 출력을 초안으로 사용합니다.
Train 472개·약 1시간 13분 / 공개 Eval 409개·1시간 / 비공개 Test 1,750개·4시간입니다.
주 지표는 **Micro CER**이며 누락·삽입을 포함한 오류 복원과 정상 구간 보존을 함께 평가합니다.
데이터 구축·자동 무결성 검사·웹 공개 채점은 완료했습니다. 독립 청취 검수는 아직입니다.
Copy·Whisper·Qwen Audio-only·Qwen Text-only의 Eval/Test 측정 8건을 공개했고,
Audio+draft의 새 초안 추론은 진행 중입니다. 미완료 점수는 표시하지 않습니다.

[v2 웹사이트](https://jhparktime.github.io/TURST-YOUR-EARS/v2.html) ·
[참가자 데이터 프리릴리스](https://github.com/jhparktime/TURST-YOUR-EARS/releases/tag/dataset-ko-asr-v2) ·
[평가 규격과 한계](docs/real-asr-v2.md) · [현재 측정 결과](docs/real-asr-v2-results.md) ·
[제출 준비 상태](docs/submission-readiness.md)

**공개 Eval 보조 트랙:** 같은 409개 녹음에 원본·합성 잡음 5 dB·패킷 손실 20%를 적용한
[음질 손상 실험](docs/public-eval-stress-probe.md)을 추가합니다. 변형은 1,227개이며 서로 다른 녹음은 1시간입니다.
초안은 손상 전 음성에서 생성됐다는 정보 비대칭을 명시합니다. 손상 음성의 모델 비교는 아직이며,
기존 v2 전체 추론 이후에 순차 실행합니다. 비공개 Test와 공식 순위는 변경하지 않습니다.

## v2 공개 Eval 재현

참가자 ZIP의 압축을 푼 뒤 아래 경로를 실제 위치로 바꿉니다.
Python 3.12 이상에서 저장소 루트를 작업 폴더로 사용합니다. Copy와 채점은 표준 라이브러리만
사용하므로 추가 패키지나 GPU가 필요하지 않습니다. `requirements.txt`는 채점 서버 실행용입니다.

```sh
python -m scripts.baseline --mode copy --inputs /data/tye-v2/eval/inputs.json --output /tmp/v2-copy.csv
python -m scripts.evaluate --references /data/tye-v2/eval/references.json --predictions /tmp/v2-copy.csv
```

결과는 `ko-correction-v2`, `primary_metric: micro_cer`, Micro CER **11.766335975170426%**입니다.
같은 CSV를 v2 사이트에 업로드하면 브라우저 안에서 채점됩니다. 비공개 Test 채점 API는 아직 연결하지 않았습니다.
Test 정답과 운영자 자료는 공개 저장소에 포함하지 않습니다.
새 공개 저장소 사본과 릴리스 ZIP에서 외부 패키지를 비활성화한 상태로 재현했고, 전체 지표 JSON이 배포 기준값과 일치했습니다.
[참가자 환경 검증 기록](docs/measurements/real-asr-v2-participant-reproduction.json)을 제공합니다.

측정용 Qwen 실행기는 [scripts/run_omni_baselines.py](scripts/run_omni_baselines.py)입니다.
고정된 Thinker 가중치·BF16·MPS·512토큰·greedy 설정으로 실제 측정을 수행하며 중단 시 같은 설정으로 재개합니다.
[모델 버전 및 초안 생성 규칙](docs/real-asr-v2.md)을 확인하고, 모델 실행 의존성은
`requirements-omni.txt`를 설치합니다. 공개 Eval만 재현하는 예는 다음과 같습니다.

```sh
python -m scripts.run_omni_baselines \
  --public /data/tye-v2 --private /data/unused-private \
  --model-cache /path/to/fixed-qwen-snapshot --work /data/v2-public-inference \
  --modes text-only audio-draft --splits eval --max-new-tokens 512
```

출력은 작업 폴더의 `eval/text-only.csv`, `eval/audio-draft.csv`에 생성됩니다.
각 CSV를 같은 공개 Eval 정답으로 채점합니다. `--splits eval` 실행은 비공개 자료를 읽지 않습니다.
간단한 단일 모드 `scripts.baseline`의 모델 실행은 자동 장치·dtype를 쓰는 편의 기능이므로,
공식 수치를 재현하려면 위의 고정 설정 실행기를 사용합니다.
빈 출력이나 고정 토큰 한도 도달 출력은 바꾸거나 재시도하지 않고 실제 결과 그대로 채점합니다.

## 보존한 합성 오류 v1 기록

아래는 `tye-ko-merged-v1 / ko-correction-v1`의 기존 설명입니다.
v1과 v2의 초안 및 Macro CER 정의가 다르므로 결과를 같은 순위에 섞지 않습니다.

[v1 웹사이트](https://jhparktime.github.io/TURST-YOUR-EARS/) · [간단 실행 코드](scripts/baseline.py) · [v1 채점 코드](server/scoring.py)

**v1 데이터 기록:** [통합 데이터 merged v1](datasets/tye-ko-merged-v1/README.md)을 구성했습니다. 기존 5시간 자료와 추가 train/eval 자료 4,081개·약 9시간 42분을 모두 보존하고, **train 472개·약 1시간 13분 / 공개 eval 409개·1시간 / 비공개 test 1,750개·4시간**으로 다시 분할했습니다. 나머지 1,450개는 중복·평가 화자·목표 시간 초과 사유와 함께 운영자 예비 풀에 보관합니다. 전체 4,081개 음성 복호화와 분할·채점 검증을 통과했고, 새 eval/test 2,159개에서 Copy와 Whisper 평가를 완료했습니다. Qwen Text-only·Audio-only·Audio+draft도 각각 eval/test 2,159개 전체 평가를 완료했습니다. 다섯 방법의 split별 측정 10건을 모두 제공합니다. 독립 청취 검수는 아직입니다. [통합·재현·추론 안내](docs/merged-dataset.md)를 확인하세요. 새 train에 이전 test 일부가 포함되므로 새 학습 정답 공개 시 이전 test는 종료된 버전으로 보관합니다.

## 과제 정의

모델은 음성과 초안만 봅니다. 오류 유무·위치·개수나 정답을 제공하지 않습니다. 초안이 맞으면 유지하고, 오류가 있으면 해당 부분을 수정하여 **전체 전사문**을 출력합니다. 발화를 요약하거나 문법에 맞게 다듬는 과제가 아닙니다.

| 조건 | 초안 생성 | 확인할 행동 |
|---|---|---|
| `clean` | 정답 전사를 그대로 사용 | 맞는 초안 보존 |
| `single` | 한 구간 치환 | 오류 한 곳 복원 |
| `multiple` | 떨어진 두 구간 치환 | 여러 오류 복원과 정상 구간 보존 |

한 구간은 이름·숫자·내용어 등 하나의 표현입니다. 문자 하나씩 나누어 오류 개수를 부풀리지 않습니다. 원본 발화가 “김민서가 네오젠 실적을 발표합니다.”이면 Single 초안은 “김민수가 네오젠 실적을 발표합니다.”가 될 수 있습니다. 정답은 항상 원본 발화입니다.

첫 규격은 원본 음성과 치환 오류에 한정합니다. 잡음, 삽입·삭제 오류, 실제 ASR이 생성한 초안은 별도 후속 실험으로 구분합니다. Clean은 별도 음성 품질 조건이 아니라 **초안에 주입 오류가 없다는 뜻**입니다.

연구 제안 **Verify Before You Correct**는 초안과 독립적인 ASR 결과의 불일치 구간을 찾고, 음향적 근거에 따라 수정 여부를 결정하는 방법입니다. 현재 제공하는 단순 베이스라인과 구분하며, 검증 모듈 및 성능 개선은 아직 구현·입증되지 않았습니다. [음성·텍스트 충돌 관련 선행 연구](https://aclanthology.org/2025.emnlp-main.246/)가 있으므로 충돌 자체를 독창성으로 주장하지 않습니다.

## 빠른 실행

Python 3.12 이상, 저장소 루트에서 실행합니다.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m scripts.baseline --mode copy --inputs examples/demo-inputs.json --output /tmp/tye-copy.csv
python -m scripts.evaluate --references examples/demo-references.json --predictions /tmp/tye-copy.csv
DEMO_MODE=1 uvicorn server.app:create_app --factory --host 127.0.0.1 --port 8000
```

[로컬 제출 화면](http://127.0.0.1:8000/#submit)에서 **공개 샌드박스 키 사용**을 선택하고 `/tmp/tye-copy.csv` 또는 [예시 CSV](web/assets/sample-submission.csv)를 업로드합니다. 공개 키는 `demo-team-key`입니다. 웹과 로컬 평가가 같은 `server/scoring.py`를 사용합니다.

Copy draft의 **소프트웨어 예시** 기대값:

| 지표 | 값 |
|---|---:|
| Macro CER | 6.451612…% |
| Clean / Single / Multiple CER | 0 / 6.451612… / 12.903225…% |
| 초안 대비 개선폭 | 0%p |
| 오류 구간 복원률 | 0% (0/6) |
| 정상 구간 훼손률 | 0% |
| 무오류 초안 변경률 | 0% (0/2) |

정답을 그대로 제출하면 CER 0%, 복원률 100%입니다. 이는 테스트용 기대값이며 연구 결과나 모델 성능이 아닙니다.

```sh
python -m pytest -q
```

CI는 임시 PostgreSQL로 재시작 후 결과 보존도 확인합니다. 로컬에서 `TEST_POSTGRES_URL`이 없으면 해당 검사만 건너뜁니다. 코드 검사는 실제 청취 검수나 모델 실험을 대체하지 않습니다.

## 베이스라인

| 방법 | 입력 | 현재 상태 |
|---|---|---|
| Copy draft | 초안 | eval/test 완료 |
| Whisper large-v3-turbo | 음성 | eval/test 2,159개 완료 |
| Qwen2.5-Omni-3B · Text-only | 초안 | eval/test 2,159개 완료 |
| Qwen2.5-Omni-3B · Audio+draft | 음성 + 초안 | eval/test 2,159개 완료 |
| Qwen2.5-Omni-3B · Audio-only | 음성 | eval/test 2,159개 완료 |

[전체 지표](docs/baseline-results.md)와 [분자·분모 및 조건별 결과 JSON](web/data/baselines.json)을 제공합니다.
[합성 오류의 난이도 점검](docs/difficulty-audit.md)과 [공개 eval의 선택적 교정 진단](docs/measurements/selective-public-eval/README.md)도 제공합니다. 후자는 생성 규칙을 아는 단순 필터의 개발용 분석이며 비공개 Test 결과나 독창성의 증거가 아닙니다.
미완료 실험에는 점수를 넣지 않습니다. Whisper는 초안을 보지 않았으며,
Whisper와 Qwen의 차이를 입력 방식만의 효과로 해석하지 않습니다.
같은 Qwen 체크포인트와 생성 설정을 사용하는 세 입력 비교로 음성의 추가 이득을 확인합니다.
각 발화는 새 대화이고 정답·오류 위치·조건은 추론 입력에 넣지 않습니다.

Qwen Audio+draft의 전체 평가를 완료했습니다. Test Macro CER는 Text-only 10.6928%에서
Audio+draft 4.3833%로 낮아졌지만, Copy 2.7211%보다 높습니다. 오류 복원률은
1,181/1,751(67.45%), 정상 구간 훼손률은 2,106/70,783(2.98%)이며,
정상 초안 583개 중 151개(25.90%)를 바꿨습니다. [전체 실행·검증 증빙](docs/measurements/qwen-audio-draft-completed.json)에
생성 한도 도달 출력 1개를 포함한 실제 결과를 보관했습니다. 공개 eval에서 같은 모델 Audio-only의 Macro CER는 13.9612%로 Audio+draft 4.7073%보다 높습니다.
따라서 이 모델·공개 개발셋에서는 초안 제공도 도움이 됐지만, Copy 2.6263%보다 좋지는 않습니다.
[Audio-only 공개 eval 실행 증빙](docs/measurements/qwen-audio-only-eval.json)에 생성 한도 도달 출력
1개를 포함한 전체 결과를 보관했습니다. Test에서도 Audio-only 10.4046%보다 Audio+draft 4.3833%의 CER가 낮았지만, Copy 2.7211%보다 높았습니다.
[완료된 세 입력 비교와 전체 검증 증빙](docs/measurements/qwen-audio-only-completed.json)에는 세 모드
6,477개 예측의 입력·출력 일치 확인과 생성 한도 진단을 포함합니다. Qwen 세 모드는 각각 Test에서
1개가 생성 한도에 도달했고, Audio-only는 eval에서도 1개가 도달했습니다. 모두 실제 출력 그대로
채점했으며 빈 출력은 없었습니다.

Apple Silicon 로컬 실행은 음성 이해 인코더를 유지한 Thinker를 사용합니다.
음성 출력 가중치는 불러오지 않습니다. 모델 스냅샷은
`Qwen/Qwen2.5-Omni-3B@f75b40e3da2003cdd6e1829b1f420ca70797c34e`으로 고정합니다.

```sh
pip install -r requirements-omni.txt
python -m scripts.run_omni_baselines \
  --public /data/merged-public --private /data/merged-private \
  --model-cache /path/to/fixed-qwen-snapshot --work /data/private-omni-results
python -m scripts.evaluate --references /data/merged-private/test-references.json \
  --predictions /data/private-omni-results/test/audio-draft.csv --output /data/audio-draft.scores.json
```

생성은 seed 0, greedy, 최대 새 토큰 512개, 출력 후처리는 앞뒤 공백 제거로 고정합니다.
입력·모델 파일 해시, 패키지 버전, 하드웨어, 실제 프롬프트를 기록하고 발화마다 체크포인트를 저장합니다.
중단 후 같은 설정으로만 재개할 수 있습니다. 고정 출력 한도에 도달한 텍스트와 빈 출력도
실제 생성 결과 그대로 채점하고 각각의 횟수를 기록합니다. 누락 가중치 같은 실행 오류는 중단하며,
실패한 예측을 정답이나 초안으로 채우지 않습니다. smoke test는 공개 eval에서만 실행합니다.
텍스트 전용 입력에는 음성이나 ASR 결과를 넣지 않습니다.

[간단한 단일 모드 CLI](scripts/baseline.py)도 제공합니다. Copy는 모델 설치 없이 실행됩니다.
모델 이용 조건은 [공식 모델 카드](https://huggingface.co/Qwen/Qwen2.5-Omni-3B)를 확인하세요.

## 현재 통합 데이터와 추론

[merged v1 데이터 카드](datasets/tye-ko-merged-v1/README.md)와 [통합·재분할 안내](docs/merged-dataset.md)가 현재 구성의 기준입니다. 음성과 정답을 바꾸지 않고 화자·세션·동일/근접 문장·PCM이 split 사이에 겹치지 않도록 구성했습니다. 실제 eval/test 분량은 원본 발화를 유지한 채 목표 1시간/4시간에서 0.3초 이내입니다.

새 공개 manifest는 `datasets/tye-ko-merged-v1/`에 있고, 음성 포함 공개용 폴더와 모든 원본을 보존한 운영자 폴더는 별도 전달합니다. [새 참가자 ZIP](https://github.com/jhparktime/TURST-YOUR-EARS/releases/tag/dataset-ko-merged-v1)과 GitHub Pages를 새 버전으로 반영했습니다. 비공개 test의 외부 채점 서버 연결은 별도입니다. 기존 데이터 버전의 점수와 혼합하지 않습니다.

Copy 기준점의 Macro CER는 train 2.504184%, eval 2.626332%, test 2.721091%입니다. 고정된 Whisper large-v3-turbo를 새 eval/test 2,159개에 음성만 입력해 실행 완료했습니다. 이는 위 Qwen2.5-Omni 기반 동일 모델 세 입력 비교 실험과 별도입니다.

```sh
pip install -r requirements-asr-mlx.txt
python -m scripts.run_merged_baselines --public /data/merged-public --private /data/merged-private --work /data/private-results --model-cache /data/whisper-turbo
```

## 이전 5시간 데이터 v1 · 재현 기록

[5시간 데이터 카드](datasets/tye-ko-5h-v1/README.md)와 [구축·인계 안내](docs/five-hour-dataset.md)는 이전 버전의 기록입니다. Zeroth-Korean의 실제 음성을 사용하고 전사 초안에만 합성 치환을 넣었습니다. 공개 eval은 개발·튜닝용이며, 비공개 test는 최종 리더보드용입니다. 원천 공식 train/test를 합친 뒤 화자와 문장을 새로 분할했습니다.

| Split | 발화 | 재생 시간 | 공개 범위 |
|---|---:|---:|---|
| eval | 421 | 1시간 | 음성·초안·정답 |
| test | 1,658 | 4시간 | 운영자 비공개; 참가자 입력은 별도 배포 |

[공개 eval ZIP](https://github.com/jhparktime/TURST-YOUR-EARS/releases/download/dataset-ko-5h-v1/trust-your-ears-ko-5h-v1-public-eval.zip)을 내려받아 사용합니다. Git에는 공개 manifest와 검증 보고서를 보관하며, 음성 파일은 release ZIP에 있습니다. 비공개 정답·원본 대응표·청취 검수표는 로컬 `private-data/tye-ko-5h-v1/`에 있고 공개 release에 포함하지 않습니다.

```sh
python -m scripts.baseline --mode copy --inputs /data/tye-ko-5h-v1-public/eval/inputs.json --output /tmp/eval-copy.csv
python -m scripts.evaluate --references /data/tye-ko-5h-v1-public/eval/references.json --predictions /tmp/eval-copy.csv
REFERENCE_PATH=/data/private/test-references.json uvicorn server.app:create_app --factory
```

독립 원본 2,079개를 사용해 총 18,000.0084375초를 구성했습니다. 패딩·반복·속도 변경은 없으며 자연 무음은 포함합니다. 정답은 원천 전사의 NFC만 적용했습니다. Clean/Single/Multiple은 각각 0/1/2곳의 치환이며, split별 조건 수는 최대 1개 차이입니다. 화자·세션·문장·PCM 중복과 이전 노출 전사에 대한 test 근접 중복을 검사했습니다.

**이전 버전 구축 당시 독립 청취 검수와 블라인드 ASR 검증은 수행하지 않았습니다.** 공개 원천 검색·사전학습 오염 가능성도 남습니다. Copy/정답 제출은 소프트웨어 검사이며 모델 성능이 아닙니다. 새 데이터는 이전 FLEURS v2 및 pilot160과 점수를 섞지 않습니다.

### 이전 FLEURS v2

[이전 120개·약 25분 38초 파일럿](datasets/tye-ko-v2/README.md)과 [기존 release](https://github.com/jhparktime/TURST-YOUR-EARS/releases/tag/dataset-v2.0.0)는 재현 기록으로 유지합니다. 해당 버전에만 적용된 자동 ASR 선별과 진단 결과를 새 5시간 데이터의 검증 결과로 해석하지 않습니다.

### 첨부 Zeroth pilot160의 전사 교정 변환

별도 전달된 참고자료 실험용 pilot160을 현재 전사 교정 규격으로 변환하는 [가져오기 코드](scripts/import_pilot160.py)도 제공합니다. **개발 123개(각 조건 41개), 평가 27개(각 조건 9개), 예비 10개**입니다. 기존 FLEURS v2와 별도 파일럿이며 점수를 혼합하지 않습니다. 원천 전사를 그대로 사용하고, 첨부 자료의 숫자·약어 자동 변환 및 alias 허용 규칙은 적용하지 않습니다. 독립 청취 검수와 블라인드 ASR 검증은 수행하지 않았습니다.

코드가 원본 ZIP의 고정 SHA256·내부 manifest·음성을 검사합니다. 첨부된 실행 파일은 실행하지 않습니다. 원본 ZIP과 평가 정답은 공개 저장소에 포함하지 않았습니다. 사용법과 분할 근거는 [변환 안내](docs/pilot160-import.md)에 있습니다.

## 데이터 계약

데이터 담당자는 **공개 입력**, **비공개 평가 정답**, **출처·검수 기록**을 분리해 전달합니다. 원본 전사 일부를 변경해 초안을 만들며, 정답 파일을 수정하지 않습니다.

공개 `inputs.json`:

```json
{
  "name": "korean-correction-eval-v1",
  "items": [{
    "id": "eval-opaque-id",
    "audio": "audio/opaque-id.wav",
    "draft": "김민수가 네오젠 실적을 발표합니다."
  }]
}
```

각 입력 행의 필드는 정확히 `id`, `audio`, `draft`입니다. ID와 음성 파일명에 오류 조건이나 정답 단어를 넣지 않습니다. 공식 데이터의 `audio`는 실제 파일 경로이며 공개 toy 자료의 `null`과 다릅니다. 음성 사용 권한과 재배포 조건이 허용하는 형태로 파일 또는 재현 가능한 접근 방법을 제공합니다.

비공개 `references.json`의 **단일 행 예시**:

```json
{
  "id": "eval-opaque-id",
  "condition": "single",
  "reference": "김민서가 네오젠 실적을 발표합니다.",
  "draft": "김민수가 네오젠 실적을 발표합니다.",
  "edits": [{"start": 0, "end": 3, "replacement": "김민수"}]
}
```

전체 manifest는 `name`, `protocol: "ko-correction-v1"`, `conditions: ["clean", "single", "multiple"]`, `items`를 가집니다. 웹·CLI 리더보드 평가에는 세 조건이 모두 필요합니다. [공개 테스트 manifest](examples/demo-references.json)가 전체 구조 예시입니다.

`start`, `end`는 **원본 NFC 정답 문자열의 Python 문자 인덱스**이며 end는 제외합니다. JavaScript UTF-16 인덱스나 정규화 후 인덱스가 아닙니다. `replacement`는 초안에 넣은 오답입니다. 주석된 치환들을 정답에 적용했을 때 **초안과 완전히 일치**해야 합니다. Clean의 `edits`는 빈 배열이며 초안=정답입니다.

구간은 정렬되고 겹치지 않으며, 서로 사이에 정규화 후 유지되는 정상 문자 한 개 이상이 있어야 합니다. 각 치환은 채점 대상 문자를 실제로 바꿔야 하고 단순 띄어쓰기·문장부호 변경은 인정하지 않습니다. 현재 규격은 순수 삽입·삭제를 지원하지 않습니다. 숫자 소수점 등 정규화가 편집 경계에 걸려 모호해지는 주석은 거부합니다. 또한 정답→초안의 최소 편집 정렬이 기록한 치환 위치와 일치해야 합니다. 반복 표현 때문에 오류가 다른 위치에 배정되는 샘플은 구간을 재검토하거나 제외합니다. 이 검사를 통과해야 Copy draft가 거짓 복원 점수를 받지 않습니다.

### 구축과 인계 기준

1. **원천 선택·검수:** 이용 조건을 기록하고 실제 음성을 들어 정답 전사를 확인합니다. 오류 후보를 만든 사람과 별개인 팀원이 원래 발화와 오답의 청각적 구별 가능성을 검수합니다. LLM이 그럴듯하다고 판정하는 것만으로 정답을 확정하지 않습니다.
2. **분할 먼저:** 화자·원본 세션·동일 발화 및 근접 중복을 개발/평가 사이에서 분리한 뒤 초안을 만듭니다. 화자 정보가 없는 자료는 그 한계를 기록합니다. 소스 간 중복도 확인합니다.
3. **희소 치환:** 현재 merged v1은 명사 한 곳 또는 떨어진 두 곳을 치환합니다. 이름·숫자 등으로 오류 유형을 확장하거나 오류 수를 늘리는 실험은 별도 데이터 버전으로 관리합니다. 초안 CER와 문장 길이, 화자, 치환 유형의 분포를 함께 기록합니다.
4. **검수 항목:** 동일 발음이라 음성으로 구별 불가능한 오답, 명백한 비문이라 텍스트만으로 답을 찾는 오류, 조사 불일치, 숫자 표기만 다른 사례를 점검합니다. Text only가 잘 푸는 사례도 별도 분석할 수 있도록 기록합니다.
5. **누출 방지:** 공개 평가에는 원본당 초안 하나만 제공합니다. 같은 음성의 Clean과 오류 초안을 동시에 배포하지 않습니다. 모든 변형은 같은 split에 두고, 짝지은 변형 비교는 개발셋 또는 주최 측의 독립 실행에서만 합니다. 소프트웨어 fixture의 반복 발화는 이 공식 데이터 규칙의 예외이며 성능 분석에 사용하지 않습니다.
6. **인계:** 음성 파일, 공개 입력 JSON, 비공개 정답 JSON, 출처 URL·라이선스·원본 ID·화자/세션·split·음성 해시·검수자·치환 유형·생성 seed를 담은 관리 기록을 전달합니다. 공개/비공개 ID·초안이 일치하는지 확인합니다. 서버는 음성을 듣거나 출처 권리를 검증하지 않습니다.

수량은 파일럿 검수와 난도를 보고 결정합니다. 수백 문장을 새로 녹음할 필요는 없습니다. 공개 원천의 전사가 검색되거나 사전학습에 포함될 수 있으므로 비공개 정답 파일만으로 오염이 해결되지는 않습니다. 원문 조회 금지 등 참가 규칙과 한계를 공개하고, 별도 실음성 검증이 가능하면 보완합니다. 인위적 오류와 실제 ASR 오류는 결과를 섞어 해석하지 않습니다.

## 평가 규격

공통 구현: [`server/scoring.py`](server/scoring.py), **ko-correction-v1**. 현재 `tye-ko-merged-v1`의 분할·조건 수량·정답·주입 주석·파일 해시는 고정했습니다. 사람의 청취 검수 인증을 뜻하지 않습니다. 챌린지 운영 전 제출 기간과 모델/외부 데이터 사용 규칙을 공지하고, 추가 검수로 내용을 변경하면 새 데이터 버전으로 배포합니다.

### 정규화와 순위

- Unicode NFC, 영문 소문자화, 모든 공백 제거. 코드의 `IGNORED` 문장부호를 제외하고, 공백 제거 후 마침표는 양쪽이 숫자일 때만 유지합니다. `-3.5%`와 `35%`는 다릅니다.
- 한글은 자모가 아닌 음절 문자 단위입니다. 조사·어미·숫자 값을 바꾸지 않으며 숫자 읽기 확장, 별칭 정답, 의역, 의미 기반 판정은 없습니다. `3시`/`세 시`, `AI`/`에이아이`도 다릅니다. 정답 표기 규칙과 예시를 데이터에 함께 공개하세요.
- 발화별 Levenshtein 편집거리 S+D+I를 구합니다. **조건 안에서** 오류 수와 정답 문자 수를 합산한 CER을 계산하고 **세 조건을 동일 비중**으로 평균한 Macro CER로 순위를 매깁니다. Clean도 포함합니다. 점수 단위는 %이며 삽입으로 100%를 넘을 수 있습니다.
- Micro CER는 전체 문자로 가중한 비율, 최악 CER는 조건별 최대값입니다. 어절 WER는 공백으로 나눈 토큰에 같은 정규화를 적용하는 보조 지표입니다.
- 팀별 최저 Macro CER를 반올림 전 값으로 비교합니다. 정확한 동점은 공동 순위(1, 1, 3)이며 표시 시각만 제출순입니다. 같은 팀에서 동점이면 먼저 제출한 결과를 유지합니다.

### 교정 행동 진단

| 반환 필드 | 정의 | 방향 |
|---|---|---|
| `cer_improvement_pp` | 초안 Macro CER − 출력 Macro CER | ↑, %p; 음수는 악화 |
| `restoration_rate` | 전체 표현을 정답으로 복원한 주입 구간 수 / 주입 구간 수 ×100 | ↑ |
| `harmful_edit_rate` | 주입 구간 밖에서 훼손된 정답 문자 수 / 주입 구간 밖 정답 문자 수 ×100 | ↓ |
| `clean_change_rate` | 정규화 후 출력이 정답과 다른 Clean 발화 수 / Clean 발화 수 ×100 | ↓ |

복원·훼손은 **정답→출력 최소 편집 정렬**에서 계산합니다. 정렬 동점은 대각선→삭제→삽입 순서입니다. 삽입은 왼쪽 문자에 붙이고 맨 앞 삽입은 첫 문자에 붙입니다. 해당 주입 구간의 출력 전체가 정답과 같아야 복원 성공입니다. 단순히 뒤에 정답 이름을 나열해도 기존 위치를 복원한 것으로 인정하지 않습니다.

정상 구간은 주입 구간 **밖**입니다. 주입한 이름 내부에 그대로 남아 있는 글자들은 정상 구간 분모에서 제외합니다. 정상 문자에 연결된 출력이 그 문자 하나와 다르면 훼손으로 셉니다. 따라서 삭제·치환·경계 삽입을 다루지만 삽입 수 자체를 세는 오류율은 아닙니다. 반복 표현·편집 경계에 따라 정렬 결과가 달라질 수 있어, CER와 함께 읽는 진단값입니다. 주입 구간 주석 범위를 일관되게 유지해야 합니다.

진단은 전체 구간/문자/발화 수를 합산하며 조건별 평균이 아닙니다. 분자·분모도 반환하고 분모가 0이면 `null`/N/A입니다. 조건별 `cer_improvement_pp`는 해당 조건의 초안 CER−출력 CER입니다. 세 조건이 있는 공식 manifest에서도 일부 보조 지표의 분모는 0일 수 있습니다.

Copy draft는 개선폭 0, 오류 복원 0, 정상 구간 훼손 0이 기준입니다. 그러나 이 값이나 Audio + draft의 좋은 점수만으로 음성 활용 효과를 입증하지 못합니다. 같은 모델의 Text only와 비교하고, 합성 치환 규칙에 과적합했는지 별도 오류 유형·실제 ASR 초안으로 확인해야 합니다. 신뢰구간·화자 단위 bootstrap은 후속 연구 분석이며 현재 자동 채점에 포함되지 않습니다.

### 제출 및 버전

CSV는 정확히 `id,prediction` 두 열, UTF-8, 모든 ID 한 번씩입니다. BOM·따옴표로 감싼 쉼표를 지원하며 빈 예측은 삭제 오류입니다. API는 최대 2 MiB, 20,000행, ID 120자, 예측 4,000자입니다. 정답·초안은 NFC, 정규화 후 1–1,000자 및 원문 최대 4,000자, 치환 최대 4곳·치환문 최대 100자입니다. 계산량 4,000만 DP cell 한도를 적용하므로 운영자는 전체 데이터셋과 긴 예측으로 공개 전 점검해야 합니다.

기본 제출 한도는 팀별 UTC 하루 5개의 유효한 새 예측입니다. 한국 시간 오전 9시에 초기화되며 무효 파일은 차감하지 않습니다. 동일 ID/예측 매핑은 기존 결과를 반환합니다. 평가 버전과 정답 manifest 해시로 결과·이력·한도를 분리하여 예전 규격 점수를 섞지 않습니다. API는 집계값만 반환하고 개별 정답·오류 위치를 반환하지 않습니다.

## 웹 운영

상단의 **한국어 / English** 버튼으로 여섯 페이지의 설명, 접근성 문구, 채점 결과·제출 기록·리더보드·오류 안내를 전환합니다. 언어 선택만 브라우저에 저장하며, 전사 예시와 제출 파일은 한국어 원문을 유지합니다. 전환 중 팀 키·선택 파일·결과는 유지되고 추가 API 요청이나 제출은 발생하지 않습니다.

- GitHub Pages는 `web/`만 배포합니다. 정답·서버·DB는 배포하지 않습니다.
- 공개 eval은 브라우저 Worker에서 무료로 채점하며 파일을 업로드하지 않습니다. [브라우저 구현](web/scorer.js)은 Python과의 전체 공개 eval 일치 검사를 통과했습니다.
- 별도 HTTPS Python API가 팀 키를 확인하고 비공개 test 정답으로 채점합니다. 호스팅 연결은 별도입니다.
- 로컬 SQLite 또는 `DATABASE_URL`의 PostgreSQL에 팀·점수를 보관합니다.

GitHub Pages만으로 비공개 서버 채점을 실행할 수 없습니다. `web/config.js`의 `apiBase`가 비어 있으면 공개 eval 채점은 계속 사용할 수 있고, Pages는 비공개 test 서버 제출만 준비 상태로 표시합니다. 로컬에서는 같은 출처의 FastAPI에 연결됩니다. 웹과 서버의 scorer 버전이 다르면 제출을 막습니다.

배포는 GitHub Settings → Pages → GitHub Actions를 선택한 후 `main`에 push하면 테스트 후 실행됩니다. 호스팅된 API 연결은 별도 운영 단계입니다. [`render.yaml`](render.yaml)을 활용할 수 있으나 [무료 서비스의 현재 제약](https://render.com/docs/free)을 확인하고 영속 DB를 사용해야 합니다. 서버 계정·키는 이 저장소에서 발급하지 않습니다.

[무료 비공개 채점 서버 연결 안내](docs/free-evaluation-hosting.md)에 현재 Test 정답의 Secret File 전달 방법과 정확한 설정값, 연결 확인 절차를 정리했습니다. Render·Supabase 계정 연결과 실제 원격 배포 검증은 아직입니다.

```text
DEMO_MODE=0
REFERENCE_PATH=/data/private-references.json
DATA_DIR=/data
ALLOWED_ORIGINS=https://jhparktime.github.io
DAILY_LIMIT=5
SUBMISSIONS_OPEN=1
```

```sh
uvicorn server.app:create_app --factory --host 0.0.0.0 --port 8000 --workers 1
DATA_DIR=/data python -m scripts.create_team 'Team name'
```

Postgres 사용 시 신뢰하는 터미널에서 TLS 연결 문자열을 `DATABASE_URL`로 지정합니다. 브라우저 설정에 넣지 않습니다. 서버가 생성하는 `tye_private` 스키마를 브라우저용 DB API에 노출하지 않습니다. SQLite 호스팅은 영속 디스크가 필요합니다. 팀 키는 한 번 출력하고 해시만 보관하므로 개별 전달하세요. `SUBMISSIONS_OPEN=0`으로 마감 후 재시작할 수 있습니다. 공개 전 HTTPS·요청 크기 및 빈도 제한·백업과 재시작 후 결과 보존을 점검합니다.

API: `GET /api/health`, `GET /api/leaderboard`, 인증된 `GET/POST /api/submissions`. 인증: `Authorization: Bearer TEAM_KEY`. 스키마: `/api/docs`.

## 과제 제출 준비 상태

수업 제출물은 원래 설계한 학회 워크샵 스타일을 유지하며 HTML 한 개로 묶습니다.
CSS·한/영 전환·공개 eval 채점기·공개 정답·실측 벤치마크가 포함되고, 별도 서버 없이 공개 eval을 채점합니다.
비공개 test 정답·예측·음성과 관리 대응표는 포함하지 않습니다.

```sh
python -m scripts.build_submission_assets --results /data/private-baseline-results --public /data/merged-public
python -m scripts.build_course_submission --output /data/submission/Team_NAME_STUDENTID.html
```

[제출 점검표](docs/submission-readiness.md)에 필수 항목, 검증 결과와 남은 사항을 기록합니다.
새 공개 데이터 release와 웹 반영을 완료했습니다. 대표 학번 확인과 추가 모델 전체 평가를 마친 뒤 최종 파일을 확정합니다.
독립 청취 미검수와 합성 치환의 한계는 제출물에 명시합니다.
