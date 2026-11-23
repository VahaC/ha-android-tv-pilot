"""Constants for the Android TV Pilot integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "android_tv_pilot"

# Config entry data
CONF_ADB_PORT: Final = "adb_port"
CONF_USE_REMOTE: Final = "use_remote"
CONF_UNIQUE_SERIAL: Final = "serial"
CONF_MAC: Final = "mac"
CONF_MANUFACTURER: Final = "manufacturer"
CONF_MODEL: Final = "model"
CONF_SW_VERSION: Final = "sw_version"

# Config entry options
CONF_WAKE_BUTTON: Final = "wake_button"
CONF_WAKE_TIMEOUT: Final = "wake_timeout"
CONF_REPRESS_INTERVAL: Final = "repress_interval"
CONF_VOLUME_ENTITY: Final = "volume_entity"
CONF_POLL_INTERVAL: Final = "poll_interval"
CONF_EXCLUDE_SYSTEM_APPS: Final = "exclude_system_apps"
CONF_APP_OVERRIDES: Final = "app_overrides"

DEFAULT_ADB_PORT: Final = 5555
DEFAULT_REMOTE_API_PORT: Final = 6466
DEFAULT_REMOTE_PAIR_PORT: Final = 6467
DEFAULT_WAKE_TIMEOUT: Final = 40
DEFAULT_REPRESS_INTERVAL: Final = 8
DEFAULT_POLL_INTERVAL: Final = 5
DEFAULT_EXCLUDE_SYSTEM_APPS: Final = True

# Client name shown on the TV during remote-protocol pairing.
REMOTE_CLIENT_NAME: Final = "Home Assistant (Android TV Pilot)"

# Key and certificate files, stored under <config>/.storage
STORAGE_PREFIX: Final = "android_tv_pilot_"
ADB_KEY_FILENAME: Final = f"{STORAGE_PREFIX}adbkey"
REMOTE_CERT_FILENAME: Final = f"{STORAGE_PREFIX}remote_cert.pem"
REMOTE_KEY_FILENAME: Final = f"{STORAGE_PREFIX}remote_key.pem"

# Frontend
STATIC_URL_PATH: Final = "/android_tv_pilot_static"
CARD_FILENAME: Final = "android-tv-pilot-card.js"
SCREENSHOT_URL: Final = "/api/android_tv_pilot/screenshot/{entry_id}"

# Attributes exposed on the media_player entity (card contract)
ATTR_ENTRY_ID: Final = "entry_id"
ATTR_POWER_STATE: Final = "power_state"
ATTR_WAKE_STATE: Final = "wake_state"
ATTR_WAKE_STARTED_AT: Final = "wake_started_at"
ATTR_WAKE_TIMEOUT: Final = "wake_timeout"
ATTR_APP_ID: Final = "app_id"
ATTR_APP_NAME: Final = "app_name"
ATTR_APP_ACTIVITY: Final = "app_activity"
ATTR_ADB_CONNECTED: Final = "adb_connected"
ATTR_REMOTE_CONNECTED: Final = "remote_connected"
ATTR_VOLUME_ENTITY: Final = "volume_entity"
ATTR_HAS_WAKE_BUTTON: Final = "has_wake_button"

POWER_OFF: Final = "off"
POWER_WAKING: Final = "waking"
POWER_ON: Final = "on"
POWER_ASLEEP: Final = "asleep"

# Services
SERVICE_SEND_KEY: Final = "send_key"
SERVICE_SEND_TEXT: Final = "send_text"
SERVICE_LAUNCH_APP: Final = "launch_app"
SERVICE_OPEN_URL: Final = "open_url"
SERVICE_ADB_COMMAND: Final = "adb_command"
SERVICE_REFRESH_APPS: Final = "refresh_apps"

ATTR_KEY: Final = "key"
ATTR_ACTION: Final = "action"
ATTR_TEXT: Final = "text"
ATTR_ENTER: Final = "enter"
ATTR_PACKAGE: Final = "package"
ATTR_URL: Final = "url"
ATTR_COMMAND: Final = "command"

KEY_ACTIONS: Final = ("press", "long", "down", "up")

# Media content types accepted by play_media
MEDIA_TYPE_APP: Final = "app"
MEDIA_TYPE_URL: Final = "url"

# Websocket error codes (card contract)
WS_ERR_NOT_FOUND: Final = "not_found"
WS_ERR_TV_UNREACHABLE: Final = "tv_unreachable"
WS_ERR_UNSUPPORTED: Final = "unsupported"
WS_ERR_FAILED: Final = "failed"
