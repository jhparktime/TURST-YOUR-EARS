# Trust Your Ears 참가 규칙

규칙 버전 1.1 · 2026-10-23 · 대상 데이터 `tye-ko-asr-v2` · 채점 `ko-correction-v2`

한국어 음성과 실제 ASR 초안을 받아 **실제 발화에 맞게 교정한 전체 전사문**을 출력합니다.
틀린 부분을 고치고 맞는 부분을 보존하는 것이 목표입니다. 음성 재전사, 초안 복사, text-only와 audio+draft 모두 비교할 수 있습니다. 사용 입력을 결과에 명시하세요.

## 1. 참가와 현재 이용 범위

- 팀은 1–2명이며 한 사람은 한 팀에만 참여합니다. 수업 제출 일정은 TA 공지를 따릅니다.
- 공개 Eval 409개는 로그인 없이 웹에서 횟수 제한 없이 채점할 수 있습니다. 채점만 하는 파일은 브라우저에서 처리합니다. 최근 20개 결과는 브라우저에 저장합니다. 공동 등록은 별도로 동의하고 제출합니다.
- 사이트 Leaderboard는 운영자 베이스라인, 공동 등록 팀의 최고 기록, 현재 브라우저의 개인 결과를 함께 비교합니다. 공동 등록은 GitHub 로그인이 필요하며 제출 CSV를 자동 재채점합니다. [등록 방법·공개 범위·기록 보관](public-leaderboard.md)을 확인하세요. 팀명·계정·방법·코드 링크·예측 CSV가 공개됩니다.
- 공동 Eval에는 팀 대표 계정 하나를 사용합니다. 최초 유효 등록의 팀명을 계정에 연결하며 중복 팀명을 거부합니다. 계정당 하루 신규 유효 제출 5회(00:00 KST 초기화), 동일 CSV는 횟수에서 제외합니다. 유효 제출뿐 아니라 중복·반려 결과도 처리 이력에 남습니다.
- 비공개 Test 1,750개는 운영자 최종 평가용입니다. 표의 Test 결과는 고정 베이스라인 측정치입니다. 온라인 Test 접수를 열 경우 일정과 팀 키 발급 방법을 별도로 공지합니다.

## 2. 데이터·모델 사용

- Train 472개의 음성·초안·정답으로 학습할 수 있습니다. Eval 정답은 개발·모델 선택·채점에 사용할 수 있습니다.
- **Eval/Test 정답을 추론 입력에 제공하거나 ID별 정답 사전을 만들면 안 됩니다.** 평가 문장을 사람이 직접 고친 예측도 허용하지 않습니다. 모든 평가 발화에 같은 자동 추론 절차를 적용하세요.
- 공개 사전학습 모델과 외부 데이터는 사용할 수 있습니다. 모델 이름·정확한 버전, 라이선스, 외부 데이터의 출처·버전·이용 조건을 기록하세요.
- Eval/Test 원천 발화와 파생 자료를 외부에서 찾아 추가 학습하거나 답안으로 사용하지 마세요. 추가 학습 데이터는 평가 자료와 중복 여부를 확인하고 방법을 기록하세요.
- 공개 모델의 사전학습에 원천 코퍼스가 포함됐는지 모르면 “불명확”으로 기재합니다. 이를 검증된 미포함으로 표시하면 안 됩니다.
- 데이터와 모델의 원래 이용 조건을 따릅니다. Zeroth Korean은 CC BY 4.0이며 원천 출처와 변경 사항을 표기합니다.

## 3. 예측 파일

UTF-8 CSV, 최대 2 MiB. 첫 행은 `id,prediction`이며 Eval의 409개 ID가 각각 정확히 한 번씩 있어야 합니다.
다른 ID, 중복 ID, 누락 ID와 잘못된 형식은 채점기가 거부합니다. 빈 prediction은 결측 행으로 숨기지 않고 삭제 오류로 채점합니다.
문장 안의 쉼표·따옴표는 표준 CSV 인용 규칙을 사용하세요. Python `csv.writer` 사용을 권장합니다.

```csv
id,prediction
e118228a33d1d90f6247,적은 농도로도 인체에 치명적인 영향을 주는 일산화탄소는 어떨까요
```

위는 **형식 예시 한 행**입니다. 실제 제출에는 전체 ID가 필요합니다. 설명, 오류 위치 목록, 요약 대신 전체 전사문을 넣으세요.
Test 접수에서도 해당 Test 입력의 전체 ID와 같은 형식을 사용합니다.

## 4. 채점·순위·동점

- 주 지표 **Micro CER** = 전체 문자 치환·삭제·삽입 수 / 전체 정답 문자 수 × 100. 낮을수록 높은 순위입니다.
- 순위는 **반올림 전 값**으로 결정합니다. 정확히 같은 값은 공동 순위이며 다음 순위는 인원만큼 건너뜁니다(1, 2, 2, 4).
- Macro CER, 어절 WER, 오류 슬롯 복원률, 교정 정밀도·F1, 정상 문자 훼손률, 불필요 삽입률과 Clean 변경률은 보조 지표입니다. 임의 가중합으로 주 지표를 바꾸지 않습니다.
- 한국어 정규화는 NFC와 소문자 변환 후 공백과 지정 문장부호를 제외합니다. 숫자 사이 소수점은 유지합니다. `3시`와 `세 시`는 같게 바꾸지 않습니다. 자세한 정의는 [평가 코드](../server/scoring_v2.py)가 기준입니다.
- Eval과 Test, 과거 v1과 현재 v2는 서로 다른 순위입니다. 개인 기록은 최근 20건을 브라우저에 보관합니다. 공동 등록은 전체 처리 이력을 별도 저장하고 팀별 최고 점수로 순위를 정합니다. JSON도 내려받아 기록할 수 있습니다.

## 5. Test 온라인 접수 시 적용 정책

현재 웹에서 열려 있는 서비스는 공개 Eval 채점입니다. 아래는 구현된 Test 서버를 연결해 접수할 때의 정책입니다.

- 운영자가 발급한 팀 키로 인증합니다. 키를 공개 코드나 노트북에 넣지 마세요.
- 팀별 **하루 신규 유효 제출 5회**, **00:00 UTC / 09:00 KST 초기화**입니다. 채점 실패 파일은 유효 횟수에 포함하지 않습니다.
- 동일 파일의 재제출은 기존 결과를 반환하며 신규 횟수를 소비하지 않습니다.
- 팀별 가장 낮은 Micro CER 결과를 순위에 사용합니다. 제출 횟수는 접수 서비스에서 확인합니다.
- Test 정답은 공개하지 않습니다. 검증된 데이터 버전과 채점 규격이 일치하는 서비스만 접수합니다.

## 6. 재현성과 결과 공유

비교 결과를 공유할 때 팀명, 사용 입력(audio / draft / both), 코드 revision, 모델 checkpoint/revision, 프롬프트, 학습 데이터, 학습·추론 파라미터, seed와 실행 환경을 기록합니다. 학습 모델은 가중치 또는 재생성 절차를 제공하세요.
Eval 문장별 수작업 예외, 정답 조회, 평가 데이터 추가 학습을 숨긴 결과는 유효한 비교로 인정하지 않습니다. 문제가 발견되면 운영자는 근거를 확인하고 해당 결과를 제외하거나 재실행을 요청할 수 있습니다.

## 7. 오류 신고와 변경

[GitHub Issues](https://github.com/jhparktime/TURST-YOUR-EARS/issues)에 데이터 버전, 발화 ID, 재현 방법과 근거를 남겨주세요. **비공개 정답·팀 키는 게시하지 마세요.**
기준 전사는 원천 코퍼스 배포 전사를 사용합니다. 정답 변경 시 버전과 변경 내역을 공개하고 같은 버전·같은 평가기로 다시 비교합니다. 과거 결과를 설명 없이 덮어쓰지 않습니다.

## 규칙 구성 참고

[Kaggle Competitions 문서](https://www.kaggle.com/docs/competitions)와 [DrivenData 공개 대회 규칙](https://www.drivendata.org/competitions/53/)의 데이터 사용, 팀, 제출, 재현성 항목 구성을 참고해 이 수업 프로젝트에 맞게 작성했습니다. 두 플랫폼과 제휴하거나 해당 플랫폼에서 접수하는 대회는 아닙니다.

---

## English summary

Teams have 1–2 members, with one team per person. Use Train labels for fitting and Eval labels for development/scoring. Never supply Eval/Test answers to inference, create answer lookups, or manually edit evaluated predictions. Public pretrained models and external data are allowed with provenance, version and license disclosure; exclude Eval/Test source recordings and derivatives from added training, and declare unknown pretraining exposure.

Submit UTF-8 CSV with `id,prediction`, every Eval ID exactly once, maximum 2 MiB. Rank by unrounded Micro CER; exact ties share positions (1, 2, 2, 4). Secondary metrics remain diagnostic. Eval and Test are separate. Publish code, model settings, data and runtime details for reproducibility.

Public browser scoring is unlimited and retains the latest 20 results locally. Separate shared registration requires GitHub sign-in and consent to publish the team, account, method, code link and predictions. GitHub Actions re-scores the CSV and stores team bests plus submission history. Shared Eval allows five new valid submissions per representative account per day, reset 00:00 KST; identical CSVs and invalid files do not consume this quota. Shared Eval is separate from private Test. Test currently uses organizer evaluation. If an online Test round opens, the server supports five new valid submissions per team per day, reset at 00:00 UTC / 09:00 KST; identical files return cached results. Each team’s best CER is ranked. Schedules and access will be announced separately. Report reference issues via GitHub Issues without exposing private answers or keys. Changes receive a version and changelog.
