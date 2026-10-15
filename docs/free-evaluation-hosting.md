# 비공개 Test 채점 서버 연결

공개 eval은 이미 GitHub Pages에서 서버 없이 채점한다. 아래 절차는 비공개 test 제출과
팀별 순위를 운영할 때 사용하는 별도 API의 배포 준비다. 현재 외부 서버는 연결하지 않았다.

## 무료 구성과 범위

GitHub Pages에 현재 화면을 유지하고, Render Free에서 기존 Python API를 실행하며,
Supabase Free의 PostgreSQL에 팀 키 해시와 결과를 보관한다. 음성 추론은 참가자 환경에서
실행하므로 채점 서버에 GPU나 음성 파일을 올리지 않는다.

Render Free는 유휴 15분 후 중지되고 다시 켜지는 데 약 1분이 걸린다. 로컬 파일 변경도
재시작 시 사라지므로 순위 DB를 SQLite에 두지 않는다. 서비스 중단·사용량 제한이 있는
수업 프로젝트용 구성이다. [Render 무료 서비스 안내](https://render.com/docs/free)

Supabase Free는 DB 500MB를 제공하며 일주일 동안 사용하지 않으면 프로젝트가 일시 중지될 수 있다.
자동 백업은 포함되지 않으므로 운영 결과는 따로 백업한다.
[Supabase 요금제](https://supabase.com/pricing)

## 1. DB와 초기 서비스

Supabase에서 Free 프로젝트를 만들고 Connect 화면의 **Session pooler** 연결 문자열을 사용한다.
IPv4 환경에서 직접 연결이 안 될 때 쓸 수 있는 방식이다. TLS를 사용하며, 비밀번호에 예약 문자가
있으면 연결 문자열에 맞게 인코딩한다. [공식 연결 안내](https://supabase.com/docs/guides/database/connecting-to-postgres)

Render에서 이 저장소의 `render.yaml`을 사용해 Free 서비스를 생성하고, `DATABASE_URL`에
그 연결 문자열을 넣는다. 기본값 `DEMO_MODE=1`은 공개 toy sandbox이므로 공식 Test가 아니다.
이 단계에서는 사이트의 `web/config.js`를 바꾸지 않는다.

DB 접속 정보는 Render의 Environment에만 입력한다. 브라우저 설정에 DB 키나 접속 문자열을
넣지 않는다. 서버가 만드는 `tye_private` 스키마는 Supabase Data API의 노출 스키마에 추가하지 않는다.

## 2. 정답 파일 전달

운영자 원본 `private-data/tye-ko-merged-v1/test-references.json`을 사용한다.
현재 파일은 **909,054바이트**이고 SHA256은 아래와 같다.

```text
a30819e3dadc78861661e2ccb673e8d76a35947af9a71693c339af22bacdac96
```

Render의 Environment → Secret Files에서 파일명을
`tye-ko-merged-v1-test-references.json`으로 지정하고 원본 내용 전체를 넣는다.
JSON을 다시 정렬하거나 공백·마지막 줄바꿈을 바꾸지 않는다. 원본 ZIP 전체나 음성은 필요하지 않다.
Render는 Secret Files의 합계 크기를 1MB로 제한하고 파일을 `/etc/secrets/<파일명>`에 제공한다.
현재 정답 파일 하나는 이 한도 안에 들어간다.
[Secret Files 안내](https://render.com/docs/configure-environment-variables#secret-files)

그다음 Environment를 아래 값으로 바꾸고 다시 배포한다.

| 항목 | 값 |
|---|---|
| `DEMO_MODE` | `0` |
| `REFERENCE_PATH` | `/etc/secrets/tye-ko-merged-v1-test-references.json` |
| `DATABASE_URL` | 본인의 Supabase TLS 연결 문자열 |
| `ALLOWED_ORIGINS` | `https://jhparktime.github.io` |
| `DAILY_LIMIT` | `5` |
| `SUBMISSIONS_OPEN` | `0` — 연결 확인 후 개방 |

## 3. 공개 주소 확인

생성된 서비스 주소의 `/api/health`에서 아래 항목이 모두 일치하는지 확인한다.

```json
{
  "mode": "evaluation",
  "dataset": "tye-ko-merged-v1-test",
  "dataset_version": "a30819e3dadc",
  "scorer": "ko-correction-v1",
  "primary_metric": "macro_cer",
  "samples": 1750,
  "submission_open": false
}
```

샘플 수만 같아서는 충분하지 않다. `dataset_version`이 다르면 Secret File의 원본 바이트가
바뀌었는지 먼저 확인한다. 프런트엔드의 기대 버전을 임의로 바꿔 통과시키지 않는다.
`/api/leaderboard`가 evaluation 모드로 응답하는지도 확인한다.

`/private-data/tye-ko-merged-v1/test-references.json`, `/test-references.json`,
`/scores.sqlite3`는 공개 URL에서 404여야 한다. 정답 파일이 웹 정적 경로에 노출되면 개방하지 않는다.

## 4. 팀과 웹사이트 연결

팀 키는 프로젝트를 받은 로컬 컴퓨터의 신뢰하는 터미널에서 발급한다.
같은 Supabase `DATABASE_URL`을 환경 변수로 설정한 뒤 다음 명령을 실행한다.
Render Free는 원격 Shell을 제공하지 않으므로 로컬 CLI를 사용한다.

```sh
python -m scripts.create_team 'Team name'
```

출력 키는 해당 팀에 별도로 전달하며 저장소에 넣지 않는다. 이 명령은 DB에 키 해시만 보관한다.
키 발급과 실제 전달은 별도 작업이며, 이 안내 작성만으로 참가자에게 메시지를 보내지 않는다.

건강 상태와 저장소 연결 확인 후 `web/config.js`의 `apiBase`를 실제 Render HTTPS 주소로 설정한다.
설정 파일의 `expectedDataset`과 `expectedReferenceVersion`은 현재 값 그대로 유지한다.
`SUBMISSIONS_OPEN=1`로 개방한 뒤 실제 사이트에서 유효한 전체 Test 예측의 채점,
팀별 제출 기록, 재시작 후 결과 보존과 CORS를 확인한다. 이 원격 검증은 아직 수행하지 않았다.

서비스 연결이 끝나면 단일 제출 HTML도 다시 생성해야 같은 API 주소가 반영된다.
연결 전 공개 eval 채점은 계속 사용할 수 있고, 비공개 Test 제출은 비활성화 상태로 둔다.
