"""
deps.py

Shared FastAPI dependencies.

sqlite3 connections aren't safe to share across threads, and FastAPI runs
sync route handlers in a thread pool -- so rather than one long-lived
connection, get_db() opens a fresh one for the lifetime of a single
request and closes it afterwards. The DB is small and local, so the
per-request connect/close cost is negligible.
"""

import os
from pathlib import Path

from config import OUTPUT_DB
from database import Database

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# JOBS_DB_PATH lets a test harness (or anyone else) point a *subprocess*
# uvicorn at a different DB file without editing code -- unlike the
# in-process TestClient tests (tests/webapp_api/), which just monkeypatch
# this module's DB_PATH directly, E2E tests start the backend as a real
# separate process and have no Python object to monkeypatch.
DB_PATH = os.environ.get("JOBS_DB_PATH") or str(PROJECT_ROOT / OUTPUT_DB)


def get_db():
    db = Database(DB_PATH)
    try:
        yield db
    finally:
        db.close()
