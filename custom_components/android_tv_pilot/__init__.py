"""Android TV Pilot: self-sufficient Android TV control over ADB and the remote protocol."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .adb import AdbClient, ensure_adb_key, load_adb_signer
from .apps import KnownAppsProvider
from .const import (
    ADB_KEY_FILENAME,
    CONF_ADB_PORT,
    CONF_APP_OVERRIDES,
    CONF_EXCLUDE_SYSTEM_APPS,
    CONF_USE_REMOTE,
    DEFAULT_ADB_PORT,
    DOMAIN,
    REMOTE_CERT_FILENAME,
    REMOTE_KEY_FILENAME,
)
from .frontend_registration import async_integration_version, async_register_frontend
from .hub import AndroidTVPilotHub
from .remote_client import RemoteClient, ensure_remote_cert
from .services import async_setup_services
from .websocket_api import async_setup_websocket_api

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.REMOTE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

KNOWN_APPS_KEY: HassKey[KnownAppsProvider] = HassKey(f"{DOMAIN}_known_apps")

type AndroidTVPilotConfigEntry = ConfigEntry[AndroidTVPilotHub]


def storage_path(hass: HomeAssistant, filename: str) -> str:
    """Path of a key/cert file under <config>/.storage."""
    return hass.config.path(".storage", filename)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up domain-level services, websocket commands, views and the card."""
    async_setup_services(hass)
    async_setup_websocket_api(hass)
    await async_register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AndroidTVPilotConfigEntry) -> bool:
    """Set up one TV. Never fails because the TV is asleep: it starts as ``off``."""
    adb_key = storage_path(hass, ADB_KEY_FILENAME)
    await hass.async_add_executor_job(ensure_adb_key, adb_key)
    signer = await hass.async_add_executor_job(load_adb_signer, adb_key)

    if (known := hass.data.get(KNOWN_APPS_KEY)) is None:
        known = await hass.async_add_executor_job(KnownAppsProvider.load)
        hass.data[KNOWN_APPS_KEY] = known

    host = entry.data[CONF_HOST]
    adb = AdbClient(host, entry.data.get(CONF_ADB_PORT, DEFAULT_ADB_PORT), signer)

    hub: AndroidTVPilotHub | None = None

    def _on_remote_update() -> None:
        if hub is not None:
            hub.on_remote_update()

    def _on_remote_invalid_auth() -> None:
        if hub is not None:
            hub.on_remote_invalid_auth()

    remote: RemoteClient | None = None
    if entry.data.get(CONF_USE_REMOTE, False):
        certfile = storage_path(hass, REMOTE_CERT_FILENAME)
        keyfile = storage_path(hass, REMOTE_KEY_FILENAME)
        await hass.async_add_executor_job(ensure_remote_cert, certfile, keyfile)
        remote = RemoteClient(
            host,
            certfile,
            keyfile,
            on_update=_on_remote_update,
            on_invalid_auth=_on_remote_invalid_auth,
        )

    hub = AndroidTVPilotHub(hass, entry, adb, remote, known)
    hub.integration_version = await async_integration_version(hass)
    entry.runtime_data = hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await hub.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


_LIVE_OPTIONS = {CONF_APP_OVERRIDES, CONF_EXCLUDE_SYSTEM_APPS}


async def _async_options_updated(hass: HomeAssistant, entry: AndroidTVPilotConfigEntry) -> None:
    """Apply app options live; reload for anything else."""
    hub = entry.runtime_data
    old = {k: v for k, v in hub.started_options.items() if k not in _LIVE_OPTIONS}
    new = {k: v for k, v in entry.options.items() if k not in _LIVE_OPTIONS}
    if old == new:
        hub.rebuild_apps()
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AndroidTVPilotConfigEntry) -> bool:
    """Unload: stop tasks and close both connections."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_stop()
    return unload_ok
