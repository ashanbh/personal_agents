"""Tests for the activity log-line writer (M0 step 2).

These pin the exact output contract the downstream coach depends on:

    running=yes|no|unknown [| focused=yes|no] | note=...
"""

from __future__ import annotations

import pytest

from app.backends import Decision
from app.logwriter import format_line, write_line


def test_format_running_only_omits_focused():
    line = format_line(Decision(running="yes", note="vscode active"))
    assert line == "running=yes | note=vscode active"


def test_format_with_focused():
    line = format_line(Decision(running="yes", focused="no", note="youtube"))
    assert line == "running=yes | focused=no | note=youtube"


def test_format_unknown_empty_note():
    line = format_line(Decision())
    assert line == "running=unknown | note="


@pytest.mark.parametrize("running", ["yes", "no", "unknown"])
def test_all_valid_running_values(running):
    assert format_line(Decision(running=running)).startswith(f"running={running} ")


def test_field_order_is_fixed():
    line = format_line(Decision(running="no", focused="yes", note="idle"))
    assert line.index("running=") < line.index("focused=") < line.index("note=")


def test_note_newlines_collapsed_to_single_line():
    line = format_line(Decision(running="yes", note="line1\nline2\r\nline3"))
    assert "\n" not in line and "\r" not in line
    assert line == "running=yes | note=line1 line2  line3"


def test_invalid_running_rejected():
    with pytest.raises(ValueError):
        format_line(Decision(running="maybe"))


def test_invalid_focused_rejected():
    with pytest.raises(ValueError):
        format_line(Decision(running="yes", focused="sometimes"))


def test_write_line_appends_and_creates_dir(tmp_path):
    log = tmp_path / "nested" / "activity.log"
    written = write_line(Decision(running="yes", note="a"), log)
    assert written == "running=yes | note=a"

    write_line(Decision(running="no", focused="yes", note="b"), log)

    contents = log.read_text(encoding="utf-8")
    assert contents == "running=yes | note=a\nrunning=no | focused=yes | note=b\n"


def test_write_line_returns_line_without_newline(tmp_path):
    log = tmp_path / "activity.log"
    written = write_line(Decision(running="unknown"), log)
    assert written == "running=unknown | note="
    assert not written.endswith("\n")
