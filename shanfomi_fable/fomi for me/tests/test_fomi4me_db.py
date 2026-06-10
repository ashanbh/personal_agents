from datetime import datetime
from zoneinfo import ZoneInfo

import fomi4me_db


def today():
    return datetime.now(ZoneInfo(fomi4me_db.DEFAULT_TZ)).date()


def test_daily_summary_aggregates(fake_db):
    s = fomi4me_db.daily_summary(today())
    assert s["focused_minutes"] == 120.0          # 1440 ticks * 5s
    assert s["nonwork_minutes"] == 45.0           # 30m instagram + 15m private
    assert s["sessions_total"] == 1
    assert s["best_session_minutes"] == 120.0


def test_drift_counted(fake_db):
    assert fomi4me_db.drift_events(today()) >= 1  # work -> instagram


def test_top_nonwork_classes_are_coarse(fake_db):
    classes = fomi4me_db.top_nonwork_classes(today())
    assert "social video" in classes              # instagram.com mapped
    for c in classes:
        assert ".com" not in c and "instagram" not in c.lower()


def test_private_rows_never_expose_identifiers(fake_db):
    # The private 15 minutes contribute to totals but never to classes.
    s = fomi4me_db.daily_summary(today())
    assert s["nonwork_minutes"] == 45.0
    flat = str(s)
    assert "private" not in flat or "private-" not in flat.replace(
        "private-work", "").replace("private-nonwork", "")
    # Stronger: classes list must not contain any private marker.
    assert all("private" not in c for c in s["top_nonwork_classes"])
