# 공개 Eval 음질 손상 보조 트랙

이 실험은 **기존 v2의 공개 Eval 409개만** 사용한다. 비공개 Test와 공식 순위의 정의는 바꾸지 않는다.
현재는 생성·검증 단계이며, 손상 음성의 모델 결과나 청취 검수는 아직 없다.
원래 v2의 Copy·Whisper·Qwen Audio-only 집계를 확인한 뒤 설계한 공개 개발 실험이다.
새로운 블라인드 평가나 이미 검증된 고난도 벤치마크로 소개하지 않는다.

## 연구 질문

음질이 달라지면 같은 모델의 Audio+draft가 Audio-only보다 유리해지는가?
원래 맞는 초안을 불필요하게 수정하는 비율도 달라지는가?
Text-only, Audio-only, Audio+draft를 비교해 어느 입력에 의존하는지 살핀다.
음성·초안 결합 자체가 새로운 방법이라는 주장은 하지 않는다.

## 결과를 보기 전에 고정할 구성

각 원본을 아래 세 조건으로 모두 만든다. 초안·정답·길이는 세 조건에서 같다.
오류율이나 모델 성능으로 발화를 선택·제외하거나 손상 강도를 바꾸지 않는다.

| 조건 | 음성 처리 | 초안 |
|---|---|---|
| original | 원본 WAV 바이트 유지 | 기존 실제 ASR 초안 |
| gaussian_5db | 전체 발화 RMS 기준 합성 백색 가우시안 잡음, SNR 5 dB | 동일 초안 |
| packet_loss_20 | 20 ms 패킷의 20%를 고정 seed로 선택해 0으로 대체 | 동일 초안 |

재생 가능한 세 조건은 총 1,227개지만 **서로 다른 녹음은 409개·1시간**이다.
Train/Test로 재분할하지 않는다. 한 원본의 세 변형은 항상 같은 묶음으로 다룬다.
합성 백색 잡음은 실제 현장 소음의 대표 표본이 아니다. 패킷 손실은 패킷 은닉·재전송 없는 단순 영 대체다.

난수는 `SHA256(tye-public-eval-stress-v1:condition:base_id)` 앞 8바이트를
정수 seed로 삼은 NumPy PCG64를 쓴다. 패킷 수는 마지막 불완전 패킷도 포함하며,
손실 개수는 `floor(0.2 × 패킷 수 + 0.5)`로 정한다. 실제 샘플 손실 비율을 별도로 기록한다.
잡음 RMS는 무음 구간을 포함한 전체 신호 RMS로 정한다. 혼합 신호가 0.98을 넘으면
음성과 잡음을 같은 비율로 줄여 클리핑을 피한다. 이때의 gain과 PCM16 양자화 후 실측 SNR도 기록한다.
손상 연산에는 정답·초안 문자열이나 모델 점수를 전달하지 않는다.

원본 초안의 정규화된 정답 일치 여부로 clean/error를 나누되 비율을 인위적으로 맞추지 않는다.
각 음질 조건에 동일한 clean/error 발화가 들어간다. 이 분류는 문자열 일치 진단이며,
원천 전사가 실제 발화와 일치하는지는 독립 청취가 필요하다.

## 측정

ko-correction-v2의 Micro CER·발화 평균 CER·WER·슬롯 복원률·정상 문자 훼손률·
불필요 삽입률·Clean 변경률을 음질 조건별로 제공한다. 초안 생성기별 결과도 유지한다.
세 음질 조건을 합친 수치를 기존 v2의 공식 순위와 섞지 않는다.

같은 Qwen 체크포인트의 조건별 `CER(Audio-only) − CER(Audio+draft)`를 비교한다.
손상 조건에서 이 차이가 커지면 초안 결합의 이점이 커졌다는 기술적 관찰을 할 수 있다.
통계적 유의성이나 독립 데이터에 대한 일반화는 별도 근거 없이 주장하지 않는다.
Whisper 비교에서는 입력 외에 모델도 다르므로 입력 결합 효과로 해석하지 않는다.

Copy와 Text-only는 초안이 같으므로 음질 조건 간 예측이 같아야 한다.
원본의 기존 측정 출력은 입력 WAV/초안 해시·고정 모델 설정을 확인한 경우에만 재사용한다.
손상 음성의 Whisper Audio-only·Qwen Audio-only·Qwen Audio+draft는 새로 추론한다.
기존 모델 작업이 끝난 뒤 순차 실행해 같은 GPU에서 두 모델을 동시에 올리지 않는다.
모델·프롬프트·greedy·512토큰 한도는 기존 v2와 동일하게 유지하고 빈/길이 제한 출력도 포함한다.

## 해석과 검수

초안은 손상 전 원본 음성에서 생성됐다. 따라서 초안에 수신 음성보다 더 많은 정보가 남아 있을 수 있다.
이 정보 비대칭은 이 실험의 조건이며, 같은 손상 음성에서 초안을 생성하는 일반적인 noisy ASR 후처리와 구분한다.
이를 통제하지 않고 기존 ASR 교정 방법보다 우수하다고 비교하지 않는다.

정답은 손상되기 전 원래 발화다. 일부 구간의 단서가 사라지면 원래 발화를 복원할 수 없을 수도 있다.
따라서 이 실험은 손상 음성과 초안을 이용한 복원 과제이며, 모든 구간이 귀로 식별 가능하다고 가정하지 않는다.
손상 전후 청취로 구간의 판별 가능성을 확인하기 전에는 성능 저하를 추론 능력 부족으로 단정하지 않는다.
현재 출력 형식에는 보류·확신도 제출이 없으므로 risk–coverage나 보류 성능을 측정했다고 쓰지 않는다.

기존 공개 자료와 새 음성·초안·정답을 모두 공개하는 개발용 보조 트랙이다.
교수 제출 자료에는 구성 완료, 실제 측정 완료, 청취 검수 완료를 구분해 표시한다.

## 공개 자료와 재현

[보조 트랙 웹 채점](https://jhparktime.github.io/TURST-YOUR-EARS/stress.html)에서
전체 1,227행 CSV를 채점하고 조건별·초안 정오답별 전체 JSON을 내려받을 수 있다.
음성·초안·정답은 별도 공개 개발 후보 release로 제공하며 Test 자료를 포함하지 않는다.

```sh
pip install -r requirements-stress.txt
python -m scripts.build_public_eval_stress --public /data/tye-v2-public --output /data/public-stress
python -m scripts.validate_public_eval_stress --public /data/tye-v2-public --probe /data/public-stress --output /data/public-stress/validation.json
python -m scripts.baseline --mode copy --inputs /data/public-stress/eval/inputs.json --output /tmp/stress-copy.csv
python -m scripts.evaluate_public_stress --probe /data/public-stress --predictions /tmp/stress-copy.csv
```

이미 만들어진 후보 ZIP을 사용하면 앞의 생성·검증 단계를 생략하고 채점을 재현할 수 있다.
Copy의 세 조건 CER는 모두 11.766335975170426%다. 음성은 모델에 입력하지 않으므로 같은 초안의 점수는 같다.
이 동일성은 채점 검산이며 손상 음성의 난도를 측정한 결과가 아니다.

손상 음성의 Qwen 입력 비교에는 `scripts.run_omni_baselines`의 `--public /data/public-stress/inference`,
`--splits eval --modes audio-only audio-draft --max-new-tokens 512`를 사용한다.
고정 모델 스냅샷과 MPS/BF16 설정은 기존 v2와 같다. Text-only와 원본 결과는
입력·완료 출력 해시를 확인한 뒤 재사용한다. 운영자 순차 실행기는
`scripts.run_public_eval_stress_suite`, 측정 출력 검증·집계는 `scripts.score_public_eval_stress`다.
결과를 공개할 때는 `scripts.build_public_eval_stress_assets`로 공개 정답·대응표·집계만 내보낸다.
