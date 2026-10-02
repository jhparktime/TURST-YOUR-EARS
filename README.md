# Trust Your Ears

A workshop-style Korean contextual ASR challenge: use helpful references without adopting incorrect names. The website, private evaluator, and leaderboard share the versioned `ko-cer-v1` protocol.

**Status:** the frontend is published; the hosted evaluator is not connected. Official Korean audio, contexts, dates, and team registration are not released. The eight-row public sandbox fixture contains no audio and is a software test, not evidence of ASR performance. The repository intentionally retains its existing `TURST-YOUR-EARS` spelling.

## Task and research scope

Input: a Korean audio clip and a short reference document/name list. Output: the complete spoken transcript. Four context types are planned: `helpful`, `partially_wrong`, `misleading`, `irrelevant`, crossed with original/noisy audio after pilot validation. `no_context` is a separate diagnostic control, excluded from ranking and aggregate entity metrics.

Illustrative example: the audio says “김민서가 네오젠 실적을 발표합니다.” A partially incorrect reference lists “김민수 · 네오젠”. The desired transcript keeps both actually spoken names. The proposed research method, **Verify Before You Correct**, checks contextual edits against audio; its effectiveness has not been established.

## Run and test

Python 3.12 or later:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
DEMO_MODE=1 uvicorn server.app:create_app --factory --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/#submit, select **공개 샌드박스 키 사용**, and upload [`web/assets/sample-submission.csv`](web/assets/sample-submission.csv). The public key is `demo-team-key`. The sample contains two deliberate name substitutions:

| Metric | Expected |
|---|---:|
| Macro CER | 1.612903…% |
| Helpful / Irrelevant CER | 0% / 0% |
| Partially wrong / Misleading CER | 3.225806…% / 3.225806…% |
| Entity accuracy | 87.5% (14/16) |
| Wrong-context adoption | 33.333333…% (2/6) |
| Mixed-context joint accuracy | 50% (1/2) |

```sh
python -m pytest -q
```

The Postgres persistence test runs when `TEST_POSTGRES_URL` points to a disposable test database; CI provides one. All other tests use temporary local storage. These checks validate software behavior, not benchmark validity.

## Scoring contract

Canonical code: [`server/scoring.py`](server/scoring.py). Version: **ko-cer-v1**. These rules describe the implemented sandbox; the official dataset/group weights are not yet frozen. Exact CSV header: `id,prediction`. Include every ID once; missing/extra/duplicate IDs are rejected. UTF-8 BOM and quoted commas are supported. Empty predictions count as deletions.

### Main metric

Normalize with Unicode NFC and lowercase Latin text. Remove all whitespace and the explicit `IGNORED` punctuation set in the scorer. After whitespace removal, a period is preserved only between adjacent digits. Signs, slash, percent symbols, and other nonlisted symbols remain. Thus `-3.5%` differs from `35%`. There is no numeric expansion, phonetic rewriting, stemming, semantic matching, or LLM judge. Korean syllables count as characters, not decomposed jamo. `AI` and `에이아이`, or `3시` and `세 시`, differ in primary CER.

Calculate Levenshtein edits per utterance. Pool edits and reference character counts **within** each condition, then average contextual condition CERs equally. No-context rows are reported separately and do not affect primary or aggregate diagnostic scores. Micro CER pools all contextual groups; worst CER takes their maximum. Secondary eojeol WER uses whitespace-separated normalized tokens. Error rates are percentages and may exceed 100%.

### Entity diagnostics

Optional human annotations use sorted, nonoverlapping **Python character offsets in the original NFC reference**; `end` is exclusive. Exclude particles from name spans. Entity accuracy counts correct occurrences, not distinct names. Wrong-context adoption counts targeted positions with a nonempty `wrong` list; success means the aligned prediction equals one of those distractors. Mixed-context joint accuracy applies to annotated `partially_wrong` utterances and requires every annotated target to be correct. The manifest must include both corrupted and uncorrupted entities in each such annotated utterance. Missing denominators return JSON `null`, displayed as N/A, with counts.

Canonical entity text, approved aliases, distractors, and aligned predicted text use the same normalization as CER. Approved `aliases` affect entity diagnostics only. The scorer enumerates permitted reference variants, selects the minimum full-transcript edit distance, and extracts aligned target spans. Ties between variants retain manifest order (canonical spelling first). Alignment ties use diagonal, deletion, insertion priority. Insertions at a span's right boundary belong to that span; at its left boundary they do not. This conservative boundary convention can penalize adjacent insertions. Annotators should avoid ambiguous boundaries and publish boundary examples. It is a deterministic diagnostic, not semantic identity recognition or proof that context caused an error. A name merely occurring elsewhere in a transcript does not receive substring-search credit.

Diagnostics are pooled across contextual samples; **they are not averaged per condition**. Counts and condition breakdowns are returned. Freeze spellings, aliases, and distractors before inspecting model outputs. Paired no-context error flips and speaker/session bootstrap confidence intervals are planned for the research report, not implemented by this scorer.

### Ranking and limits

Best full-precision Macro CER per team; exact ties share rank (1, 1, 3). Submission time orders tied rows for display only. At equal score, the first submission remains that team's representative result. Display rounds to two decimals; displayed equal values need not be exact ties.

Default allowance: five accepted unique submissions per team per UTC day (09:00 Korea time). Invalid files do not count. Identical ID/prediction mappings reuse the previous result and timestamp, even after the limit or on another day. The API returns aggregate metrics, not private transcripts, entity strings, or per-utterance errors.

CSV: at most 2 MiB, 20,000 rows, 120 characters per ID, 4,000 raw characters per prediction. References: 1–1,000 normalized characters; at most four entities and 16 alias combinations per row. Requests have a 15-million dynamic-programming-cell budget, including alignment and alias evaluation; organizers must check full-manifest workload before release. The budget is checked before scoring.

Both **scorer version and reference content hash** namespace stored scores, history, and submission allowance. Changes produce a fresh leaderboard; old records remain stored and do not mix with the new protocol.

## Private reference manifest

Only the deliberately public sandbox manifest belongs in the repository. Official references must be supplied privately on the evaluation host.

```json
{
  "name": "korean-evaluation-v1",
  "conditions": ["partially_wrong_clean"],
  "items": [{
    "id": "eval-001",
    "condition": "partially_wrong_clean",
    "context": "partially_wrong",
    "reference": "김민서가 네오젠 실적을 발표합니다.",
    "entities": [
      {"start": 0, "end": 3, "text": "김민서", "wrong": ["김민수"]},
      {"start": 5, "end": 8, "text": "네오젠", "aliases": []}
    ]
  }]
}
```

This is a schema example, not an evaluation corpus. Explicit `context` is required when condition names include an acoustic suffix. Each group has exactly one context type. `conditions`, when provided, must match the actual group set; official releases should always declare it. A nonempty `wrong` field declares a corrupted target; a missing or empty field declares an uncorrupted target. The scorer trusts those annotations and does not inspect context documents. Organizers must verify these declarations against the actual public input documents. The sample has four groups, two rows each. Each distinct condition string is one equally weighted averaging group: four groups in the sandbox, eight context × acoustic groups in the proposed full matrix. The proposed full matrix has eight contextual groups, but must be finalized from real pilot data before launch. Public inputs should contain opaque IDs, audio and reference documents, without ground-truth condition labels, target spans, aliases or distractor annotations.

## Hosting

- **GitHub Pages:** publishes only `web/`, never reference manifests, server code or databases.
- **HTTPS Python API:** authenticates teams, validates submissions, scores against private references, and stores results.
- **SQLite** for local/persistent-disk hosting; **PostgreSQL** via `DATABASE_URL` for durable hosted storage.

GitHub Pages alone cannot run the private scorer. With no `apiBase` in [`web/config.js`](web/config.js), local FastAPI serves the whole application; the GitHub Pages site displays a prelaunch state and disables submission. No results are fabricated in the browser. Frontend/backend scorer-version mismatches block submission.

### Frontend deployment

1. Set GitHub **Settings → Pages → Source: GitHub Actions**.
2. Push to `main`. The workflow tests against SQLite and Postgres before publishing `web/`.
3. Connect a deployed HTTPS evaluator by setting `apiBase` to its origin in `web/config.js`.
4. Site: https://jhparktime.github.io/TURST-YOUR-EARS/

### Separate evaluator

The included [`render.yaml`](render.yaml) uses a free Render service; plan details can change, so check [Render's current free-service documentation](https://render.com/docs/free). Its ephemeral filesystem is unsuitable for scores. A [Supabase Free project](https://supabase.com/pricing) can provide Postgres within its current limits. Free services may sleep or pause; account creation and connection remain operator setup steps.

1. Create the database and obtain a session-pooler connection string with TLS (`sslmode=require`). Store it privately as `DATABASE_URL`; never in `web/config.js`.
2. Deploy the Render Blueprint in sandbox mode first. The evaluator creates the private `tye_private` schema. Do not expose it through Supabase APIs or grant browser roles access.
3. Set `ALLOWED_ORIGINS=https://jhparktime.github.io` and connect `apiBase`.
4. Check submission, ranking and persistence after a service restart.
5. For official evaluation, upload the manifest through a private secret-file mechanism, set `REFERENCE_PATH` to its private path, and set `DEMO_MODE=0`.

For SQLite deployment, mount a persistent `/data` disk and run one worker. A stateless deployment without Postgres loses team keys and scores on restart.

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
curl -f http://127.0.0.1:8000/api/health
DATA_DIR=/data python -m scripts.create_team 'Team name'
```

For hosted Postgres, provision teams from a trusted terminal with the private `DATABASE_URL`. Team keys are printed once and stored only as hashes. Send them privately. There is no registration dashboard. Close submissions with `SUBMISSIONS_OPEN=0` and restart. Back up data and enforce HTTPS, proxy body limits with modest multipart overhead above 2 MiB, and request rate limits before public launch.

API: `GET /api/health`, `GET /api/leaderboard`, authenticated `GET/POST /api/submissions`. Team authentication: `Authorization: Bearer TEAM_KEY`. Interactive schema: `/api/docs`.

## Before official release

- Select Korean source audio, confirm access/redistribution rights, and record provenance. No Korean source corpus has been selected yet.
- Start with a proposed 100-original-utterance pilot. Have two listeners independently verify actual audio without seeing manipulated context. Exclude acoustically indistinguishable distractors from resistance claims.
- Split originals before generating variants; keep variants together and separate speakers/source sessions where possible.
- Public leaderboard inputs should use one context per original, stratified across speaker/session, utterance length and target count before assigning conditions. Exposing all versions enables cross-condition answer inference. Paired analysis needs development data or organizer-controlled isolated execution.
- Public-source references may have entered pretraining. A private answer file does not remove that contamination. Use independently recorded holdout audio when feasible and report limitations.
- Freeze condition weights, transcript style, aliases, external-data rules and submission limits before final method development. Audit complete annotation coverage and per-condition target counts.
- Publish dates, organizer contacts, source licenses, input downloads, baseline code and a reproducible evaluation recipe. There is no claimed conference affiliation.

## Layout

```text
web/                    Pages frontend and public example CSV
server/                 authenticated API, scorer and database adapter
scripts/create_team.py  organizer-only team provisioning
examples/               deliberately public text-only fixture
tests/                 scoring and API integration tests
.github/workflows/      tests and Pages deployment
```
