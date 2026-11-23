"""Media player entity (the card's ``entity``)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.event import async_track_state_change_event

from . import AndroidTVPilotConfigEntry
from .const import (
    ATTR_ADB_CONNECTED,
    ATTR_APP_ACTIVITY,
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_ENTRY_ID,
    ATTR_HAS_WAKE_BUTTON,
    ATTR_INTEGRATION_VERSION,
    ATTR_POWER_STATE,
    ATTR_REMOTE_CONNECTED,
    ATTR_VOLUME_ENTITY,
    ATTR_WAKE_STARTED_AT,
    ATTR_WAKE_STATE,
    ATTR_WAKE_TIMEOUT,
    DOMAIN,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_URL,
    POWER_ON,
)
from .entity import AddEntitiesCallback, AndroidTVPilotEntity

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY_MEDIA
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AndroidTVPilotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the media player."""
    async_add_entities([AndroidTVPilotMediaPlayer(entry.runtime_data)])


class AndroidTVPilotMediaPlayer(AndroidTVPilotEntity, MediaPlayerEntity):
    """Android TV media player."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = SUPPORTED_FEATURES

    def __init__(self, hub) -> None:
        """Initialize."""
        super().__init__(hub)
        self._attr_unique_id = f"{hub.entry.unique_id or hub.entry.entry_id}_media_player"

    async def async_added_to_hass(self) -> None:
        """Also follow the external volume entity."""
        await super().async_added_to_hass()
        if (entity_id := self.hub.volume_entity) is not None:
            self.async_on_remove(
                async_track_state_change_event(self.hass, [entity_id], self._on_volume_entity)
            )

    @callback
    def _on_volume_entity(self, _event: Event) -> None:
        self.async_write_ha_state()

    # --------------------------------------------------------------- state

    @property
    def state(self) -> MediaPlayerState:
        """off / idle / playing / paused / on."""
        hub = self.hub
        if hub.power_state != POWER_ON:
            return MediaPlayerState.OFF
        if hub.state.playback == "playing":
            return MediaPlayerState.PLAYING
        if hub.state.playback == "paused":
            return MediaPlayerState.PAUSED
        if hub.is_launcher:
            return MediaPlayerState.IDLE
        return MediaPlayerState.ON

    @property
    def source(self) -> str | None:
        """Current app label."""
        if self.hub.power_state != POWER_ON:
            return None
        return self.hub.app_label(self.hub.state.app_id)

    @property
    def source_list(self) -> list[str]:
        """Visible app labels."""
        return [app.label for app in self.hub.apps if not app.hidden]

    @property
    def app_id(self) -> str | None:
        """Foreground package."""
        return self.hub.state.app_id if self.hub.power_state == POWER_ON else None

    @property
    def app_name(self) -> str | None:
        """Foreground app label."""
        return self.source

    def _external_volume(self) -> Any:
        if (entity_id := self.hub.volume_entity) is None:
            return None
        return self.hass.states.get(entity_id)

    @property
    def volume_level(self) -> float | None:
        """Volume 0..1 (from the external volume entity when configured)."""
        if (ext := self._external_volume()) is not None:
            return ext.attributes.get("volume_level")
        return self.hub.volume_level

    @property
    def is_volume_muted(self) -> bool | None:
        """Mute state."""
        if (ext := self._external_volume()) is not None:
            return ext.attributes.get("is_volume_muted")
        return self.hub.volume_muted

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Card contract attributes."""
        hub = self.hub
        started = hub.wake.wake_started_at
        on = hub.power_state == POWER_ON
        return {
            ATTR_ENTRY_ID: hub.entry.entry_id,
            ATTR_POWER_STATE: hub.power_state,
            ATTR_WAKE_STATE: hub.wake.wake_state,
            ATTR_WAKE_STARTED_AT: started.isoformat() if started else None,
            ATTR_WAKE_TIMEOUT: hub.wake_timeout,
            ATTR_APP_ID: hub.state.app_id if on else None,
            ATTR_APP_NAME: hub.app_label(hub.state.app_id) if on else None,
            ATTR_APP_ACTIVITY: hub.state.app_activity if on else None,
            ATTR_ADB_CONNECTED: hub.adb_connected,
            ATTR_REMOTE_CONNECTED: hub.remote_connected,
            ATTR_VOLUME_ENTITY: hub.volume_entity,
            ATTR_HAS_WAKE_BUTTON: hub.wake_button is not None,
            ATTR_INTEGRATION_VERSION: hub.integration_version,
        }

    # ------------------------------------------------------------ commands

    async def async_turn_on(self) -> None:
        """Turn on from any state."""
        await self.hub.async_turn_on()

    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.hub.async_turn_off()

    async def _forward_volume(self, service: str, data: dict[str, Any] | None = None) -> bool:
        if (entity_id := self.hub.volume_entity) is None:
            return False
        await self.hass.services.async_call(
            "media_player", service, {"entity_id": entity_id, **(data or {})}, blocking=True
        )
        return True

    async def async_volume_up(self) -> None:
        """Volume up."""
        if not await self._forward_volume("volume_up"):
            await self.hub.async_send_key("VOLUME_UP")

    async def async_volume_down(self) -> None:
        """Volume down."""
        if not await self._forward_volume("volume_down"):
            await self.hub.async_send_key("VOLUME_DOWN")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute (the TV key toggles, so only send when it changes)."""
        if await self._forward_volume("volume_mute", {"is_volume_muted": mute}):
            return
        if self.hub.volume_muted is None or self.hub.volume_muted != mute:
            await self.hub.async_send_key("MUTE")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume."""
        if not await self._forward_volume("volume_set", {"volume_level": volume}):
            await self.hub.async_set_volume_level(volume)

    async def async_media_play(self) -> None:
        """Play."""
        await self.hub.async_send_key("PLAY")

    async def async_media_pause(self) -> None:
        """Pause."""
        await self.hub.async_send_key("PAUSE")

    async def async_media_stop(self) -> None:
        """Stop."""
        await self.hub.async_send_key("STOP")

    async def async_media_next_track(self) -> None:
        """Next."""
        await self.hub.async_send_key("NEXT")

    async def async_media_previous_track(self) -> None:
        """Previous."""
        await self.hub.async_send_key("PREVIOUS")

    async def async_select_source(self, source: str) -> None:
        """Launch an app by label or package."""
        await self.hub.async_select_source(source)

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """``app`` -> package, ``url`` -> deep link."""
        if media_type == MEDIA_TYPE_APP:
            await self.hub.async_launch_app(media_id)
        elif media_type == MEDIA_TYPE_URL:
            await self.hub.async_open_url(media_id)
        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_media_type",
                translation_placeholders={"media_type": str(media_type)},
            )
