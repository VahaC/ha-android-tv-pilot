"""Diagnostics (no key material; host, serial and MAC redacted)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import AndroidTVPilotConfigEntry
from .const import CONF_MAC, CONF_UNIQUE_SERIAL

TO_REDACT = {CONF_HOST, CONF_MAC, CONF_UNIQUE_SERIAL, "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AndroidTVPilotConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub = entry.runtime_data
    return {
        "entry": async_redact_data(
            {"data": dict(entry.data), "options": dict(entry.options), "unique_id": entry.unique_id},
            TO_REDACT,
        ),
        "power_state": hub.power_state,
        "wake_state": hub.wake.wake_state,
        "adb_connected": hub.adb_connected,
        "remote_connected": hub.remote_connected,
        "state": asdict(hub.state),
        "apps": [app.as_dict() for app in hub.apps],
    }
