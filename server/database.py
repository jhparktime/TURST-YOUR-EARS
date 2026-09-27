"""SQLite locally; private Postgres schema for free persistent hosted storage."""
import os
import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path):
        self.postgres = bool(os.getenv("DATABASE_URL"))
        if self.postgres:
            import psycopg
            from psycopg.rows import dict_row
            self.raw = psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row,
                                       connect_timeout=15, prepare_threshold=None)
            self.raw.execute("SET search_path TO tye_private")
            self.raw.commit()
        else:
            self.raw = sqlite3.connect(path, timeout=20)
            self.raw.row_factory = sqlite3.Row

    def execute(self, query, parameters=()):
        if self.postgres:
            if query == "BEGIN IMMEDIATE":
                # Serialize quota admission across workers, not just within a process.
                return self.raw.execute("SELECT pg_advisory_xact_lock(82713491)")
            query = query.replace("?", "%s")
        return self.raw.execute(query, parameters)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self.raw.commit()
            else:
                self.raw.rollback()
        finally:
            self.raw.close()


def connect(path):
    return Database(path)


def initialize(path):
    if not os.getenv("DATABASE_URL"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        if db.postgres:
            db.execute("CREATE SCHEMA IF NOT EXISTS tye_private")
        db.execute("CREATE TABLE IF NOT EXISTS teams (id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, key_hash TEXT UNIQUE NOT NULL)")
        db.execute("""CREATE TABLE IF NOT EXISTS submissions (
            id TEXT PRIMARY KEY, team_id TEXT NOT NULL, dataset TEXT NOT NULL,
            created TEXT NOT NULL, digest TEXT NOT NULL, result TEXT NOT NULL,
            UNIQUE(team_id, dataset, digest))""")
        db.execute("CREATE INDEX IF NOT EXISTS submission_lookup ON submissions (dataset, team_id, created)")
        if db.postgres:
            # Keep these outside Supabase's public API schemas. No anon/authenticated access.
            db.execute("REVOKE ALL ON SCHEMA tye_private FROM PUBLIC")
            db.execute("REVOKE ALL ON ALL TABLES IN SCHEMA tye_private FROM PUBLIC")
