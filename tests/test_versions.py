"""Release guard: every place that carries the version must agree (no Home Assistant needed)."""

from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "android_tv_pilot" / "manifest.json"
PACKAGE_JSON = ROOT / "card" / "package.json"
CARD_SOURCE = ROOT / "card" / "src" / "android-tv-pilot-card.ts"
BUNDLE = ROOT / "custom_components" / "android_tv_pilot" / "frontend" / "android-tv-pilot-card.js"


def _manifest_version() -> str:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]


def test_card_package_version_matches_manifest() -> None:
    assert json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["version"] == _manifest_version()


def test_card_source_version_matches_manifest() -> None:
    match = re.search(r'export const CARD_VERSION\s*=\s*"([^"]+)"', CARD_SOURCE.read_text(encoding="utf-8"))
    assert match, "CARD_VERSION not found in the card source"
    assert match.group(1) == _manifest_version()


def test_built_bundle_contains_the_version() -> None:
    """A stale bundle (built before the version bump) fails here."""
    bundle = BUNDLE.read_text(encoding="utf-8")
    version = _manifest_version()
    assert f'"{version}"' in bundle or f"'{version}'" in bundle, (
        f"{BUNDLE.name} does not contain version {version}; run 'npm run build' in card/"
    )
