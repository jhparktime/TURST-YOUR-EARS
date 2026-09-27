# Trust Your Ears

Workshop-style website and server-side evaluation for a contextual ASR course challenge.

**Status:** working local prototype. Official audio, references, dates and organizers are not yet released. The included six-row sandbox fixture tests software behavior only; it is not an ASR dataset and provides no evidence of model quality. The repo intentionally retains its existing `TURST-YOUR-EARS` spelling.

## Participant task

Input is an audio clip plus a reference name list; output is the complete spoken transcript. Teams may use contextual decoding or a transcription-and-correction pipeline, subject to the eventual frozen external-data rules. For example, audio says “send it to Marina” while the list contains “Maria”; the submitted prediction should retain “Marina.”

## Run the whole site locally

Python 3.12 or later:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
DEMO_MODE=1 uvicorn server.app:create_app --factory --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. On **Evaluate**, select **Use the sandbox team key**, upload `web/assets/sample-submission.csv`, and submit. The expected macro WER is **8.33%** (Helpful 0%, Misleading 25%, Irrelevant 0%). This is calculated by the server and stored in SQLite. The key is intentionally public in sandbox mode. Sandbox scores are not competition results.

```sh
python -m pytest -q
```

## Hosting architecture

- **GitHub Pages** serves only `web/`: introduction, task, data/rules, submission interface, leaderboard and workshop details.
- **A separate HTTPS Python service** receives predictions, authenticates team keys, validates IDs, scores against private transcripts, and stores results. Local runs use SQLite; hosted runs can use PostgreSQL via `DATABASE_URL`.
- The browser calls that service; participants remain on this website. Nothing invokes a third-party evaluation portal.
- Do not publish the private reference manifest or the SQLite database to GitHub or the Pages artifact. The committed `examples/demo-references.json` is deliberately public toy data.

GitHub Pages cannot run a private Python scorer. A GitHub deployment alone publishes the frontend, not a functioning public evaluation service.

## Deploy the frontend to GitHub Pages

1. In the GitHub repository, choose **Settings → Pages → Source: GitHub Actions**.
2. Deploy the evaluation service below and set `apiBase` in `web/config.js` to its HTTPS origin (without a trailing slash).
3. Push to `main`. The included workflow runs tests and publishes **only `web/`**.
4. The project-site address is `https://jhparktime.github.io/TURST-YOUR-EARS/`.

With an empty `apiBase`, the site uses its own origin. This runs locally via FastAPI, but on GitHub Pages the form correctly displays “service not connected” and disables submission.

## Free hosted option: Render + Supabase

Current official plan documentation: [Render Free](https://render.com/docs/free), [Supabase Free](https://supabase.com/pricing). Free usage has limits; do not select paid compute or extras. Render sleeps after 15 minutes idle and may take about a minute to wake; Supabase may pause after a week of inactivity. This is suitable for a course prototype, not an availability guarantee.

1. Create a **Supabase Free** project. Copy its PostgreSQL session-pooler connection string from the Connect dialog and require TLS (`sslmode=require`). Keep the database password private.
2. In Render, create a Blueprint from this repository. `render.yaml` explicitly uses a **Free** Python web service and does not create a Render database. Render’s own free Postgres expires after 30 days.
3. Enter the connection string as the secret `DATABASE_URL` when prompted. The server creates a private `tye_private` schema. Do not add this schema to Supabase’s exposed schemas or grant browser roles access. The browser never receives the database credentials.
4. Deploy in sandbox mode first, then set `web/config.js` to the resulting Render HTTPS origin and push the change.
5. Test a submission and verify that its result survives a service restart.
6. For official evaluation, add the reference JSON through Render’s **Secret Files** interface, set `REFERENCE_PATH=/etc/secrets/private-references.json`, and change `DEMO_MODE=0`. Do not upload the official JSON to the public repository.
7. Render Free has no shell access. Provision teams from a trusted local terminal with `DATABASE_URL` set privately, using the same `python -m scripts.create_team` command.

With `DATABASE_URL` configured, team keys and scores live in Supabase rather than Render’s disposable filesystem. Never put database credentials in `web/config.js`. Creating and connecting these external accounts remains an operator setup step.

## Deploy the evaluation service

For SQLite, use a container/Python host with HTTPS and a persistent disk. The Dockerfile binds port 8000. Run one replica/worker with a persistent `/data` volume. Alternatively, use `DATABASE_URL` for PostgreSQL as above; the score database then needs no local disk. Stateless hosting without either persistent storage option loses the leaderboard and team registry on restart.

Production startup, with the environment variables below loaded:

```sh
uvicorn server.app:create_app --factory --host 0.0.0.0 --port 8000 --workers 1
curl -f http://127.0.0.1:8000/api/health
```

For a public **sandbox**, set `DEMO_MODE=1`, `DATA_DIR=/data`, and `ALLOWED_ORIGINS=https://jhparktime.github.io`. Mount persistent storage. The demo key permits everyone to submit to the same sandbox team; do not use it for an official leaderboard.

For **official evaluation**:

```text
DEMO_MODE=0
REFERENCE_PATH=/data/private-references.json
DATA_DIR=/data
ALLOWED_ORIGINS=https://jhparktime.github.io
DAILY_LIMIT=5
SUBMISSIONS_OPEN=1
```

Upload the reference file privately to the evaluation host. The schema is:

```json
{
  "name": "evaluation-v1",
  "items": [
    {"id": "eval-001", "condition": "helpful_clean", "reference": "the actual human-verified transcript"}
  ]
}
```

Each reference must contain 1–500 normalized words. IDs must be unique. Each distinct `condition` string is a separately and equally weighted group. The proposed official groups are `helpful_clean`, `helpful_noisy`, `misleading_clean`, `misleading_noisy`, `irrelevant_clean`, and `irrelevant_noisy`; all six must be represented when that protocol is adopted. The server is generic and accepts any nonempty group labels, so organizers must validate the agreed group set before launch. The complete runnable toy manifest is `examples/demo-references.json`, with three groups and two rows each. Official IDs, audio and context lists must be released separately; only transcripts stay private. Any manifest change creates a new score namespace: the leaderboard and team history show only the new version and appear empty until new submissions arrive. Old rows remain in the database. Freeze the manifest once evaluation opens.

Create a key for each team on the evaluation host:

```sh
DATA_DIR=/data python -m scripts.create_team 'Team name'
```

The key is shown once; send it privately to the team. Only its hash is stored. There is no web registration or organizer dashboard yet. To close submissions, set `SUBMISSIONS_OPEN=0` and restart. Back up `/data`, enforce a request body limit at the HTTPS proxy (allow modest multipart overhead above 2 MiB), and rate-limit requests before public launch. The application rejects CSV payloads over 2 MiB; a proxy limit also bounds upload buffering before parsing.

## Submission and scoring contract

Canonical implementation: [`server/scoring.py`](server/scoring.py). UTF-8 CSV header: `id,prediction`. Predictions have a 500-word per-row limit and a 10-million total reference-word × hypothesis-word computation budget per request. Organizers must size the evaluation set accordingly. Predictions must cover exactly the reference IDs; duplicates, missing IDs and extra IDs are rejected. Empty predictions count as deletions.

`wer-macro-v1` normalizes with Unicode NFKC, case folding, punctuation-to-space, and whitespace tokenization. No stemming, number expansion or semantic equivalence. Apostrophes and hyphens split words. Compute Levenshtein word edits per utterance, pool edits/reference words within each condition, then average condition WERs equally. Values are percentages and may exceed 100%. Micro WER is secondary. Best macro WER per team wins; exact ties favor earlier submission. Scores are ranked at full precision and displayed to two decimals.

The default allowance is five accepted unique submissions per team per UTC day. Invalid submissions do not count. Resubmitting identical ID/prediction mappings returns the previous result without consuming an allowance, retaining its original timestamp even on later days. The server returns aggregate condition scores only, never references or per-utterance errors. Authentication is required for submission and private history; leaderboard scores and team names are public. Use team labels rather than personal data if desired.

API: `GET /api/health`, `GET /api/leaderboard`, authenticated `GET/POST /api/submissions`. Interactive schema: `/api/docs` on the scorer. Team authentication: `Authorization: Bearer TEAM_KEY`.

## Before an official challenge

- Select licensed source audio and document redistribution/access conditions.
- Verify transcripts against audio independently of the model being evaluated.
- Keep all variants of one original recording in the same split; separate speakers/source sessions where possible.
- Freeze the full condition matrix, external-data/pretraining rules, normalization and submission allowance before developing the final method.
- Treat public-source memorization as a limitation. Hiding a transcript behind an API does not remove training contamination. Use controlled model execution or independently collected holdout audio if stronger guarantees are needed.
- Have an independent reviewer audit the manifest and scorer. The included tests establish software correctness, not benchmark validity or model effectiveness.
- Add official audio/context downloads, registration/contact instructions and dates to the site. There is no claimed conference affiliation.

## Project layout

```text
web/                    GitHub Pages artifact only
server/                 authenticated API + deterministic scorer
scripts/create_team.py  organizer-only team provisioning
examples/               deliberately public toy reference
tests/                 metric and API integration tests
.github/workflows/      tests and Pages deployment
```
