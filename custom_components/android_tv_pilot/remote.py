"""Remote entity."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_DELAY_SECS,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_HOLD_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteEntity,
    RemoteEntityFeature,
)
from homeassistant.core import HomeAssistant

from . import AndroidTVPilotConfigEntry
from .const import POWER_ON
from .entity import AddEntitiesCallback, AndroidTVPilotEntity
from .hub import AndroidTVPilotHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AndroidTVPilotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the remote."""
    async_add_entities([AndroidTVPilotRemote(entry.runtime_data)])


class AndroidTVPilotRemote(AndroidTVPilotEntity, RemoteEntity):
    """Android TV remote."""

    _attr_supported_features = RemoteEntityFeature.ACTIVITY

    def __init__(self, hub: AndroidTVPilotHub) -> None:
        """Initialize."""
        super().__init__(hub)
        self._attr_unique_id = f"{hub.entry.unique_id or hub.entry.entry_id}_remote"

    @property
    def is_on(self) -> bool:
        """On when the screen is on."""
        return self.hub.power_state == POWER_ON

    @property
    def activity_list(self) -> list[str]:
        """Visible app labels."""
        return [app.label for app in self.hub.apps if not app.hidden]

    @property
    def current_activity(self) -> str | None:
        """Current app label."""
        if not self.is_on:
            return None
        return self.hub.app_label(self.hub.state.app_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on; with ``activity`` launch that app afterwards."""
        await self.hub.async_turn_on()
        if activity := kwargs.get(ATTR_ACTIVITY):
            await self.hub.async_select_source(activity)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.hub.async_turn_off()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send keys from the vocabulary (``hold_secs`` > 0 means long press)."""
        num_repeats = int(kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS))
        delay = float(kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS))
        hold = float(kwargs.get(ATTR_HOLD_SECS, DEFAULT_HOLD_SECS) or 0)
        commands = list(command)
        for repeat in range(num_repeats):
            for index, cmd in enumerate(commands):
                if hold > 0:
                    await self.hub.async_send_key(cmd, "long", hold_secs=hold)
                else:
                    await self.hub.async_send_key(cmd, "press")
                last = repeat == num_repeats - 1 and index == len(commands) - 1
                if delay and not last:
                    await asyncio.sleep(delay)
