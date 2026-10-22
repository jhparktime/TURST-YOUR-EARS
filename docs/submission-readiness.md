# 수업 제출 점검표

대상: `Team_박재현_202220741.html` · 프로젝트 `tye-ko-asr-v2 / ko-correction-v2`

TA가 요구한 HTML·Challenge 설명·Leaderboard·개인 GitHub·Baseline 코드·평가 데이터·Evaluation 코드에 맞춰 구성합니다. 사이트는 참가자가 과제를 이해하고 예시를 체험한 뒤 모델과 CSV를 만드는 순서로 안내합니다.

| 과제 항목 | 제공 내용 |
|---|---|
| 메인화면 | `web/index.html`, 학회 워크샵 형식·왼쪽 메뉴 카드·한/영 전환 |
| Challenge 설명 | 한국어 음성 + 실제 ASR 초안 → 전체 전사 교정, 원본 음성 예시 2개 |
| Leaderboard | 다섯 베이스라인의 Eval/Test 실측 10건, CER 순위와 내 결과 비교 |
| 개인 GitHub | 사이트·제출 HTML에서 프로젝트 저장소 연결 |
| Baseline | Copy, Whisper와 Qwen 세 입력 조건의 실행·재현 코드 |
| Dataset | Train 472개·약 1시간 13분, Eval 409개·1시간의 음성·초안·정답 공개; Test 1,750개·4시간 별도 보관 |
| Evaluation | Python·브라우저 채점, Micro CER 및 한국어 정규화·교정·보존 지표 |
| 추가 참가 지원 | CPU 학습·추론 및 평가 노트북 2개, 구체적인 참가 규칙 |
| 웹 내 평가 | 전체 Eval CSV를 브라우저에서 채점·JSON 저장, 설치 없이 Copy 체험 |

## 제공 파일과 재현

```sh
python -m scripts.build_course_submission_v2 --output /path/to/submission/Team_박재현_202220741.html
```

이 HTML은 CSS, 한/영 안내, 공개 Eval 채점기·정답, 실측 비교표와 음성 2개를 내장합니다. Test 정답이나 개별 예측은 내장하지 않습니다. 데이터·노트북·전체 코드 링크는 프로젝트 저장소로 연결합니다.

- 참가 규칙: [competition-rules.md](competition-rules.md)
- 학습·평가 노트북: [notebooks](../notebooks/)
- 노트북 실행 기록: [starter-notebooks-v1.json](measurements/starter-notebooks-v1.json)
- 원본 자료와 평가 상세 기록: [real-asr-v2.md](real-asr-v2.md)
- 기존 모델 실측: [real-asr-v2-results.md](real-asr-v2-results.md)

## 평가 운영 범위

공개 Eval은 즉시 사용할 수 있는 브라우저 채점입니다. Leaderboard의 팀 제출을 가장한 행은 없으며, 운영자 측정 베이스라인과 사용자의 브라우저 비교 행을 표시합니다.

비공개 Test는 운영자의 최종 비교 평가용입니다. 온라인 접수 API와 DB 코드는 저장소에 있으며, 현재 사이트에는 원격 Test 서비스를 연결하지 않습니다. 비공개 접수를 열 때에는 일정·팀 키·접수 규칙을 별도로 공지합니다. 이 운영 확장은 수업 필수 산출물과 구분합니다.

기준 전사는 Zeroth Korean 배포 전사입니다. 전사에 대한 이의와 버전 변경은 참가 규칙에 따라 기록합니다. 데이터 구축·모델 측정·소프트웨어 검증의 기존 상세 기록은 보존합니다.

## 수업 저장소 제출

수업 포크의 `submission/park-jaehyun-202220741` 브랜치에는 `submission/Team_박재현_202220741.html` 한 파일만 추가합니다. HTML 준비·브랜치 push와 원본 수업 저장소로의 PR 제출은 별도 단계입니다. PR 생성 여부는 제출 폴더의 최신 확인 기록을 따릅니다.

과거 합성 오류 v1은 `web/archive-v1.html`에 보존하며 현재 v2 순위에 섞지 않습니다.
