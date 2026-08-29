import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "shortlists.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS shortlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    requirements_json TEXT NOT NULL,
    comparison_json TEXT NOT NULL
)
"""


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(CREATE_TABLE_SQL)
    return conn


def save_shortlist(thread_id, requirements, comparison):
    conn = _get_connection()
    with conn:
        conn.execute(
            "INSERT INTO shortlists (thread_id, created_at, requirements_json, comparison_json) VALUES (?, datetime('now'), ?, ?)",
            (thread_id, requirements.model_dump_json(), comparison.model_dump_json()),
        )
    conn.close()


def get_shortlists_by_thread(thread_id):
    conn = _get_connection()
    with conn:
        rows = conn.execute(
            "SELECT id, created_at, requirements_json, comparison_json FROM shortlists WHERE thread_id = ?",
            (thread_id,),
        ).fetchall()
    conn.close()
    return rows
