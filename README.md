# Trust Your Ears

**한국어 음성 + 전사 초안 → 실제 발화에 맞게 교정한 전체 전사문.**

음성을 근거로 초안의 오류를 복원하면서 원래 맞던 부분을 보존하는 **Audio-grounded Transcript Correction** 챌린지입니다. 한국어 음성·전사 자료를 재사용하고 전사의 일부만 치환해 입력 초안을 만듭니다. 음성과 검수된 정답 전사는 바꾸지 않습니다.

[웹사이트](https://jhparktime.github.io/TURST-YOUR-EARS/) · [베이스라인](scripts/baseline.py) · [채점 코드](server/scoring.py)

**현재 상태:** 웹·채점 규격·베이스라인 실행 코드와 [실제 한국어 음성을 포함한 합성 오류 파일럿](datasets/tye-fleurs-ko-v1/README.md)을 제공합니다. 개발 30개·평가 75개이며 독립 청취 검수는 아직 남아 있습니다. 실제 모델 결과와 호스팅된 채점 서버 연결은 준비 전입니다. `examples/`의 6행은 별도의 음성 없는 소프트웨어 테스트 자료입니다. 저장소의 기존 `TURST-YOUR-EARS` 철자는 유지합니다.

## 과제 정의

모델은 음성과 초안만 봅니다. 오류 유무·위치·개수나 정답을 제공하지 않습니다. 초안이 맞으면 유지하고, 오류가 있으면 해당 부분을 수정하여 **전체 전사문**을 출력합니다. 발화를 요약하거나 문법에 맞게 다듬는 과제가 아닙니다.

| 조건 | 초안 생성 | 확인할 행동 |
|---|---|---|
| `clean` | 정답 전사를 그대로 사용 | 맞는 초안 보존 |
| `single` | 한 구간 치환 | 오류 한 곳 복원 |
| `multiple` | 떨어진 2–4개 구간 치환 | 여러 오류 복원과 정상 구간 보존 |

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

| 실행 모드 | 모델에 보이는 입력 | 역할 |
|---|---|---|
| `copy` | 초안 | 그대로 복사하는 기준점 |
| `audio-only` | 음성 | 초안 없이 다시 전사 |
| `text-only` | 초안 | 언어 지식만으로 가능한 교정 |
| `audio-draft` | 음성 + 초안 | 음성 근거를 이용하는 단순 교정 |

모델 방식 세 가지는 **동일한 Qwen2.5-Omni 체크포인트**를 사용합니다. 모델 크기·생성 설정·개발 데이터·출력 후처리를 고정합니다. Audio only 프롬프트에는 초안을 넣지 않고, Text only에는 음성 파일이나 음성 인식 결과를 넣지 않습니다. 각 발화는 새 대화로 처리하며 다른 평가 발화의 출력은 재사용하지 않습니다.

[공식 모델 카드](https://huggingface.co/Qwen/Qwen2.5-Omni-3B)의 텍스트·음성 입력 인터페이스에 맞춘 실행 코드입니다. **한국어 실제 추론은 아직 실행하지 않았습니다.** 한국어 적합성, GPU 메모리, 설치 조합은 파일럿에서 확인하고 최종 모델을 확정합니다. 모델 이용 조건도 해당 모델 카드를 따릅니다.

모델 실험은 웹 서버와 별도 Python 3.12 환경에서 준비합니다. 아래 Transformers 태그는 모델 카드의 설치 예시를 따릅니다. GPU에 맞는 PyTorch 및 ffmpeg가 필요하며 전체 환경 잠금 파일은 첫 실험 후 보관합니다.

```sh
pip install 'git+https://github.com/huggingface/transformers@v4.51.3-Qwen2.5-Omni-preview' accelerate qwen-omni-utils
```

모델을 불변 버전으로 내려받은 로컬 스냅샷 경로를 사용합니다. 입력 JSON의 음성 경로는 그 JSON이 있는 폴더 기준입니다.

```sh
python -m scripts.baseline --mode audio-only --model /path/to/fixed-model-snapshot --inputs /data/dev/inputs.json --output /tmp/audio-only.csv
python -m scripts.baseline --mode text-only --model /path/to/fixed-model-snapshot --inputs /data/dev/inputs.json --output /tmp/text-only.csv
python -m scripts.baseline --mode audio-draft --model /path/to/fixed-model-snapshot --inputs /data/dev/inputs.json --output /tmp/audio-draft.csv
python -m scripts.evaluate --references /data/dev/references.json --predictions /tmp/audio-draft.csv --output /tmp/audio-draft.scores.json
```

원격 모델 ID를 사용하면 `--revision`에 40자리 커밋 SHA를 지정해야 합니다. 모델 가중치를 자동으로 실행하거나 유료 API를 호출하는 웹 기능은 없습니다. 예측 CSV 옆의 `.run.json`에는 모델·버전·프롬프트·시드·패키지 목록과 입력/출력 파일 해시가 저장됩니다. 모델 스냅샷 해시, 음성 파일 해시, 하드웨어 정보도 실험 보고에 함께 보관하세요. 출력 제한에 도달하면 조용히 잘라 제출하지 않고 실패합니다.

텍스트 예시에서 Copy draft와 입출력 검증을 실행할 수 있습니다. Audio 모드는 실제 음성 없이는 실패합니다. 예측 파일을 쓰기 전 모든 발화의 추론이 성공해야 하며, 실패한 행을 정답으로 채우는 대체 처리는 없습니다.

## 평가용 음성 데이터

[FLEURS 한국어 기반 파일럿](datasets/tye-fleurs-ko-v1/README.md)에 원본 WAV 105개와 합성 오류 초안이 있습니다. 개발 30개(조건별 10개), 평가 75개(조건별 25개), 총 약 23분 52초입니다. 음성·정답은 원천 자료를 유지하고 초안만 치환했습니다. CC BY 4.0 출처·변경 사항과 재현 절차를 데이터 카드에 기록했습니다.

[구축 코드](scripts/build_dataset.py)와 [검증 코드](scripts/validate_dataset.py)를 제공합니다. 공개 개발 정답은 `datasets/tye-fleurs-ko-v1/dev/references.json`, 비공개 평가 정답과 검수표는 로컬 `private-data/tye-fleurs-ko-v1/`에 있습니다. 생성 코드와 원천은 공개되어 있으므로 원문 조회·사전학습 오염을 해결한 비밀 평가셋은 아닙니다. 독립 청취 검수와 화자 분리 확인은 완료되지 않았습니다.

```sh
pip install -r requirements-dataset.txt
python -m scripts.validate_dataset --private private-data/tye-fleurs-ko-v1
```

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
3. **희소 치환:** 문장의 대부분은 유지하고 이름·숫자·내용어 단위로 1곳 또는 2–4곳을 바꿉니다. 길이·도메인·화자·목표 표현 유형을 조건별로 균형 있게 배정하고 초안 CER 분포를 기록합니다. 짧은 문장에 4곳을 강제로 넣지 않습니다.
4. **검수 항목:** 동일 발음이라 음성으로 구별 불가능한 오답, 명백한 비문이라 텍스트만으로 답을 찾는 오류, 조사 불일치, 숫자 표기만 다른 사례를 점검합니다. Text only가 잘 푸는 사례도 별도 분석할 수 있도록 기록합니다.
5. **누출 방지:** 공개 평가에는 원본당 초안 하나만 제공합니다. 같은 음성의 Clean과 오류 초안을 동시에 배포하지 않습니다. 모든 변형은 같은 split에 두고, 짝지은 변형 비교는 개발셋 또는 주최 측의 독립 실행에서만 합니다. 소프트웨어 fixture의 반복 발화는 이 공식 데이터 규칙의 예외이며 성능 분석에 사용하지 않습니다.
6. **인계:** 음성 파일, 공개 입력 JSON, 비공개 정답 JSON, 출처 URL·라이선스·원본 ID·화자/세션·split·음성 해시·검수자·치환 유형·생성 seed를 담은 관리 기록을 전달합니다. 공개/비공개 ID·초안이 일치하는지 확인합니다. 서버는 음성을 듣거나 출처 권리를 검증하지 않습니다.

수량은 파일럿 검수와 난도를 보고 결정합니다. 수백 문장을 새로 녹음할 필요는 없습니다. 공개 원천의 전사가 검색되거나 사전학습에 포함될 수 있으므로 비공개 정답 파일만으로 오염이 해결되지는 않습니다. 원문 조회 금지 등 참가 규칙과 한계를 공개하고, 별도 실음성 검증이 가능하면 보완합니다. 인위적 오류와 실제 ASR 오류는 결과를 섞어 해석하지 않습니다.

## 평가 규격

공통 구현: [`server/scoring.py`](server/scoring.py), **ko-correction-v1**. 파일럿 음성 데이터가 제공되며, 독립 청취 검수 후 정식 평가 전에 분할·조건별 수량·표기 기준·모델/외부 데이터 사용 규칙을 동결합니다.

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

CSV는 정확히 `id,prediction` 두 열, UTF-8, 모든 ID 한 번씩입니다. BOM·따옴표로 감싼 쉼표를 지원하며 빈 예측은 삭제 오류입니다. API는 최대 2 MiB, 20,000행, ID 120자, 예측 4,000자입니다. 정답·초안은 NFC, 정규화 후 1–1,000자 및 원문 최대 4,000자, 치환 최대 4곳·치환문 최대 100자입니다. 계산량 1,500만 DP cell 한도를 적용하므로 운영자는 전체 데이터셋과 긴 예측으로 공개 전 점검해야 합니다.

기본 제출 한도는 팀별 UTC 하루 5개의 유효한 새 예측입니다. 한국 시간 오전 9시에 초기화되며 무효 파일은 차감하지 않습니다. 동일 ID/예측 매핑은 기존 결과를 반환합니다. 평가 버전과 정답 manifest 해시로 결과·이력·한도를 분리하여 예전 규격 점수를 섞지 않습니다. API는 집계값만 반환하고 개별 정답·오류 위치를 반환하지 않습니다.

## 웹 운영

상단의 **한국어 / English** 버튼으로 여섯 페이지의 설명, 접근성 문구, 채점 결과·제출 기록·리더보드·오류 안내를 전환합니다. 언어 선택만 브라우저에 저장하며, 전사 예시와 제출 파일은 한국어 원문을 유지합니다. 전환 중 팀 키·선택 파일·결과는 유지되고 추가 API 요청이나 제출은 발생하지 않습니다.

- GitHub Pages는 `web/`만 배포합니다. 정답·서버·DB는 배포하지 않습니다.
- 별도 HTTPS Python API가 팀 키를 확인하고 비공개 정답으로 채점합니다.
- 로컬 SQLite 또는 `DATABASE_URL`의 PostgreSQL에 팀·점수를 보관합니다.

GitHub Pages만으로 비공개 서버 채점을 실행할 수 없습니다. `web/config.js`의 `apiBase`가 비어 있으면 Pages는 평가 준비 상태를 표시하고 제출을 막습니다. 로컬에서는 같은 출처의 FastAPI에 연결됩니다. 웹과 서버의 scorer 버전이 다르면 제출을 막습니다.

배포는 GitHub Settings → Pages → GitHub Actions를 선택한 후 `main`에 push하면 테스트 후 실행됩니다. 호스팅된 API 연결은 별도 운영 단계입니다. [`render.yaml`](render.yaml)을 활용할 수 있으나 [무료 서비스의 현재 제약](https://render.com/docs/free)을 확인하고 영속 DB를 사용해야 합니다. 서버 계정·키는 이 저장소에서 발급하지 않습니다.

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

웹 설명·베이스라인 코드·평가 규격은 전사 교정으로 통일했습니다. 실제 한국어 음성·합성 오류 초안과 정답 파일은 파일럿으로 구축했습니다. 남은 항목은 **독립 청취 검수와 정식 평가셋 확정**, **실측 모델 베이스라인 비교**, **외부 채점 서버 연결**, **수업 저장소용 단일 HTML 제출물**입니다. 이 저장소에 실제 성능이나 학회 제휴를 가장한 예시는 넣지 않습니다. 수업 저장소 PR은 별도 제출 단계입니다.
