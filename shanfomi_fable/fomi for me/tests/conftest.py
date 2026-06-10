import sqlite3
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

SCHEMA = """
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL, bundle_id TEXT, app_name TEXT, domain TEXT,
    category TEXT NOT NULL, confidence REAL NOT NULL, tier INTEGER NOT NULL
);
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_ts REAL NOT NULL, end_ts REAL NOT NULL,
    work_s INTEGER NOT NULL, nonwork_s INTEGER NOT NULL, close_reason TEXT NOT NULL
);
"""


@pytest.fixture
def fake_db(tmp_path, monkeypatch):
    """Create a synthetic FomiForMe DB for 'today' and point FOMI4ME_DB at it."""
    db = tmp_path / "fomi4me.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)

    # Anchor at *noon today* in the reader's timezone so the synthetic day never
    # straddles midnight regardless of when the tests run.
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/Los_Angeles")
    today = datetime.now(tz).date()
    noon = datetime(today.year, today.month, today.day, 12, 0, tzinfo=tz).timestamp()

    rows = []
    # 2h of work in VS Code (1440 ticks @5s), 8:00–10:00
    t = noon - 4 * 3600
    for i in range(1440):
        rows.append((t + i * 5, "com.microsoft.VSCode", "Code", None, "work", 0.9, 0))
    # 30 min of instagram (360 ticks), 10:30–11:00
    t = noon - 1.5 * 3600
    for i in range(360):
        rows.append((t + i * 5, "com.apple.Safari", "Safari", "instagram.com",
                     "nonwork", 0.9, 0))
    # 15 min private-nonwork — identifiers MUST be NULL (sanitized upstream)
    t = noon - 0.9 * 3600
    for i in range(180):
        rows.append((t + i * 5, None, None, None, "private-nonwork", 0.9, 0))
    now = noon  # session row below uses the same anchor
    conn.executemany(
        "INSERT INTO events (ts,bundle_id,app_name,domain,category,confidence,tier) "
        "VALUES (?,?,?,?,?,?,?)", rows)
    conn.execute(
        "INSERT INTO sessions (start_ts,end_ts,work_s,nonwork_s,close_reason) "
        "VALUES (?,?,?,?,?)", (now - 4 * 3600, now - 2 * 3600, 7200, 0, "nonwork"))
    conn.commit()
    conn.close()

    monkeypatch.setenv("FOMI4ME_DB", str(db))
    return db
