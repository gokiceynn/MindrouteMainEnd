import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent.parent / "database" / "mood.db"


def get_sqlite():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


