# Trust Your Ears · Korean FLEURS pilot v1

한국어 **실제 음성 + 합성 오류 전사 초안** 데이터입니다. 음성을 합성한 TTS 자료가 아닙니다. 원본 WAV와 원본 전사를 유지하고 초안의 숫자값·명사만 치환했습니다.

**현재 단계: 독립 청취 검수 전 파일럿.** 실제 음성 파일을 포함하지만 팀원이 원본 전사 정확성과 오답의 청각적 구별 가능성·문맥상 자연스러움을 확인하기 전에는 검수 완료 평가셋이나 공식 챌린지 결과로 부르지 않습니다.

| 구성 | 개발셋 | 평가셋 |
|---|---:|---:|
| 실제 발화 | 30 | 75 |
| Clean / Single / Multiple | 10 / 10 / 10 | 25 / 25 / 25 |
| 총 음성 길이 | 7분 1.86초 | 16분 49.86초 |
| 문자 수 범위, CER 정규화 후 | 35–79 | 35–89 |
| 음성 | 16 kHz, mono, 원본 WAV | 16 kHz, mono, 원본 WAV |
| 초안 그대로 제출한 Macro CER | 2.546569% | 2.541711% |

마지막 행은 **입력 초안의 오류량을 나타내는 Copy draft 기준점**입니다. 음성 인식 모델을 실행한 성능이나 음성 활용 효과가 아닙니다. 전체 원본 WAV는 약 91.6 MB입니다.

## 파일

- `dev/inputs.json`, `dev/audio/`: 공개 개발 입력과 실제 음성.
- `dev/references.json`: 공개 개발 정답, 조건, 오류 구간 주석.
- `eval/inputs.json`, `eval/audio/`: 공개 평가 입력과 실제 음성. 입력 필드는 정확히 `id,audio,draft`입니다.
- 각 split의 `audio-checksums.json`: 음성 SHA-256.
- 각 split의 `copy-draft.csv`: 초안을 그대로 제출하는 실제 데이터용 CSV 예시.
- 각 split의 `copy-draft.scores.json`: 재현 가능한 초안 복사 진단값.
- `metadata.json`: 원천 버전, seed, 데이터 통계와 검수 상태.
- `substitutions.json`: 고정 명사 치환 후보. 같은 글자 수·받침 유무를 가진 쌍만 적용합니다.

평가 정답은 공개 폴더에 없습니다. 운영자 로컬의 `private-data/tye-fleurs-ko-v1/`에 `eval-references.json`, `provenance.json`, `dev-review.json`, `eval-review.json`, `review-template.csv`를 생성했습니다. 이 디렉터리는 Git에서 제외됩니다. **평가 정답·평가 ID와 원천 전사의 대응표는 공개 저장소나 GitHub Pages에 올리지 마세요.** 과제 채점자가 재현할 수 있도록 별도 전달하거나 서버 평가로 제공할 수 있습니다. 생성 코드와 원천이 공개되어 있으므로 이는 보안상 완전히 비밀인 테스트셋이 아닙니다.

## 원천과 이용 조건

- 원천: [Google FLEURS](https://huggingface.co/datasets/google/fleurs), 한국어 `ko_kr`.
- 고정 버전: [`70bb2e84b976b7e960aa89f1c648e09c59f894dd`](https://huggingface.co/datasets/google/fleurs/tree/70bb2e84b976b7e960aa89f1c648e09c59f894dd).
- 원천 개발 `dev.tsv`에서 개발셋, 원천 테스트 `test.tsv`에서 평가셋을 선별했습니다.
- 원천 라이선스: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). 이 파생 데이터에도 CC BY 4.0을 적용합니다. 원천 저자·데이터셋 출처를 표시하고 오류 초안을 추가한 변경 사실을 표시하세요. 저자의 후원·제휴를 뜻하지 않습니다.
- 인용: Conneau et al. (2022), [FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech](https://arxiv.org/abs/2205.12446).

원본 음성 파일은 **바이트 단위 그대로 복사**했습니다. 리샘플링·잡음 합성·음성 재생성·양자화는 하지 않았습니다. 정답은 원천 TSV의 `transcription` 열(정규화된 전사)에 NFC만 적용했습니다. 원천의 구두점·숫자 표기 규칙을 유지하며 `raw_transcription`과 원본 문장 ID는 운영자 기록에 남깁니다.

## 초안 생성과 분할

1. 원천 문장 ID와 정규화 전사 기준으로 같은 문장의 여러 녹음 중 하나만 선택합니다.
2. 한글·숫자·제한된 구두점만 있는 전사, 정규화 후 35–180자, 원천 길이 4–20초를 선택합니다. 영문 혼용과 복잡한 괄호 표기는 첫 버전에서 제외했습니다.
3. 모든 조건의 후보는 **유효한 치환 위치가 두 곳 이상 있는 같은 모집단**에서 뽑습니다. 이 선별 편향을 결과 해석에 포함해야 합니다.
4. 명사는 단어 시작의 명사 어간과 허용한 조사·복수형에서만 치환합니다. 숫자는 값만 바꾸며 소수·음수 및 자릿수가 달라지는 변형은 제외합니다. 이 규칙은 실제 ASR 오류 확률을 추정한 혼동 행렬이 아닙니다.
5. Clean은 그대로, Single은 한 곳, Multiple은 두 곳을 바꿉니다. 이 버전의 Multiple은 **정확히 2곳**입니다. 3–4곳 오류는 아직 생성하지 않았습니다.
6. 조건을 국소 음성 길이 3개 묶음마다 하나씩 배정합니다. 성별을 완전히 균형화하지는 않았으며 통계를 제공합니다.
7. 개발·평가 사이에 원천 문장 ID, 전사, 음성 SHA-256이 겹치지 않게 합니다. 문자 SequenceMatcher 유사도 0.85 이상인 교차 split 전사도 제외합니다. 이는 모든 의미적 중복을 배제하는 판정은 아닙니다.
8. 초안을 오류 주석으로 완전히 재구성할 수 있고 정답→초안 정렬이 주석과 일치하는 샘플만 사용합니다. 초안 복사의 복원률·정상 구간 훼손률은 모두 0임을 확인합니다.

**화자 분리는 입증하지 못했습니다.** 사용한 원천 TSV에는 화자 ID·세션 ID가 없습니다. 공식 dev/test 분할과 서로 다른 문장은 유지했지만 동일 화자가 두 세트에 존재할 수 있습니다. 성별 열을 화자 ID로 대신하지 않습니다.

## 재현과 평가

저장소 루트, Python 3.12 이상에서 실행합니다. 원본 두 음성 압축 파일은 총 약 340.6 MB이며 캐시를 재사용합니다. 고정 원천 TSV·음성 압축 파일의 SHA-256이 다르면 중단합니다.

```sh
pip install -r requirements-dataset.txt
python -m scripts.build_dataset --cache /path/to/fleurs-cache --output /path/to/new-public-set --private-output /path/to/new-private-set --dev-count 30 --eval-count 75 --seed 20261015
python -m scripts.validate_dataset --dataset datasets/tye-fleurs-ko-v1 --private private-data/tye-fleurs-ko-v1
python -m scripts.baseline --mode copy --inputs datasets/tye-fleurs-ko-v1/dev/inputs.json --output /tmp/tye-dev-copy.csv
python -m scripts.evaluate --references datasets/tye-fleurs-ko-v1/dev/references.json --predictions /tmp/tye-dev-copy.csv
python -m scripts.baseline --mode copy --inputs datasets/tye-fleurs-ko-v1/eval/inputs.json --output /tmp/tye-eval-copy.csv
python -m scripts.evaluate --references private-data/tye-fleurs-ko-v1/eval-references.json --predictions /tmp/tye-eval-copy.csv
```

`build_dataset`의 기본 치환 파일은 이 폴더의 `substitutions.json`입니다. 동일 seed·원천·치환 파일이면 입력·오류 주석·선택 음성 파일을 재현합니다. 기존 완성본은 덮어쓰지 않습니다. `validate_dataset`은 공개 파일만으로 음성/입력 및 개발 정답을 검사하고, `--private`을 전달하면 평가 정답·원천 대응·교차 split 전사까지 확인합니다. 자동 검사는 청취 검수 완료를 인증하지 않습니다.

## 팀원 검수와 공개 리더보드 전환

`private-data/tye-fleurs-ko-v1/review-template.csv`에 개발·평가 전체 105개가 있습니다. 또는 `dev-review.json` / `eval-review.json`의 각 항목에 다음을 기록합니다.

- 음성을 듣고 원본 전사가 실제 발화와 일치하는지.
- 주입한 원래 단어와 오답이 음성으로 구별 가능한지.
- 조사 불일치나 명백한 비문만으로 답이 드러나는지.
- 검수자와 수정/제외 사유. 단순히 모든 행을 자동 승인하지 않습니다.

이후 실제 모델을 실행하고 Audio only / Text only / Audio + draft를 비교합니다. FLEURS 원문은 공개되고 사전학습에 포함되었을 수 있습니다. 공개 원문 조회 금지 규칙만으로 오염을 해결할 수 없으며, 점수를 일반적인 한국어 ASR 성능이나 새로운 음성 이해 능력의 증명으로 해석하지 않습니다. 인위적 치환과 실제 ASR 오류의 결과도 구분해야 합니다. 아직 외부 웹 채점 서버는 연결되지 않았습니다.
