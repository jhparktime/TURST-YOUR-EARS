# Trust Your Ears

**team03 · 박재현 · 이재왕**

**한국어 음성 + 전사 초안 → 실제 발화에 맞게 교정한 전체 전사문.**

음성을 근거로 초안의 오류를 복원하면서 원래 맞던 부분을 보존하는 **Audio-grounded Transcript Correction** 챌린지입니다. 음성과 원천 정답 전사는 바꾸지 않습니다.

**한국어 실제 ASR 오류 교정 챌린지 · v2**
Train 472개·약 1시간 13분 / 공개 Eval 409개·1시간 / 비공개 Test 1,750개·4시간입니다.
주 지표는 **Micro CER**이며 정상 구간을 얼마나 보존하는지도 함께 보여줍니다.

[챌린지·웹 채점](https://jhparktime.github.io/TURST-YOUR-EARS/) ·
[참가 규칙](docs/competition-rules.md) ·
[참가자 데이터](https://github.com/jhparktime/TURST-YOUR-EARS/releases/tag/dataset-ko-asr-v2)

## 이 대회에서 도전할 것

문장이 자연스럽더라도 실제 발화와 다를 수 있습니다. 실제 ASR 초안에서 오류를 찾아 고치고 이미 맞은 부분은 지키는 것이 목표입니다. 두 문장의 듣기 체험, 로그인 없는 Copy 웹 채점, CPU 노트북, 공동 등록 순서로 시작할 수 있습니다. 채점 결과는 CER와 함께 오류 슬롯 복원률·정상 문자 훼손률을 바로 보여줍니다.

Kaggle·Codabench도 맞춤 채점과 리더보드를 지원합니다. 우리의 참여 이유는 한국어 전사 교정에 맞춘 과제와 피드백입니다. [참가 이유](https://jhparktime.github.io/TURST-YOUR-EARS/#why) · [플랫폼 비교 근거와 운영 범위](docs/platform-comparison.md)

## 처음 참가한다면

1. [학습·추론 노트북](notebooks/01_train_baseline.ipynb)을 실행합니다. Train만으로 어절 치환 교정기를 학습하고 Eval CSV를 만듭니다. CPU와 Python 표준 라이브러리로 동작하는 text-only 입문 예제이며 LLM 미세조정과는 별도입니다.
2. [평가 노트북](notebooks/02_evaluate.ipynb)에서 Copy와 자신의 모델을 같은 코드로 비교합니다. Eval 정답은 추론에 넣지 않습니다.
3. [웹 채점](https://jhparktime.github.io/TURST-YOUR-EARS/#submit)에 CSV를 선택하면 CER와 교정·보존 지표를 확인하고 JSON으로 저장할 수 있습니다. 설치 없이 Copy 점수 체험도 가능합니다. 채점 기록은 새로고침 후에도 이 브라우저에 남습니다. 공동 순위에 등록하려면 아래 등록 묶음을 GitHub 양식으로 제출하세요.

Colab: [01 Train](https://colab.research.google.com/github/jhparktime/TURST-YOUR-EARS/blob/main/notebooks/01_train_baseline.ipynb) · [02 Evaluate](https://colab.research.google.com/github/jhparktime/TURST-YOUR-EARS/blob/main/notebooks/02_evaluate.ipynb)

Copy·Whisper·Qwen Audio-only·Text-only·Audio+draft의 Eval/Test 측정 10건을 제공합니다.
[참가자 시작 방법·기준 점수·실행 안내](docs/baseline-comparison-v2.md)를 제공합니다. Copy로 제출 흐름을 확인한 뒤 가장 좋은 제공 기준점인 Whisper에 도전해 보세요.
공개 Eval에서 Whisper는 Micro CER 6.19%, Copy는 11.77%입니다. 상세 결과는 [리더보드](https://jhparktime.github.io/TURST-YOUR-EARS/#baselines)와 [측정 기록](docs/real-asr-v2-results.md)을 확인하세요.
운영자 베이스라인과 GitHub에서 재채점한 참가 팀 최고 기록을 같은 표에 표시합니다. 웹 채점의 최근 20개 결과는 브라우저에 보관하며, [공동 등록 방법과 운영 규칙](docs/public-leaderboard.md)에 따라 제출하면 기록이 다른 참가자에게도 공개됩니다. Test는 운영자 최종 평가용으로 보관합니다.

[데이터·평가 상세 규격](docs/real-asr-v2.md) · [수업 제출 점검표](docs/submission-readiness.md) ·
[음질 손상 보조 트랙](https://jhparktime.github.io/TURST-YOUR-EARS/stress.html) ·
[보조 트랙 설계·측정 기록](docs/public-eval-stress-probe.md)

## 데이터는 어떻게 수집·구축했나

[수집·구축 기록](docs/data-collection.md)에 원천과 라이선스, 고정 버전, 통합·제외 수량,
분할 기준, 실제 ASR 초안 생성 및 검사·배포 과정을 정리했습니다.
Zeroth Korean의 기존 2,079개와 추가 2,002개를 통합한 4,081개 풀에서 2,631개를 사용합니다.
원본 음성·전사는 유지하고, v2 초안은 Whisper·Qwen의 실제 음성 단독 출력입니다.
평가 분량은 Eval 1시간 + Test 4시간이며 Train 약 1시간 13분은 별도입니다.
[사이트 요약](https://jhparktime.github.io/TURST-YOUR-EARS/#data-collection) ·
[메타데이터](datasets/tye-ko-asr-v2/metadata.json) · [자동 검증 기록](docs/measurements/real-asr-v2-validation.json)

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

## 제출 파일과 웹 운영

수업 저장소에는 `submission/Team_박재현_202220741.html` 한 파일을 제출합니다. [제출 점검표](docs/submission-readiness.md)에 필수 항목과 확인 상태를 기록합니다. 현재 공개 자산에는 본 실험 10건이 포함되며, 아래 명령으로 제출 HTML을 생성합니다. 수업 PR은 아직 생성하지 않았습니다.

저장소의 공개 v2 자산으로 단일 HTML을 생성합니다. CSS·한/영 전환·공개 Eval 정답·브라우저 채점기·벤치마크가 내장되며, 비공개 Test 정답이나 개별 예측은 포함하지 않습니다.

```sh
python -m scripts.build_course_submission_v2 --output /path/to/submission/Team_박재현_202220741.html
```

GitHub Actions는 검사를 통과한 `web/`만 Pages로 배포합니다. 공개 Eval은 브라우저 Worker에서 처리하며 제출 CSV를 서버로 보내지 않습니다. [Python 평가기](server/scoring_v2.py)와 [브라우저 평가기](web/scorer-v2.js)의 전체 공개 지표 일치를 확인했습니다.

비공개 Test 접수에는 별도 HTTPS API와 영속 DB가 필요합니다. 로컬 Test 1,750행의 채점과 재시작 후 기록 보존은 검증했지만, 외부 서비스는 연결하지 않았습니다. [v2 무료 호스팅 안내](docs/free-evaluation-hosting.md)에 정답 Secret File·DB·두 Pages 출처 연결·원격 검증 절차를 정리했습니다. 연결 전에는 `web/config-v2.js`의 `apiBase`를 비워 두고 공식 접수를 닫습니다. DB 접속 정보와 팀 키를 브라우저나 공개 저장소에 넣지 않습니다.

## 코드 검사

Python 3.12 이상과 Node.js에서 저장소 루트를 작업 폴더로 사용합니다.

```sh
pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/test_i18n.cjs
```

CI는 임시 PostgreSQL로 재시작 후 결과 보존도 확인합니다. 로컬에서 `TEST_POSTGRES_URL`이 없으면 해당 검사만 건너뜁니다. 자동 검사와 Copy 재현은 소프트웨어 동작을 확인합니다. 모델 성능과 난도는 실측 결과로 비교합니다.

## 과거 실험 기록

합성 명사 치환을 사용한 `tye-ko-merged-v1 / ko-correction-v1`과 현재 실제 ASR v2는 별도 버전입니다. v1의 조건별 CER 평균과 v2의 발화별 Macro CER 정의도 다르므로 점수를 같은 순위에 섞지 않습니다. 기존 원본·실험·평가 코드는 재현용으로 유지합니다.

- [합성 오류 v1 웹사이트](https://jhparktime.github.io/TURST-YOUR-EARS/archive-v1.html) · [데이터 통합·분할](docs/merged-dataset.md) · [베이스라인 결과](docs/baseline-results.md)
- [v1 난이도 점검](docs/difficulty-audit.md) · [공개 Eval 선택적 교정 진단](docs/measurements/selective-public-eval/README.md) · [v1 평가기](server/scoring.py)
- [이전 5시간 데이터](docs/five-hour-dataset.md) · [Zeroth pilot160 변환](docs/pilot160-import.md) · [FLEURS 파일럿](datasets/tye-ko-v2/README.md)
