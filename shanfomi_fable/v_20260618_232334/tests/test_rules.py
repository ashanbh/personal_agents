import json
from pathlib import Path

import pytest

RULES = Path(__file__).resolve().parent.parent / "app" / "Sources" / "FomiCore" / "Rules"
PERSONAS = ["engineer", "accountant", "doctor"]

REQUIRED_KEYS = {
    "persona", "workBundlePrefixes", "nonworkBundlePrefixes",
    "workDomainSuffixes", "nonworkDomainSuffixes",
    "workAppSubstrings", "nonworkAppSubstrings", "meetingBundlePrefixes",
}


@pytest.mark.parametrize("persona", PERSONAS)
def test_pack_schema(persona):
    pack = json.loads((RULES / f"{persona}.json").read_text())
    assert REQUIRED_KEYS.issubset(pack.keys())
    assert pack["persona"] == persona
    # No overlap between work and nonwork lists.
    for kind in ("BundlePrefixes", "DomainSuffixes", "AppSubstrings"):
        overlap = set(pack[f"work{kind}"]) & set(pack[f"nonwork{kind}"])
        assert not overlap, f"{persona}: {kind} overlap {overlap}"


def test_sensitive_schema():
    s = json.loads((RULES / "sensitive.json").read_text())
    assert {"privateDomainSuffixes", "privateBundlePrefixes",
            "privateAppSubstrings"}.issubset(s.keys())
    assert len(s["privateDomainSuffixes"]) > 0


def test_doctor_ehr_is_metadata_only():
    pack = json.loads((RULES / "doctor.json").read_text())
    assert pack.get("metadataOnlyBundlePrefixes"), "doctor persona must protect EHR"
    for prefix in pack["metadataOnlyBundlePrefixes"]:
        assert prefix in pack["workBundlePrefixes"]


def test_meetings_are_work_everywhere():
    for persona in PERSONAS:
        pack = json.loads((RULES / f"{persona}.json").read_text())
        assert any("zoom" in b for b in pack["meetingBundlePrefixes"])
