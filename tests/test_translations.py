"""strings.json, en.json and uk.json stay in sync; every raised key is translated."""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

PKG = Path(__file__).resolve().parents[1] / "custom_components" / "android_tv_pilot"


def _load(name: str) -> dict:
    return json.loads((PKG / name).read_text(encoding="utf-8"))


def _keys(data: object, prefix: str = "") -> set[str]:
    if isinstance(data, dict):
        out: set[str] = set()
        for key, value in data.items():
            out |= _keys(value, f"{prefix}.{key}" if prefix else key)
        return out
    return {prefix}


def _placeholders(data: object, prefix: str = "") -> dict[str, set[str]]:
    if isinstance(data, dict):
        out: dict[str, set[str]] = {}
        for key, value in data.items():
            out.update(_placeholders(value, f"{prefix}.{key}" if prefix else key))
        return out
    return {prefix: set(re.findall(r"\{(\w+)\}", str(data)))}


def test_en_matches_strings() -> None:
    assert _load("translations/en.json") == _load("strings.json")


def test_uk_has_same_keys_and_placeholders() -> None:
    strings, uk = _load("strings.json"), _load("translations/uk.json")
    assert _keys(uk) == _keys(strings)
    assert _placeholders(uk) == _placeholders(strings)


def test_every_raised_translation_key_exists() -> None:
    exceptions = set(_load("strings.json")["exceptions"])
    source = "\n".join(p.read_text(encoding="utf-8") for p in PKG.glob("*.py"))
    raised = set(re.findall(r"(?:Error|Exception)\(\s*\"([a-z_]+)\"", source))
    raised |= set(re.findall(r"translation_key=\"([a-z_]+)\"", source))
    raised -= {"key_action", "hidden_mode"}  # selector keys
    assert raised, "pattern found nothing"
    assert raised <= exceptions, raised - exceptions


def test_services_yaml_matches_strings() -> None:
    services = set(_load("strings.json")["services"])
    yaml_text = (PKG / "services.yaml").read_text(encoding="utf-8")
    declared = set(re.findall(r"^([a-z_]+):\s*$", yaml_text, re.MULTILINE))
    assert declared == services
    assert set(_load("icons.json")["services"]) == services


def test_no_urls_inside_translation_strings() -> None:
    """hassfest rejects URLs in strings; links go through description_placeholders."""
    for name in ("strings.json", "translations/en.json", "translations/uk.json"):
        text = (PKG / name).read_text(encoding="utf-8")
        assert "http://" not in text and "https://" not in text, name


def test_wake_descriptions_use_link_placeholders() -> None:
    for name in ("strings.json", "translations/uk.json"):
        data = _load(name)
        for desc in (
            data["config"]["step"]["wake"]["description"],
            data["options"]["step"]["settings"]["description"],
        ):
            assert "{guide_url}" in desc and "{firmware_url}" in desc, name


def test_services_yaml_has_no_device_target_filters() -> None:
    """hassfest: "Services do not support device filters on target"."""
    yaml = pytest.importorskip("yaml")
    services = yaml.safe_load((PKG / "services.yaml").read_text(encoding="utf-8"))
    for name, spec in services.items():
        assert "device" not in spec["target"], name
        assert spec["target"]["entity"] == {"integration": "android_tv_pilot"}, name


def test_manifest_requirements_are_minimums() -> None:
    """hassfest: packages Home Assistant also depends on must not be pinned with ==."""
    manifest = _load("manifest.json")
    assert manifest["requirements"] == ["adb-shell[async]>=0.4.4", "androidtvremote2>=0.3.3"]
