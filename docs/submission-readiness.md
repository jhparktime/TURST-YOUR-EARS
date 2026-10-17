# 제출 준비 점검표 — 실제 ASR v2

수업 기준: [Speech Recognition Challenge 2026](https://github.com/LSH-Ajou/Speech-Recognition-Challenge-2026).
수업 저장소에는 `submission/Team_<대표이름>_<학번>.html` 한 개를 추가한다.
샘플을 복제하지 않고 자체 워크샵 사이트와 공개 평가기를 한 HTML에 묶는다.

현재 제출 후보는 **tye-ko-asr-v2 / ko-correction-v2**다. 데이터 구축과
본 실험 다섯 방법의 Eval/Test 측정 10건, 보조 트랙 측정 15건을 완료했다.
독립 청취 검수와 비공개 서버 연결은 아직 완료되지 않았다.

| 필수 항목 | 현재 산출물 | 확인 상태 |
|---|---|---|
| 메인·Challenge 설명 | `web/v2.html`, `docs/real-asr-v2.md` | 실제 음성+ASR 초안→전체 전사 교정, 한/영 전환 |
| Leaderboard | `web/data-v2/baselines.json`, `docs/real-asr-v2-results.md` | Copy·Whisper·Qwen Audio-only·Text-only·Audio+draft의 Eval/Test 10건 완료 |
| 개인 GitHub | https://github.com/jhparktime/TURST-YOUR-EARS | 사이트에 연결 |
| Baseline 코드 | `scripts/baseline.py`, `scripts/run_omni_baselines.py` | 고정 모델 버전·입력 조건·프롬프트 및 중단 재개 |
| Evaluation 데이터 | `datasets/tye-ko-asr-v2/`, 참가자 ZIP | 공개 Eval 409개·1시간의 음성·초안·정답 포함 |
| 평가 방법·코드 | `server/scoring_v2.py`, `web/scorer-v2.js` | 주 지표 Micro CER, 슬롯 복원·훼손·삽입 지표 |
| 웹 내 평가 | `v2.html#submit` | 실제 공개 Eval 409행 채점·전체 JSON 내려받기·Python 결과 일치 확인 |
| 단일 HTML | `scripts/build_course_submission_v2.py` | 측정 10건 내장; 실제 409행 채점·전체 JSON 일치·한/영 및 분할 전환 확인 |

## 데이터와 공개 범위

Train 472개·약 1시간 13분, 공개 Eval 409개·1시간, 비공개 Test 1,750개·4시간이다.
기존 녹음을 유지하고 실제 Whisper·Qwen 음성 단독 출력으로 초안을 교체했다.
생성기 배정은 v2 Test 오류 분석 전에 고정했다. 점수가 높은 오류만 골라 남기지 않았다.
원래 녹음 풀의 선택 제약과 기존 v1 Test 집계를 본 이력은
[데이터 정의](real-asr-v2.md)에 기록한다. 독립 청취 검수는 현재 0건이다.

[참가자 ZIP 프리릴리스](https://github.com/jhparktime/TURST-YOUR-EARS/releases/tag/dataset-ko-asr-v2)는
Train/Eval만 포함한다. Test 정답·개별 예측·원천 대응표·검수표는 비공개 보관한다.
Test 입력 ZIP에도 정답·조건 라벨·검수표를 넣지 않는다. 단일 HTML에는 공개 Eval 정답만 내장한다.
공개 Eval 점수는 개발용이며 공식 참가 팀의 비공개 Test 순위와 구분한다.

## 완료된 검증과 남은 작업

- 2,631개 음성 전체의 복호화·원천 바이트·정답 보존·생성기 배정·실제 출력 대응을 검사했다.
  화자·세션·동일 문장·동일 음성의 split 간 겹침을 확인했다. 음성을 사람이 검수한 결과는 아니다.
- GitHub Pages와 단일 HTML에서 실제 409행 CSV를 채점하고 한/영 전환 및 JSON 내려받기를 확인했다.
  모든 공개 지표가 Python과 일치했다. 서버 없는 공개 채점은 사용 가능하다.
- 단일 HTML 안에 Pipeline·Baseline & Method·References를 보완하고 모델별 입력 조건을 표로 설명했다.
  새 CSV를 선택하거나 채점에 실패하면 이전 점수·내려받기를 지우도록 수정했다. 정상 채점→잘못된 분할 거부→재채점과
  전체 JSON 일치를 [브라우저 검증 기록](measurements/real-asr-v2-course-ui-check.json)에 남겼다.
- 새 공개 저장소 사본과 릴리스 ZIP만으로 Copy·평가를 재현했다. 외부 패키지를 비활성화해도 전체 JSON이 배포 기준값과 같았다.
  공개 881개 음성의 체크섬과 ZIP 전체 CRC도 확인했다. [참가자 재현 기록](measurements/real-asr-v2-participant-reproduction.json)을 남긴다.
- 로컬 비공개 API에서 실제 Test 1,750행의 Copy·Whisper 채점과 재시작 후 결과 보존을 확인했다.
  [검증 기록](measurements/real-asr-v2-api-software-check.json)은 원격 배포 완료를 뜻하지 않는다.
- Text-only와 Audio+draft 모두 Eval/Test 2,159개 추론과 입력·실제 출력 대응 검증을 완료했다.
  Audio+draft의 Test Micro CER는 9.5645%, 정상 문자 훼손률은 1.4668%다. 전체 지표와 생성기별 결과를 공개한다.
  한도 도달 출력도 그대로 평가했으며, 데이터 자체의 청취 검수 완료를 뜻하지 않는다.
  [전체 모델 검증 기록](measurements/real-asr-v2-all-models.json)에 모델 완료 해시와 갱신된 제출 HTML의 확인값을 남긴다.
- 독립 청취 검수에서 원천 전사 오류·숫자 표기 차이·불명료 발화를 확인하고 처리 내역을 남긴다.
- [무료 배포 안내](free-evaluation-hosting.md)에 따라 비공개 API·DB를 연결한다.
  자체 Pages와 수업 Pages 두 출처의 접속·채점·기록 보존을 원격 검증하기 전에는 접수를 닫아 둔다.
- 대표 정보로 `Team_박재현_202220741.html` 후보를 만들었다. 수업 원본 main 기준 로컬 브랜치에는
  이 HTML 한 파일만 추가했으며, 409행 채점·전체 JSON 일치·언어와 분할 전환을 실제 파일에서 확인했다.
  본 실험 10건을 반영하고 실제 파일에서 전체 Copy 지표가 Python과 같음을 재확인했다. 수업 PR은 아직 생성하지 않았다.

## 추가한 공개 Eval 보조 트랙

공개 Eval 409개·1시간에서 원본·합성 잡음 5 dB·20 ms 패킷 20% 손실의 1,227개 변형을 만들었다.
같은 원본의 초안·정답을 유지하고 모든 음성의 손상·길이·원본 보존을 자동 검증했다.
[보조 트랙](https://jhparktime.github.io/TURST-YOUR-EARS/stress.html)에서 전체 CSV를 채점하고
음질 조건별·원래 초안의 정오답별 결과를 내려받는다. Python과 브라우저의 전체 지표가 일치한다.
배포된 페이지에서도 1,227행을 채점하고 전체 JSON이 Python과 일치함을 확인했다.
다른 분할 CSV의 ID 불일치 차단과 정상 CSV로의 복구도 확인했다. 이는 소프트웨어 동작 검증이다.
[원격 검증 기록](measurements/public-eval-stress/live-software-check.json)에 CI·릴리스의 확인값을 남겼다.
Copy 외에도 실제 Whisper 예측 1,227행을 배포된 웹에서 채점했다. 세 조건과 초안 정오답별
9개 집단의 전체 JSON이 Python과 일치했다. [비복사 예측 검증 기록](measurements/public-eval-stress/live-whisper-software-check.json)은
웹 평가기의 동작 검증이며 보조 트랙 전체 모델 비교의 완료를 뜻하지 않는다.
새 공개 저장소 사본과 릴리스 ZIP만으로 1,227행 Copy·채점도 재현했다. 외부 패키지 없이 전체 JSON이
웹에서 내려받은 결과와 일치했다. [참가자 재현 기록](measurements/public-eval-stress/participant-reproduction.json)을 남긴다.
다섯 방법 × 세 조건의 측정 15건을 완료했다. 새 손상 음성 818개에 대한 Whisper·Qwen Audio-only·Audio+draft
추론의 입력·실제 출력 대응을 검증했다. [완료 기록](measurements/public-eval-stress/all-models.json)에 확인값을 남긴다.
새 공개 개발 실험으로서 기존 비공개 Test·공식 순위와 구분한다.
초안은 손상 전 원본 음성에서 생성됐다는 정보 비대칭과 청취 미검수를 명시한다.
[구성·해석 규격과 결과](public-eval-stress-probe.md)에 조건별 비교와 해석의 한계를 기록한다.

## 보존한 v1 결과

`web/index.html`, `web/data/`, `docs/baseline-results.md`와 기존 v1 release는 과거 합성 명사 치환 실험이다.
v1은 10건 측정이 완료됐지만 새 실제 ASR v2 실험의 완료 상태를 대신하지 않는다.
v1의 조건 평균 Macro CER와 v2의 발화 평균 Macro CER는 정의가 다르므로 같은 순위에 섞지 않는다.
