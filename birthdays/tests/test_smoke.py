"""Smoke tests for the birthdays agent after the canonical-layout migration.

These are import/logic checks that need no network and no private data — they
just confirm the core modules load from src/ and their pure helpers behave.
Run from the agent root:  python3 -m pytest tests/ -q   (or: python3 tests/test_smoke.py)
"""
import importlib.util
import os

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")


def _load(modname):
    path = os.path.join(SRC, f"{modname}.py")
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_modules_import():
    for m in ("preprocess", "sync_birthdays", "send_birthday_messages", "postprocess"):
        assert _load(m) is not None


def test_method_normalization():
    pre = _load("preprocess")
    assert pre.clean_method("imessage") == "iMessage"
    assert pre.clean_method('"WhatsApp"') == "WhatsApp"
    assert pre.clean_method("Family is Fortune") == "Family is Fortune"


def test_sync_phone_digits():
    sync = _load("sync_birthdays")
    assert sync.digits("+1 (925) 219-5955") == "19252195955"


if __name__ == "__main__":
    test_modules_import()
    test_method_normalization()
    test_sync_phone_digits()
    print("OK: all birthdays smoke tests passed")
