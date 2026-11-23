"""Lovelace resource registration, including the update path ``?v=<old>`` -> ``?v=<new>``."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.core import HomeAssistant

from custom_components.android_tv_pilot import frontend_registration as fr

from .test_init import MP, _fake_transports, _setup, _unload  # noqa: F401 - autouse fixture

MANIFEST = Path(fr.__file__).parent / "manifest.json"
VERSION = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
BASE = "/android_tv_pilot_static/android-tv-pilot-card.js"


class FakeResources:
    """Stands in for lovelace's ResourceStorageCollection."""

    def __init__(self, items: list[dict]) -> None:
        self.items = [dict(i) for i in items]
        self.created: list[dict] = []
        self.updated: list[tuple[str, dict]] = []

    async def async_get_info(self) -> dict:
        return {"resources": len(self.items)}

    def async_items(self) -> list[dict]:
        return self.items

    async def async_create_item(self, data: dict) -> dict:
        item = {"id": f"new{len(self.items)}", "type": data["res_type"], "url": data["url"]}
        self.items.append(item)
        self.created.append(data)
        return item

    async def async_update_item(self, item_id: str, updates: dict) -> dict:
        self.updated.append((item_id, updates))
        for item in self.items:
            if item["id"] == item_id:
                item["url"] = updates["url"]
        return {}


def _install(hass: HomeAssistant, resources: FakeResources, mode: str = "storage") -> None:
    hass.data["lovelace"] = SimpleNamespace(resource_mode=mode, resources=resources)


async def test_old_version_is_updated(hass: HomeAssistant) -> None:
    resources = FakeResources(
        [
            {"id": "other", "type": "module", "url": "/local/community/other-card.js?v=3"},
            {"id": "ours", "type": "module", "url": f"{BASE}?v=0.0.9"},
        ]
    )
    _install(hass, resources)
    url = f"{BASE}?v={VERSION}"
    await fr._async_register_resource(hass, url)
    assert resources.updated == [("ours", {"res_type": "module", "url": url})]
    assert resources.created == []
    assert resources.items[0]["url"] == "/local/community/other-card.js?v=3"  # untouched


async def test_same_version_is_left_alone(hass: HomeAssistant) -> None:
    url = f"{BASE}?v={VERSION}"
    resources = FakeResources([{"id": "ours", "type": "module", "url": url}])
    _install(hass, resources)
    await fr._async_register_resource(hass, url)
    assert resources.updated == []
    assert resources.created == []


async def test_missing_resource_is_created(hass: HomeAssistant) -> None:
    resources = FakeResources([])
    _install(hass, resources)
    url = f"{BASE}?v={VERSION}"
    await fr._async_register_resource(hass, url)
    assert resources.created == [{"res_type": "module", "url": url}]


async def test_yaml_mode_falls_back_to_extra_js_url(hass: HomeAssistant) -> None:
    resources = FakeResources([])
    _install(hass, resources, mode="yaml")
    with patch.object(fr, "add_extra_js_url") as extra:
        await fr._async_register_resource(hass, f"{BASE}?v={VERSION}")
    extra.assert_called_once_with(hass, f"{BASE}?v={VERSION}")
    assert resources.created == []


async def test_integration_version_attribute_matches_resource_version(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    attrs = hass.states.get(MP).attributes
    assert attrs["integration_version"] == VERSION
    assert await fr.async_integration_version(hass) == VERSION
    await _unload(hass, entry)


async def test_integration_version_is_not_reread_from_disk(hass: HomeAssistant) -> None:
    """After an update on disk without a restart, the running version is still reported."""
    assert await fr.async_integration_version(hass) == VERSION
    with patch.object(fr, "async_get_integration", side_effect=AssertionError("re-read")):
        assert await fr.async_integration_version(hass) == VERSION
