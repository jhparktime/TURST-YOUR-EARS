# Baseline measurements · tye-ko-merged-v1

동일한 고정 eval/test에서 측정한 결과입니다. 모든 값은 %이며 개선폭은 %p입니다.
개별 test 예측·정답은 포함하지 않았습니다. 미완료 실험은 점수 0으로 대체하지 않습니다.

| Baseline | Split | Macro CER ↓ | Micro CER ↓ | WER ↓ | 개선폭 ↑ | 복원률 ↑ | 훼손률 ↓ | Clean 변경률 ↓ | 최악 조건 CER ↓ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Copy draft | eval | 2.6263 | 2.6326 | 6.5078 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 5.1758 |
| Copy draft | test | 2.7211 | 2.7193 | 6.8176 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 5.4982 |
| Whisper large-v3-turbo · Audio only | eval | 6.1864 | 6.1852 | 24.8321 | -3.5601 | 96.5686 | 6.3382 | 64.9635 | 6.6667 |
| Whisper large-v3-turbo · Audio only | test | 5.3424 | 5.3417 | 23.7329 | -2.6213 | 96.8589 | 5.4490 | 57.1184 | 5.6440 |
| Qwen2.5-Omni-3B · text-only | eval | 8.4616 | 8.4687 | 16.0058 | -5.8353 | 9.0686 | 5.5656 | 44.5255 | 11.1148 |

Copy는 초안을 그대로 유지합니다. Whisper는 초안 없이 음성만 입력합니다.
Whisper: `mlx-community/whisper-large-v3-turbo@a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb`.
ko, temperature 0, task transcribe, initial prompt 없음, 이전 발화 문맥 재사용 없음.
Qwen 실험은 고정 `Qwen/Qwen2.5-Omni-3B@f75b40e3da2003cdd6e1829b1f420ca70797c34e`에서 입력만 비교합니다.
Whisper와 Qwen의 성능 차이를 입력 효과만으로 해석하지 않습니다.

미완료 split별 측정: 5건. 조건별 CER/WER와 분자·분모는 [전체 JSON](../web/data/baselines.json)을 확인하세요.

현재 오류는 실제 ASR 오인식이 아닌 합성 명사 치환입니다. 독립 청취 검수는 아직이며,
높은 주입 구간 복원률을 전체 문장 정확도 또는 음성 활용의 증거로 해석하지 않습니다.
