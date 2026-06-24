from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import digest_builder
import fomi4me_db


def today():
    return datetime.now(ZoneInfo(fomi4me_db.DEFAULT_TZ)).date()


def test_digest_contains_only_aggregates(fake_db):
    summary = fomi4me_db.daily_summary(today())
    subject, plain, html = digest_builder.build(summary)
    for text in (subject, plain, html):
        low = text.lower()
        assert "instagram" not in low
        assert "vscode" not in low and "safari" not in low
        assert "http" not in low
        assert "private-" not in low
    assert "2h 00m" in plain  # focused time present


def test_sanitizer_catches_domains():
    with pytest.raises(ValueError):
        digest_builder.assert_sanitized("watched instagram.com all day")
    with pytest.raises(ValueError):
        digest_builder.assert_sanitized("see https://example.org/x")
    with pytest.raises(ValueError):
        digest_builder.assert_sanitized("category private-nonwork leaked")


def test_sanitizer_passes_real_digest(fake_db):
    summary = fomi4me_db.daily_summary(today())
    subject, plain, _ = digest_builder.build(summary)
    digest_builder.assert_sanitized(subject, plain)  # must not raise


def test_review_mode_default_on(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DIGEST_REVIEW_MODE", raising=False)
    cfg = digest_builder.config()
    assert cfg["review_mode"] is True
