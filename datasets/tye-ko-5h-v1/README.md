> 종료된 평가 버전입니다. 새 train에 이전 test 일부가 포함되므로 merged-v1 공개 후에는 이 test로 공식 순위를 운영하지 않습니다. [현재 merged-v1](../tye-ko-merged-v1/README.md)을 사용하고 점수를 혼합하지 마세요.

# TYE Korean Correction · 5 hours v1

한국어 **음성 + 전사 초안 → 교정된 전체 전사문** 데이터입니다. 정답은 Zeroth-Korean 원천 전사 그대로이며, 초안에만 실제 명사 치환을 주입했습니다. 상태는 **독립 청취 미검수 파일럿**입니다.

| Split | 공개 범위 | 발화 | 재생 시간 | 화자 | Clean / Single / Multiple |
|---|---|---:|---:|---:|---|
| eval | 음성·초안·정답 공개 | 421 | 3,600.001375초 (1시간) | 20 | 140 / 141 / 140 |
| test | 운영자 비공개 | 1,658 | 14,400.0070625초 (4시간) | 46 | 553 / 552 / 553 |
| 합계 | | 2,079 | 18,000.0084375초 (5시간) | 66 | |

Eval은 프롬프트·설정 개발과 공개 재현에 사용합니다. Test는 최종 리더보드에 사용하며 정답으로 학습·튜닝하지 않습니다. Test 입력은 대회 운영 시 음성·초안만 별도 배포하고, 운영자 묶음 전체를 배포하지 않습니다.

## 다운로드

- [공개 eval 전체 ZIP](https://github.com/jhparktime/TURST-YOUR-EARS/releases/download/dataset-ko-5h-v1/trust-your-ears-ko-5h-v1-public-eval.zip)
- [ZIP SHA256](https://github.com/jhparktime/TURST-YOUR-EARS/releases/download/dataset-ko-5h-v1/trust-your-ears-ko-5h-v1-public-eval.zip.sha256)
- [원천·라이선스](NOTICE), [메타데이터](metadata.json), [검증 보고서](validation-report.json)
- [생성·분할·인계 절차](../../docs/five-hour-dataset.md)

이 저장소 폴더에는 공개 eval의 입력·정답·Copy CSV와 메타데이터만 있습니다. WAV는 ZIP에서 받습니다. ZIP을 풀면 `tye-ko-5h-v1-public/eval/`에 입력 JSON과 실제 음성이 함께 있습니다. `public-release-lock.json`은 **전체 ZIP 내용**의 고정 해시 목록이며, 음성을 제외한 이 저장소 폴더의 목록이 아닙니다.

```sh
python -m scripts.baseline --mode copy --inputs /data/tye-ko-5h-v1-public/eval/inputs.json --output /tmp/eval-copy.csv
python -m scripts.evaluate --references /data/tye-ko-5h-v1-public/eval/references.json --predictions /tmp/eval-copy.csv
```

## 생성과 검증

원천은 [Zeroth-Korean, OpenSLR SLR40](https://www.openslr.org/40/), CC BY 4.0입니다. [고정 미러 버전](https://huggingface.co/datasets/kresnik/zeroth_korean/tree/1fe937899f828af822293d05e086200946088bdf)의 공식 train/test를 합친 뒤 화자·세션·문장을 새로 분리했습니다. 원천 공식 test-only 벤치마크가 아닙니다.

음성은 16 kHz mono PCM16 WAV이며 원천 FLAC의 PCM 샘플과 같습니다. 반복·패딩·속도 변경 없이 독립 원본 발화를 한 번씩 사용했습니다. 자연 무음은 재생 시간에 포함합니다. 정답에는 NFC 정규화만 적용했습니다. 숫자 읽기·약어·동의어 허용 규칙을 추가하지 않습니다.

치환 후보는 서로 다른 원천 문장에 두 번 이상 나타난 명사입니다. 길이·조사 결합 유형을 유지하고 자모 성분 1개, 없으면 2개가 다른 단어를 사용합니다. Clean=0곳, Single=1곳, Multiple=2곳이며 모든 조건은 두 오류를 만들 수 있는 같은 후보 집합에서 배정했습니다. 조건 수 차이는 1개 이내입니다. 완전한 한국어 발음 모델이나 실제 ASR 혼동 확률은 아닙니다.

자동 검사에서 화자·세션 교집합, 중복 파형, split 간 동일 문장은 없었습니다. Test는 eval 및 이전에 노출된 385개 전사와 정규화 문장 유사도 0.85 이상인 후보를 제외했습니다. 배포물을 두 번 생성해 모든 파일의 바이트 일치를 확인했습니다. Local API에서도 test 전체 1,658행의 Copy 제출·정답 제출·비공개 파일 접근 차단을 검사했습니다. 이는 실제 온라인 서버 배포를 뜻하지 않습니다.

| 소프트웨어 기준점 | Public eval | Private test |
|---|---:|---:|
| Copy draft Macro CER (%) | 2.715577 | 2.686546 |
| Copy 오류 복원률 / 정상 구간 훼손률 (%) | 0 / 0 | 0 / 0 |
| 정답 제출 Macro CER (%) | 0 | 0 |

위 값은 채점기의 동작 확인값입니다. 모델 추론 결과가 아닙니다. `ko-correction-v1`의 기존 정규화·조건별 동등 비중 Macro CER·복원·훼손 규칙을 사용합니다.

## 한계와 운영 상태

**사람의 독립 청취 검수와 블라인드 ASR 교차 검증은 수행하지 않았습니다.** 원천 전사 오류, 문맥만으로 풀리는 오류, 구별하기 어려운 발음이 남을 수 있습니다. 청취 검수표와 원본 대응표는 운영자 묶음에 있습니다. 검수로 내용을 바꾸면 새 버전과 별도 점수로 공개합니다.

공개 원천을 재사용하므로 test 원문 조회·사전학습 오염 가능성이 있습니다. Test 정답 파일을 비공개로 두는 것만으로 이를 막을 수는 없습니다. 원천 조회 금지 및 외부 데이터 규칙을 대회 시작 전 공지해야 합니다. 이전 FLEURS v2와 pilot160은 별도 버전으로 보관하며 점수를 혼합하지 않습니다.
