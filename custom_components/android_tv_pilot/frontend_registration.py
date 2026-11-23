"""Serve the card and make Lovelace load it automatically.

- Static files: ``custom_components/android_tv_pilot/frontend/`` at ``/android_tv_pilot_static``
  (``hass.http.async_register_static_paths`` + ``StaticPathConfig``).
- Lovelace in storage mode: create or update a ``module`` resource
  ``/android_tv_pilot_static/android-tv-pilot-card.js?v=<version>``.
- Otherwise (YAML resources or Lovelace not loaded): ``frontend.add_extra_js_url``.

Lovelace data is read as ``hass.data["lovelace"]``: a ``LovelaceData`` dataclass with
``resource_mode`` / ``resources`` on current Home Assistant, ``mode`` on 2024.x/2025.x
releases, and a plain dict on older ones.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant
from homeassistant.loader import async_get_integration

from .const import CARD_FILENAME, DOMAIN, STATIC_URL_PATH

_LOGGER = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend"
_REGISTERED = f"{DOMAIN}_frontend_registered"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register the static path and the Lovelace resource. Never raises."""
    if hass.data.get(_REGISTERED):
        return
    hass.data[_REGISTERED] = True
    try:
        integration = await async_get_integration(hass, DOMAIN)
        version = str(integration.version or "0")
        card_exists = await hass.async_add_executor_job((FRONTEND_DIR / CARD_FILENAME).is_file)
        if not card_exists:
            _LOGGER.warning(
                "Card file %s is missing; the dashboard card will not load"
                " (the integration itself works). Reinstall the integration from HACS",
                FRONTEND_DIR / CARD_FILENAME,
            )
            return
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL_PATH, str(FRONTEND_DIR), False)]
        )
        url = f"{STATIC_URL_PATH}/{CARD_FILENAME}?v={version}"

        if hass.state is CoreState.running:
            await _async_register_resource(hass, url)
        else:

            async def _on_started(_: Event) -> None:
                await _async_register_resource(hass, url)

            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)
    except Exception:
        _LOGGER.warning("Could not register the Android TV Pilot card", exc_info=True)


def _lovelace_resources(hass: HomeAssistant) -> tuple[str | None, Any]:
    """Return (resource mode, resources collection) across HA versions."""
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        return None, None
    if isinstance(lovelace, dict):
        return lovelace.get("mode"), lovelace.get("resources")
    mode = getattr(lovelace, "resource_mode", None) or getattr(lovelace, "mode", None)
    return mode, getattr(lovelace, "resources", None)


async def _async_register_resource(hass: HomeAssistant, url: str) -> None:
    try:
        mode, resources = _lovelace_resources(hass)
        if mode == "storage" and resources is not None and hasattr(resources, "async_create_item"):
            await resources.async_get_info()  # ensures the collection is loaded
            base = url.split("?", 1)[0]
            for item in resources.async_items():
                item_url = str(item.get("url", ""))
                if item_url.split("?", 1)[0] != base:
                    continue
                if item_url != url:
                    await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
                    _LOGGER.debug("Updated Lovelace resource to %s", url)
                return
            await resources.async_create_item({"res_type": "module", "url": url})
            _LOGGER.debug("Added Lovelace resource %s", url)
            return
    except Exception:
        _LOGGER.debug("Lovelace resource registration failed; using extra JS URL", exc_info=True)
    add_extra_js_url(hass, url)
