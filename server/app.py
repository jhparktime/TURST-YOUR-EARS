import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .scoring import VERSION, parse_submission, score, validate_references
from .database import connect, initialize

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 2 * 1024 * 1024


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_app(data_dir=None, reference_path=None, demo=None):
    demo = (os.getenv("DEMO_MODE", "0") == "1") if demo is None else demo
    data_dir = Path(data_dir or os.getenv("DATA_DIR", "./private-data"))
    reference_path = reference_path or os.getenv("REFERENCE_PATH")
    if not reference_path and not demo:
        raise RuntimeError("Set REFERENCE_PATH to private reference JSON, or use DEMO_MODE=1 for the toy sandbox.")
    ref_path = Path(reference_path) if reference_path else ROOT / "examples/demo-references.json"
    manifest = json.loads(ref_path.read_text())
    refs = manifest["items"]
    try:
        validate_references(refs)
        if "conditions" in manifest and set(manifest["conditions"]) != {r['condition'] for r in refs}:
            raise ValueError('Declared conditions must match the manifest rows.')
        if all(r.get('context', r['condition']) == 'no_context' for r in refs):
            raise ValueError('At least one contextual condition is required.')
        for condition in {r['condition'] for r in refs}:
            if len({r.get('context', r['condition']) for r in refs if r['condition'] == condition}) != 1:
                raise ValueError('A condition cannot mix context types.')
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    # Content hash prevents ranking scores produced by different reference versions together.
    reference_version = hashlib.sha256(ref_path.read_bytes()).hexdigest()
    dataset = ("sandbox:" if demo else "evaluation:") + VERSION + ':' + reference_version
    db_path = data_dir / "scores.sqlite3"
    initialize(db_path)
    if demo:
        with connect(db_path) as db:
            db.execute("INSERT INTO teams VALUES (?, ?, ?) ON CONFLICT DO NOTHING", ("demo", "Sandbox team", token_hash("demo-team-key")))
    lock = threading.Lock()
    daily_limit = int(os.getenv("DAILY_LIMIT", "5"))

    app = FastAPI(title="Trust Your Ears evaluation", docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
    origins = [v.strip() for v in os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",") if v.strip()]
    if "*" in origins:
        raise RuntimeError("ALLOWED_ORIGINS must contain exact frontend origins.")
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                       allow_headers=["Authorization", "Content-Type"])

    def authenticate(authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Enter the team key issued by the organizers.")
        with connect(db_path) as db:
            row = db.execute("SELECT id, name FROM teams WHERE key_hash=?", (token_hash(authorization[7:]),)).fetchone()
        if row is None or (not demo and row["id"] == "demo"):
            raise HTTPException(401, "Invalid team key.")
        return row

    @app.get("/api/health")
    def health():
        return {"mode": "sandbox" if demo else "evaluation", "dataset": manifest["name"],
                "dataset_version": reference_version[:12], "scorer": VERSION, "primary_metric": "macro_cer",
                "daily_limit": daily_limit, "samples": len(refs),
                "submission_open": os.getenv("SUBMISSIONS_OPEN", "1") == "1"}

    @app.get("/api/leaderboard")
    def leaderboard():
        with connect(db_path) as db:
            rows = db.execute("SELECT s.*, t.name FROM submissions s JOIN teams t ON s.team_id=t.id WHERE dataset=? ORDER BY created ASC", (dataset,)).fetchall()
        best = {}
        for row in rows:
            result = json.loads(row["result"])
            item = {"team": row["name"], "created": row["created"], "submission_id": row["id"], **result}
            if row["team_id"] not in best or result["macro_cer"] < best[row["team_id"]]["macro_cer"]:
                best[row["team_id"]] = item
        entries = sorted(best.values(), key=lambda r: (r["macro_cer"], r["created"]))
        rank, previous = 0, None
        for position, entry in enumerate(entries, 1):
            if entry['macro_cer'] != previous:
                rank = position
            entry['rank'] = rank
            previous = entry['macro_cer']
        return {"mode": "sandbox" if demo else "evaluation", "entries": entries}

    @app.get("/api/submissions")
    def history(authorization: str | None = Header(default=None)):
        team = authenticate(authorization)
        with connect(db_path) as db:
            rows = db.execute("SELECT id, created, result FROM submissions WHERE team_id=? AND dataset=? ORDER BY created DESC LIMIT 50", (team["id"], dataset)).fetchall()
        return {"team": team["name"], "entries": [{"id": r["id"], "created": r["created"], **json.loads(r["result"])} for r in rows]}

    @app.post("/api/submissions")
    def submit(file: UploadFile = File(...), authorization: str | None = Header(default=None)):
        team = authenticate(authorization)
        if os.getenv("SUBMISSIONS_OPEN", "1") != "1":
            raise HTTPException(403, "Submissions are closed.")
        body = file.file.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise HTTPException(413, "Maximum submission size is 2 MiB.")
        try:
            predictions = parse_submission(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        canonical = json.dumps(predictions, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        # Serialize admission and scoring to avoid quota races and bound CPU concurrency.
        with lock, connect(db_path) as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT id, created, result FROM submissions WHERE team_id=? AND dataset=? AND digest=?", (team["id"], dataset, digest)).fetchone()
            if prior:
                return {"id": prior["id"], "created": prior["created"], "reused": True, **json.loads(prior["result"])}
            used = db.execute("SELECT count(*) AS used FROM submissions WHERE team_id=? AND dataset=? AND created>=?", (team["id"], dataset, now[:10])).fetchone()["used"]
            if used >= daily_limit:
                raise HTTPException(429, "Daily submission limit reached. It resets at 00:00 UTC.")
            try:
                result = score(predictions, refs)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            identifier = str(uuid.uuid4())
            db.execute("INSERT INTO submissions VALUES (?, ?, ?, ?, ?, ?)", (identifier, team["id"], dataset, now, digest, json.dumps(result)))
        return {"id": identifier, "created": now, "reused": False, **result}

    # Only web/ is public. Private references and database are never mounted.
    app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="site")
    return app
