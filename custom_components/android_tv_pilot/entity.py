"""Base entity."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import Entity

try:
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback as AddEntitiesCallback,
    )
except ImportError:  # Home Assistant < 2025.3
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MAC, CONF_MANUFACTURER, CONF_MODEL, CONF_SW_VERSION, DOMAIN
from .hub import AndroidTVPilotHub

__all__ = ["AddEntitiesCallback", "AndroidTVPilotEntity"]


class AndroidTVPilotEntity(Entity):
    """Common device info and hub subscription.

    Entities stay available while the TV sleeps so that ``turn_on`` stays callable;
    the state is ``off`` instead.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = None

    def __init__(self, hub: AndroidTVPilotHub) -> None:
        """Initialize."""
        self.hub = hub
        entry = hub.entry
        data = entry.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            connections={(CONNECTION_NETWORK_MAC, data[CONF_MAC])} if data.get(CONF_MAC) else set(),
            name=entry.title,
            manufacturer=data.get(CONF_MANUFACTURER),
            model=data.get(CONF_MODEL),
            sw_version=data.get(CONF_SW_VERSION),
            configuration_url=None,
        )
        self._host = data[CONF_HOST]

    async def async_added_to_hass(self) -> None:
        """Subscribe to hub updates."""
        self.async_on_remove(self.hub.async_add_listener(self.async_write_ha_state))
