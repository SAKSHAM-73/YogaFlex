"""
Session Store — SQLite Persistence
=====================================
Saves per-session pose data so the difficulty adapter
can cluster historical performance across sessions.

Schema
------
sessions  : one row per yoga session
pose_logs : one row per pose attempt within a session
"""

import sqlite3
import json
import time
import os
from pathlib import Path
from typing import Optional

# DB lives at project root (next to api/ and logic/)
_DB_PATH = Path(__file__).parent.parent / "yogaflex.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist. Call once at app startup."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id   TEXT    NOT NULL,
                started_at  REAL    NOT NULL,
                ended_at    REAL,
                duration_sec REAL
            );

            CREATE TABLE IF NOT EXISTS pose_logs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      INTEGER NOT NULL REFERENCES sessions(id),
                pose_name       TEXT    NOT NULL,
                avg_similarity  REAL    NOT NULL,
                peak_similarity REAL    NOT NULL,
                reps            INTEGER NOT NULL DEFAULT 0,
                hold_sec        REAL    NOT NULL DEFAULT 0,
                joint_scores    TEXT,           -- JSON blob
                logged_at       REAL    NOT NULL
            );
        """)


# ── Session lifecycle ──────────────────────────────────────────────────────────

def start_session(client_id: str) -> int:
    """Open a new session row. Returns session_id."""
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (client_id, started_at) VALUES (?, ?)",
            (client_id, time.time())
        )
        return cur.lastrowid


def end_session(session_id: int):
    """Close an open session row."""
    now = time.time()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT started_at FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row:
            duration = now - row["started_at"]
            conn.execute(
                "UPDATE sessions SET ended_at=?, duration_sec=? WHERE id=?",
                (now, round(duration, 1), session_id)
            )


# ── Pose logging ───────────────────────────────────────────────────────────────

def log_pose_attempt(
    session_id:      int,
    pose_name:       str,
    avg_similarity:  float,
    peak_similarity: float,
    reps:            int   = 0,
    hold_sec:        float = 0.0,
    joint_scores:    Optional[dict] = None,
):
    """Append one pose attempt to the log."""
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO pose_logs
               (session_id, pose_name, avg_similarity, peak_similarity,
                reps, hold_sec, joint_scores, logged_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                session_id,
                pose_name,
                round(avg_similarity,  4),
                round(peak_similarity, 4),
                reps,
                round(hold_sec, 1),
                json.dumps(joint_scores) if joint_scores else None,
                time.time(),
            )
        )


# ── Query helpers ──────────────────────────────────────────────────────────────

def get_all_pose_logs(limit: int = 500) -> list[dict]:
    """Return recent pose logs for clustering."""
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT pose_name, avg_similarity, peak_similarity, reps, hold_sec
               FROM pose_logs ORDER BY logged_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_session_summary(session_id: int) -> dict:
    """Aggregate stats for one session."""
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT pose_name,
                      AVG(avg_similarity)  AS avg_sim,
                      MAX(peak_similarity) AS best_sim,
                      SUM(reps)            AS total_reps,
                      SUM(hold_sec)        AS total_hold
               FROM pose_logs
               WHERE session_id = ?
               GROUP BY pose_name""",
            (session_id,)
        ).fetchall()

        session_row = conn.execute(
            "SELECT duration_sec FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()

        return {
            "session_id":   session_id,
            "duration_sec": session_row["duration_sec"] if session_row else None,
            "poses": [dict(r) for r in rows],
        }
