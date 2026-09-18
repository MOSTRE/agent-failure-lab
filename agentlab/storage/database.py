"""Minimal local metadata store (SQLite). Only run/diagnosis metadata — never session bodies."""
from __future__ import annotations

import sqlite3
from pathlib import Path


def db_path() -> Path:
    return Path.home() / ".agentlab" / "agentlab.db"


def connect(path: Path | None = None) -> sqlite3.Connection:
    p = path or db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS runs ("
        "id INTEGER PRIMARY KEY, benchmark TEXT, agent TEXT, verdict TEXT, "
        "duration_ms INTEGER, created_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS diagnoses ("
        "id INTEGER PRIMARY KEY, session TEXT, category TEXT, confidence REAL, "
        "critical_step INTEGER, created_at TEXT)"
    )
    return conn


def record_run(conn: sqlite3.Connection, benchmark: str, agent: str, verdict: str, duration_ms: int, created_at: str) -> None:
    conn.execute(
        "INSERT INTO runs (benchmark, agent, verdict, duration_ms, created_at) VALUES (?,?,?,?,?)",
        (benchmark, agent, verdict, duration_ms, created_at),
    )
    conn.commit()


def record_diagnosis(conn: sqlite3.Connection, session: str, category: str, confidence: float, critical_step: int, created_at: str) -> None:
    conn.execute(
        "INSERT INTO diagnoses (session, category, confidence, critical_step, created_at) VALUES (?,?,?,?,?)",
        (session, category, confidence, critical_step, created_at),
    )
    conn.commit()
