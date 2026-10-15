# 제출 준비 점검표

수업 기준: [Speech Recognition Challenge 2026](https://github.com/LSH-Ajou/Speech-Recognition-Challenge-2026).
수업 저장소에는 `submission/Team_<대표이름>_<학번>.html` 한 개만 추가한다.
샘플 페이지를 복제하지 않고 자체 워크샵 사이트를 하나의 HTML로 묶는다.

| 필수 항목 | 현재 산출물 | 확인 |
|---|---|---|
| 메인화면 index.html | `web/index.html` | 자체 워크샵 디자인, 여섯 페이지와 한/영 전환 |
| Challenge 설명·프로젝트 | Challenge·연구 발표 페이지, README | 음성+초안→전체 전사 교정으로 통일 |
| Leaderboard·벤치마크 비교 | `web/data/baselines.json`, `docs/baseline-results.md` | Copy·Whisper·Qwen Text-only의 eval/test 완료; 두 음성 입력 비교는 미완료 |
| 개인 GitHub | https://github.com/jhparktime/TURST-YOUR-EARS | 페이지 내 링크 |
| Baseline 코드 | `scripts/baseline.py`, `scripts/run_omni_baselines.py` | 입력 분리·프롬프트·고정 버전·중단 재개 |
| Evaluation 데이터 | `datasets/tye-ko-merged-v1/`, 참가자 ZIP | 공개 eval 409개·1시간 포함; 음성 ZIP 새 release 공개 완료 |
| 평가 방법·코드 | `server/scoring.py`, `web/scorer.js` | 동일 ko-correction-v1, 브라우저/Python 공개 eval 점수 일치 |
| 웹 안에서 평가 | 결과 제출의 공개 eval 채점 | 브라우저 실제 409행 Copy 채점 및 영어 전환 검증 |
| 단일 HTML | `scripts/build_course_submission.py` | CSS·JS·공개 eval 정답·벤치마크·예시 CSV 내장; 최종 학번 파일명과 최종본 검증은 대기 |

## 버전과 공개 범위

현재 데이터는 `tye-ko-merged-v1`, 평가 규격은 `ko-correction-v1`이다.
공개 train 472개·약 1시간 13분, 공개 eval 409개·1시간, 비공개 test 1,750개·4시간이다.
전체 4,081개는 운영자 원본 풀에 보존하며, 예비 1,450개를 학습에 쓰지 않는다.
새 train 일부가 이전 test에 속했으므로 새 자료를 공개하면 이전 test는 종료한다.

단일 제출 HTML은 공개 eval 정답만 내장한다. 비공개 test의 개별 정답·예측·음성·원천 대응표는
GitHub Pages와 수업 HTML에 넣지 않는다. Test 집계 성능과 조건별 분자·분모는 공개할 수 있다.
실제 비공개 test 제출은 별도 API를 연결해야 하며, 연결 전에는 해당 제출을 비활성화한다.
공개 eval 개발 점수는 공식 참가 팀 순위가 아니다.

## 최종 확정 전 남은 항목

1. 대표 학번을 확인하고 정식 파일명을 확정한다. 대표 이름은 박재현으로 준비하며, 학번은 추정해 쓰지 않는다.
2. Qwen Audio+draft·Audio-only의 eval/test 전체 추론과 지표를 완료한 뒤 표를 갱신한다. Text-only는 2,159개 전체 채점을 완료했다.
3. 모든 모델 결과를 반영한 HTML을 다시 생성해 단일 파일에서 채점·한/영 전환을 확인한다.
4. 비공개 Test 채점 서버는 아직 미연결이다. [무료 배포 안내](free-evaluation-hosting.md)에 따라 계정·Secret File·DB를 연결하고 원격 채점과 재시작 후 보존을 확인한다.
5. 준비한 개인 포크의 `submission/`에 정식 파일 하나만 추가하고, 원본 수업 저장소에 제출할 PR의 변경 범위를 확인한다. 현재 제출 브랜치·수업 PR은 만들지 않았다.

## 완료한 준비와 확인 범위

- 참가자 train/eval ZIP과 SHA256을 [새 release](https://github.com/jhparktime/TURST-YOUR-EARS/releases/tag/dataset-ko-merged-v1)로 공개했다. 운영자 ZIP과 Test 입력 묶음은 비공개 보관 중이다.
- Pages의 공개 eval에서 실제 409행 Copy CSV 채점과 한/영 전환을 확인했다. 이 검증은 비공개 Test 서버의 배포 완료를 뜻하지 않는다.
- Copy·Whisper·Qwen Text-only 각각의 eval/test 결과 6건을 공개했다. [Text-only의 전체 실행 증빙](measurements/qwen-text-only-completed.json)에는 생성 한도 도달 1건도 실제 출력 그대로 채점했다는 기록을 포함한다.
- [공개 개발셋 난이도 진단](measurements/selective-public-eval/README.md)의 전체 후보와 예측을 공개하고 연구 발표 페이지에 반영했다. 이 필터의 비공개 Test 성능은 측정하지 않았다.
- 개인 포크 [jhparktime/Speech-Recognition-Challenge-2026](https://github.com/jhparktime/Speech-Recognition-Challenge-2026)을 준비했다. 원본 샘플 대신 자체 사이트를 묶는 방식이며 대표 학번은 아직 확인되지 않았다.

독립 청취 미검수와 합성 명사 치환의 한계는 공개 자료에 명시한다. 현재 결과만으로
실제 ASR 오류에 대한 일반화나 음성 활용의 추가 이득을 입증했다고 주장하지 않는다.
수업 PR의 실제 제출은 최종 파일명과 내용을 확인한 뒤 진행한다.

원격 CI 실행 [38804148185](https://github.com/jhparktime/TURST-YOUR-EARS/actions/runs/38804148185)의 Python 검사 99개·언어 전환 검사 5개와 Pages 배포가 성공했다. 로컬 API에서는 새 test 전체의 Copy·Whisper 실제 예측 제출, 재시작 후 순위 보존, 비공개 경로 404를 확인했다. 원격 비공개 서버에서의 검증은 아직이다.
