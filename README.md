# Trust Your Ears

**한국어 음성 + 전사 초안 → 실제 발화에 맞게 교정한 전체 전사문.**

음성을 근거로 초안의 오류를 복원하면서 원래 맞던 부분을 보존하는 **Audio-grounded Transcript Correction** 챌린지입니다. 음성과 원천 정답 전사는 바꾸지 않습니다.

**현재 제출 후보: 실제 ASR v2.** Whisper·Qwen의 실제 음성인식 출력을 초안으로 사용합니다.
Train 472개·약 1시간 13분 / 공개 Eval 409개·1시간 / 비공개 Test 1,750개·4시간입니다.
주 지표는 **Micro CER**이며 누락·삽입을 포함한 오류 복원과 정상 구간 보존을 함께 평가합니다.
데이터 구축·자동 무결성 검사·웹 공개 채점은 완료했습니다. 독립 청취 검수는 아직입니다.
Copy·Whisper·Qwen Audio-only·Text-only·Audio+draft의 Eval/Test 측정 10건을 완료했습니다.
Test Micro CER는 Audio+draft 9.56%, 같은 Qwen의 Audio-only 10.40%, Text-only 15.03%입니다.
Audio+draft는 초안 복사 7.86%와 Whisper 5.34%보다 높아, 결합만으로 전체 교정 품질이 개선되지는 않았습니다.

[v2 웹사이트](https://jhparktime.github.io/TURST-YOUR-EARS/v2.html) ·
[참가자 데이터 프리릴리스](https://github.com/jhparktime/TURST-YOUR-EARS/releases/tag/dataset-ko-asr-v2) ·
[평가 규격과 한계](docs/real-asr-v2.md) · [현재 측정 결과](docs/real-asr-v2-results.md) ·
[제출 준비 상태](docs/submission-readiness.md)

**공개 Eval 보조 트랙:** 같은 409개 녹음에 원본·합성 잡음 5 dB·패킷 손실 20%를 적용한
[음질 손상 실험](docs/public-eval-stress-probe.md)을 추가합니다. 변형은 1,227개이며 서로 다른 녹음은 1시간입니다.
초안은 손상 전 음성에서 생성됐다는 정보 비대칭을 명시합니다. 손상 음성의 모델 비교는 아직이며,
본 실험 측정 후 손상 음성의 추론을 순차 실행 중입니다. 비공개 Test와 공식 순위는 변경하지 않습니다.

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

CI는 임시 PostgreSQL로 재시작 후 결과 보존도 확인합니다. 로컬에서 `TEST_POSTGRES_URL`이 없으면 해당 검사만 건너뜁니다. 자동 검사나 Copy 재현은 독립 청취 검수·모델 성능·난도의 증거를 대신하지 않습니다.

## 과거 실험 기록

합성 명사 치환을 사용한 `tye-ko-merged-v1 / ko-correction-v1`과 현재 실제 ASR v2는 별도 버전입니다. v1의 조건별 CER 평균과 v2의 발화별 Macro CER 정의도 다르므로 점수를 같은 순위에 섞지 않습니다. 기존 원본·실험·평가 코드는 재현용으로 유지합니다.

- [합성 오류 v1 웹사이트](https://jhparktime.github.io/TURST-YOUR-EARS/) · [데이터 통합·분할](docs/merged-dataset.md) · [베이스라인 결과](docs/baseline-results.md)
- [v1 난이도 점검](docs/difficulty-audit.md) · [공개 Eval 선택적 교정 진단](docs/measurements/selective-public-eval/README.md) · [v1 평가기](server/scoring.py)
- [이전 5시간 데이터](docs/five-hour-dataset.md) · [Zeroth pilot160 변환](docs/pilot160-import.md) · [FLEURS 파일럿](datasets/tye-ko-v2/README.md)
