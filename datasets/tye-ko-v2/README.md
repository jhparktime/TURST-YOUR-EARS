# Trust Your Ears · Korean Correction v2

**최종 배포본: 실제 한국어 음성 + 합성 오류 전사 초안.** 개발 60개·평가 60개이며 음성은 약 25분 37.62초입니다. 고정된 배포 파일의 목록과 SHA-256은 `release-lock.json`에 있습니다. v1 파일럿과 ID·정답·분할이 다르므로 결과를 혼합하지 마세요.

## 과제와 구성

음성과 전사 초안을 받아 실제 발화에 맞는 전체 전사문을 출력합니다. 원본 WAV와 정답 전사는 변경하지 않았으며, **초안의 명사 또는 숫자 값만 치환**했습니다. TTS 합성 음성이나 실제 ASR 출력 오류를 수집한 데이터가 아닙니다.

| 조건 | 개발 | 평가 | 주입 오류 |
|---|---:|---:|---:|
| Clean | 20 | 20 | 0곳 |
| Single | 20 | 20 | 1곳 |
| Multiple | 20 | 20 | 정확히 2곳 |

- `dev/inputs.json`, `dev/audio/`: 공개 개발 입력과 실제 16 kHz mono WAV.
- `dev/references.json`: 개발 정답·조건·NFC 문자 기준 오류 위치.
- `eval/inputs.json`, `eval/audio/`: 평가 입력. 각 행의 필드는 `id,audio,draft`만 포함합니다.
- 각 split의 `copy-draft.csv`, `copy-draft.scores.json`: 초안을 그대로 제출하는 채점 기준점. 모델 교정 성능이 아닙니다.
- `quality-report.json`: 음성 전사 교차 검사 기준과 원천별 포함·제외 수. 평가 전사와 샘플별 모델 출력은 포함하지 않습니다.
- `metadata.json`, `audio-checksums.json`, `release-lock.json`: 버전·분할·음성·파일 무결성 기록.

운영자용 `private-data/tye-ko-v2/`에는 평가 정답, 원천 대응표, 샘플별 음성 전사 검사 결과, 추가 청취 검수표가 있습니다. 공개 저장소나 GitHub Pages에 올리지 마세요. 평가 정답 manifest의 전체 SHA-256은 공개 metadata에 고정해 두었습니다.

## 출처와 이용 조건

원천은 [Google FLEURS](https://huggingface.co/datasets/google/fleurs), 한국어 `ko_kr`, 고정 revision [`70bb2e84b976b7e960aa89f1c648e09c59f894dd`](https://huggingface.co/datasets/google/fleurs/tree/70bb2e84b976b7e960aa89f1c648e09c59f894dd)입니다. 원천 및 파생 데이터는 **CC BY 4.0**이며 출처·저자·초안 치환 사실을 표시해야 합니다. 저자의 후원이나 제휴를 의미하지 않습니다. 세부 출처 표시는 `NOTICE`를 따릅니다.

Conneau et al. (2022), [FLEURS: Few-shot Learning Evaluation of Universal Representations of Speech](https://arxiv.org/abs/2205.12446).

## 선별과 분할

1. 원천 음성 압축 파일과 전사 TSV의 고정 해시를 검사합니다. WAV는 바이트 단위 그대로 복사합니다. 정답은 원천 `transcription` 열에 NFC만 적용합니다.
2. 한글 중심(문자 중 한글 비율 80% 이상, 숫자 제외), 4–20초, 정규화 25–180자, 유효한 치환 후보 두 곳 이상을 가진 같은 모집단에서 모든 조건을 선별합니다. 제한적인 영문 혼용·원천 구두점을 허용합니다. 이 기준 때문에 전체 한국어 발화를 대표하지 않습니다.
3. 개발 후보는 **원천 train**에서 seed 20261015로 180개를 선택하고, 평가 후보는 원천 dev/test의 조건 충족 발화를 사용합니다. **v1에 공개한 문장은 평가 후보에서 전부 제외**하고, v1 전사와 문자 유사도 0.85 이상인 후보·동일 음성도 제외합니다. FLEURS는 train 화자가 dev/test 화자와 다르다고 명시합니다. 이 보장은 원천에 의존하며, 우리가 화자 신원을 직접 확인한 것은 아닙니다. TSV에는 개별 화자·세션 ID가 없습니다.
4. 고정 Whisper 체크포인트로 **음성만** 전사합니다. 초안·정답·정답 힌트·이전 발화 문맥을 모델에 제공하지 않습니다. 원천 전사 대비 CER 10% 이하이고, 치환 후보 단어 두 곳 이상이 정렬된 음성 전사에서 원문 그대로 확인되는 후보만 사용합니다. 주입 위치는 이 확인된 후보에서 선택합니다. 모델 출력으로 정답을 덮어쓰지 않습니다. 전체 전사의 일치를 강제하지 않으므로 검증 모델의 0% CER을 보장하지 않습니다.
5. 동일 문장 ID·정규화 전사·음성은 중복하지 않습니다. 개발·평가 간 문자 SequenceMatcher 유사도 0.85 이상인 전사도 제외합니다. 모든 의미적 중복을 판정하는 방법은 아닙니다.
6. 음성 길이 순 세 개씩 묶어 Clean/Single/Multiple을 하나씩 배정합니다. 치환은 어간·조사 경계를 확인하고, 같은 글자 수·받침 유무를 유지합니다. 소수·음수·자릿수 변경은 주입 대상에서 제외합니다. 일부 치환은 의미가 비슷하거나 문맥으로 유추할 수 있습니다. 실제 ASR 혼동 확률이나 균일한 발음 유사성을 주장하지 않습니다.

## 검증 범위와 해석

**사람의 독립 청취 검수는 수행하지 않았습니다.** 원천 공식 전사를 정답으로 사용하고, 주입할 단어를 블라인드 음성 전사와 교차 확인한 자동 검증 배포본입니다. 교차 확인이 참조 전사 전체의 절대적 정확성이나 음성 이해 능력을 증명하지는 않습니다. 원천과 검증 모델의 공통 오류·사전학습 오염 가능성이 남습니다.

선별에 사용한 Whisper에 유리한 선택 편향이 있습니다. `audio-only-qa.scores.json`은 실제 실행 출력의 진단값이며, 공정한 모델 비교 결과나 독립적인 일반화 증거로 제시하지 마세요. 음성 전사에는 주입 위치 밖의 오류가 남을 수 있어 초안을 전체 음성 전사로 대체하면 정상 구간을 훼손할 수 있습니다. 교정 실험에서는 같은 모델·생성 설정의 Audio only / Text only / Audio + draft를 비교하여 텍스트 문맥만으로 풀리는 비율을 함께 보고하세요.

원천 전사·생성 코드가 공개되어 정답을 복원할 수 있습니다. 원문 조회 금지 규칙만으로 완전히 비밀인 테스트셋이 되지는 않습니다. 이 데이터는 **공개 코퍼스에서 구성한 수업용 고정 교정 벤치마크**이며 새로운 비공개 한국어 음성 이해 성능의 증명으로 해석하지 않습니다. 별도 사람 검수가 필요할 때 운영자 검수표를 사용하고 변경 사항은 새 버전으로 배포하세요.

## 평가와 실행

주지표는 Clean/Single/Multiple 조건 CER의 동일 비중 평균인 Macro CER ↓입니다. 오류 구간 복원률 ↑, 정상 구간 훼손률 ↓, Clean 변경률 ↓, 초안 대비 개선폭(%p)도 기록합니다. 공백과 지정 문장부호는 제외하고 숫자 읽기·동의어를 정답으로 자동 치환하지 않습니다. 규격은 `server/scoring.py`의 `ko-correction-v1`입니다.

```sh
python -m scripts.validate_dataset --dataset datasets/tye-ko-v2
python -m scripts.validate_dataset --dataset datasets/tye-ko-v2 --private private-data/tye-ko-v2 --source-cache /path/to/fleurs-cache
python -m scripts.baseline --mode copy --inputs datasets/tye-ko-v2/eval/inputs.json --output /tmp/tye-v2-copy.csv
python -m scripts.evaluate --references private-data/tye-ko-v2/eval-references.json --predictions /tmp/tye-v2-copy.csv
```

웹 평가 서버에는 `REFERENCE_PATH=/absolute/path/private-data/tye-ko-v2/eval-references.json`을 설정합니다. 외부 채점 서버의 배포 완료를 뜻하지는 않습니다.

## 재현

Apple Silicon에서 사용한 검증 모델·revision·패키지는 `scripts/transcribe_audio.py`와 `requirements-audio-qa.txt`에 고정했습니다. 다른 환경에서 모델 전사 결과가 달라질 수 있으므로 배포 파일의 `release-lock.json`을 최종 파일 판정 기준으로 사용하세요. 원천 전체 음성 다운로드는 약 1.76 GB입니다.

```sh
pip install -r requirements-audio-qa.txt
python -m scripts.build_final_dataset prepare --cache /path/to/fleurs-cache --work /path/to/new-candidate-work --previous-provenance /path/to/v1-private/provenance.json
python -m scripts.transcribe_audio --inputs /path/to/new-candidate-work/train-inputs.json --output /path/to/new-candidate-work/asr-train --model-cache /path/to/whisper-model
python -m scripts.transcribe_audio --inputs /path/to/new-candidate-work/dev-inputs.json --output /path/to/new-candidate-work/asr-dev --model-cache /path/to/whisper-model
python -m scripts.transcribe_audio --inputs /path/to/new-candidate-work/test-inputs.json --output /path/to/new-candidate-work/asr-test --model-cache /path/to/whisper-model
python -m scripts.build_final_dataset freeze --work /path/to/new-candidate-work --output /path/to/new-public-release --private /path/to/new-private-release
python -m scripts.build_final_dataset seal --output /path/to/new-public-release
```

후보·모델 출력·정답 대응표는 비공개 작업 폴더에 두세요. 고정 출력과 같은 원천·seed·사전이면 최종 파일 선택·초안·주석을 재현합니다. 기존 봉인된 버전은 덮어쓰지 않습니다.
