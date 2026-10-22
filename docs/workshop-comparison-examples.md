# 참가자용 실제 모델 비교 예시

웹사이트는 공개 Eval의 두 발화에 대해 **초안 복사 → Whisper 음성 재전사 → Qwen 음성+초안 교정** 결과를 보여 줍니다. 세 출력은 기존 베이스라인 CSV에서 가져왔으며 새로 생성하거나 사람이 고치지 않았습니다.

| 발화 ID | 비교 목적 | Copy 문자 오류 | Whisper 문자 오류 | Qwen 음성+초안 문자 오류 |
|---|---|---:|---:|---:|
| `601a22f6ff80b3227f4e` | 생성되는 → 생산되는 | 1 / 26 | 1 / 26 | 0 / 26 |
| `e245e5eed59e0ba5fc1a` | 맞는 랜섬웨어를 유지 | 0 / 31 | 1 / 31 | 0 / 31 |

오류 수와 CER는 `server/scoring_v2.py`를 그대로 사용합니다. 전사문 강조는 설명용이며 CSV 원문은 바꾸지 않습니다. 음성은 배포된 공개 Eval WAV의 바이트와 체크섬을 유지합니다.

두 발화는 **수정과 보존의 차이를 설명하려고 선택한 사례**입니다. 전체 Eval에서 Qwen 음성+초안은 CER 13.54%로 Whisper 6.19%보다 높습니다. 사례가 전체 성능 우위를 뜻하지 않도록 사이트에 전체 점수와 리더보드 링크를 제공합니다.

## 재생성

공개 Eval WAV와 고정 베이스라인의 전체 Eval CSV를 준비한 뒤 실행합니다. Eval 폴더에는 `references.json`, `copy-draft.csv`, `whisper-audio-only.csv`, `audio/`가 필요합니다.

```sh
python -m scripts.build_example_comparison \
  --eval-root /data/tye-ko-asr-v2/eval \
  --audio-draft-csv /data/baselines/eval/audio-draft.csv
```

내보내기는 공개 Eval 버전·전체 409개 ID·Copy 일치·전체 Eval 지표 일치·음성 체크섬을 확인합니다. Test manifest는 거부합니다. `web/assets/examples-v2/model-comparison.json`에 실제 출력·전체 지표·원본 CSV SHA-256을 기록합니다. 원본 음성과 두 사례의 기준 전사는 `examples.json`에 기록합니다.

첫 화면의 파형은 첫 발화의 실제 PCM 값으로부터 만들었습니다. 과정 그림은 참가 모델의 입력, 수정·보존 판단, 전체 전사문 제출을 설명하는 개념도이며 특정 모델의 내부 구조를 뜻하지 않습니다.
