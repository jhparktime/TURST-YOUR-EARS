"""Run from the project root: python -m scripts.create_team 'Team name'."""
import os
import secrets
import sys
import uuid
from pathlib import Path
from server.app import initialize, connect, token_hash

name = " ".join(sys.argv[1:]).strip()
if not name or len(name) > 60:
    raise SystemExit("Provide a team name of 1–60 characters.")
path = Path(os.getenv("DATA_DIR", "./private-data")) / "scores.sqlite3"
initialize(path)
token = secrets.token_urlsafe(32)
with connect(path) as db:
    db.execute("INSERT INTO teams VALUES (?, ?, ?)", (str(uuid.uuid4()), name, token_hash(token)))
print(f"Team created: {name}\nTeam key (store privately; shown once): {token}")
