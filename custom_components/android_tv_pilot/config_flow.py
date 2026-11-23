"""Config, options and reauth flows."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from .adb import (
    DEVICE_INFO_COMMAND,
    AdbAuthTimeout,
    AdbClient,
    AdbUnreachable,
    DeviceInfoResult,
    ensure_adb_key,
    load_adb_signer,
    parse_device_info,
)
from .const import (
    ADB_KEY_FILENAME,
    CONF_ADB_PORT,
    CONF_APP_OVERRIDES,
    CONF_EXCLUDE_SYSTEM_APPS,
    CONF_MAC,
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_POLL_INTERVAL,
    CONF_REPRESS_INTERVAL,
    CONF_SW_VERSION,
    CONF_UNIQUE_SERIAL,
    CONF_USE_REMOTE,
    CONF_VOLUME_ENTITY,
    CONF_WAKE_BUTTON,
    CONF_WAKE_TIMEOUT,
    DEFAULT_ADB_PORT,
    DEFAULT_EXCLUDE_SYSTEM_APPS,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_REPRESS_INTERVAL,
    DEFAULT_WAKE_TIMEOUT,
    DOMAIN,
    REMOTE_CERT_FILENAME,
    REMOTE_KEY_FILENAME,
)
from .remote_client import (
    RemoteAuthError,
    RemotePairing,
    RemoteUnreachable,
    ensure_remote_cert,
)
from .wake_entity import WAKE_ENTITY_DOMAINS

_LOGGER = logging.getLogger(__name__)

CONF_PIN = "pin"
CONF_SKIP_REMOTE = "skip_remote"
CONF_PACKAGE = "package"
CONF_LABEL = "label"
CONF_ICON_URL = "icon_url"
CONF_HIDDEN = "hidden"

# Links shown in the wake forms (URLs must not live inside translation strings).
WAKE_LINKS = {
    "guide_url": "https://community.home-assistant.io/t/wake-a-xiaomi-tv-box-from-deep-standby-with-an-esp32-bluetooth-esphome/1035816",
    "firmware_url": "https://github.com/dckiller51/esphome-xiaomi-ble-wake",
}

# The user has to walk to the TV and accept "Allow USB debugging".
ADB_AUTH_WAIT = 30.0


def _seconds(minimum: int, maximum: int) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="s"
        )
    )


def wake_schema() -> vol.Schema:
    """Wake settings (config flow and options)."""
    return vol.Schema(
        {
            vol.Optional(CONF_WAKE_BUTTON): EntitySelector(
                EntitySelectorConfig(domain=list(WAKE_ENTITY_DOMAINS))
            ),
            vol.Required(CONF_WAKE_TIMEOUT, default=DEFAULT_WAKE_TIMEOUT): _seconds(10, 300),
            vol.Required(CONF_REPRESS_INTERVAL, default=DEFAULT_REPRESS_INTERVAL): _seconds(2, 60),
        }
    )


async def _async_adb_identify(hass: HomeAssistant, host: str, port: int) -> DeviceInfoResult:
    """Connect over ADB (waiting for the debugging prompt) and read the TV identity."""
    key = hass.config.path(".storage", ADB_KEY_FILENAME)
    await hass.async_add_executor_job(ensure_adb_key, key)
    signer = await hass.async_add_executor_job(load_adb_signer, key)
    client = AdbClient(host, port, signer, connect_timeout=5.0, auth_timeout=ADB_AUTH_WAIT)
    try:
        await client.async_connect()
        output = await client.async_shell(DEVICE_INFO_COMMAND)
    finally:
        await client.async_close()
    return parse_device_info(output)


class AndroidTVPilotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a TV: ADB -> remote pairing -> wake settings."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._data: dict[str, Any] = {}
        self._title: str = ""
        self._pairing: RemotePairing | None = None
        self._pairing_error: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options flow."""
        return AndroidTVPilotOptionsFlow()

    # ------------------------------------------------------------------ user

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Host, name and ADB port."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input.get(CONF_ADB_PORT, DEFAULT_ADB_PORT))
            try:
                info = await _async_adb_identify(self.hass, host, port)
            except AdbAuthTimeout:
                errors["base"] = "adb_auth_timeout"
            except AdbUnreachable:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during ADB setup")
                errors["base"] = "unknown"
            else:
                unique_id = info.serial or info.mac
                if not unique_id:
                    errors["base"] = "no_unique_id"
                else:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_ADB_PORT: port})
                    self._title = user_input[CONF_NAME].strip() or info.model or host
                    self._data = {
                        CONF_HOST: host,
                        CONF_ADB_PORT: port,
                        CONF_UNIQUE_SERIAL: info.serial,
                        CONF_MAC: info.mac,
                        CONF_MANUFACTURER: info.manufacturer,
                        CONF_MODEL: info.model,
                        CONF_SW_VERSION: f"Android {info.release}" if info.release else None,
                        CONF_USE_REMOTE: False,
                    }
                    return await self.async_step_pair()

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): TextSelector(),
                vol.Required(CONF_NAME, default="Android TV"): TextSelector(),
                vol.Required(CONF_ADB_PORT, default=DEFAULT_ADB_PORT): NumberSelector(
                    NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
        )

    # ------------------------------------------------------------------ pair

    async def _async_start_pairing(self) -> bool:
        """Ask the TV to show a PIN. False if the remote protocol is unreachable."""
        if self._pairing is not None:
            self._pairing.close()
        certfile = self.hass.config.path(".storage", REMOTE_CERT_FILENAME)
        keyfile = self.hass.config.path(".storage", REMOTE_KEY_FILENAME)
        await self.hass.async_add_executor_job(ensure_remote_cert, certfile, keyfile)
        self._pairing = RemotePairing(self._data[CONF_HOST], certfile, keyfile)
        try:
            await self._pairing.async_start()
        except RemoteUnreachable:
            self._pairing.close()
            self._pairing = None
            return False
        return True

    async def async_step_pair(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Remote-protocol pairing with the PIN shown on the TV (or skip: ADB only)."""
        errors: dict[str, str] = {}
        if user_input is None:
            if not await self._async_start_pairing():
                errors["base"] = "remote_unreachable"
        elif user_input.get(CONF_SKIP_REMOTE):
            if self._pairing is not None:
                self._pairing.close()
                self._pairing = None
            self._data[CONF_USE_REMOTE] = False
            return await self._async_after_pair()
        else:
            pin = str(user_input.get(CONF_PIN, "")).strip().upper()
            if self._pairing is None and not await self._async_start_pairing():
                errors["base"] = "remote_unreachable"
            elif not pin:
                errors[CONF_PIN] = "invalid_pin"
            else:
                assert self._pairing is not None
                try:
                    await self._pairing.async_finish(pin)
                except RemoteAuthError:
                    errors[CONF_PIN] = "invalid_pin"
                    await self._async_start_pairing()
                except RemoteUnreachable:
                    errors["base"] = "pairing_closed"
                    if not await self._async_start_pairing():
                        errors["base"] = "remote_unreachable"
                else:
                    self._pairing.close()
                    self._pairing = None
                    self._data[CONF_USE_REMOTE] = True
                    return await self._async_after_pair()

        schema = vol.Schema(
            {
                vol.Optional(CONF_PIN): TextSelector(),
                vol.Optional(CONF_SKIP_REMOTE, default=False): BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="reauth_pair" if self.source == "reauth" else "pair",
            data_schema=schema,
            errors=errors,
            description_placeholders={"host": self._data.get(CONF_HOST, "")},
        )

    async def async_step_reauth_pair(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pairing during reauth."""
        return await self.async_step_pair(user_input)

    async def _async_after_pair(self) -> ConfigFlowResult:
        if self.source == "reauth":
            entry = self._get_reauth_entry()
            return self.async_update_reload_and_abort(
                entry, data_updates={CONF_USE_REMOTE: self._data[CONF_USE_REMOTE]}
            )
        return await self.async_step_wake()

    # ------------------------------------------------------------------ wake

    async def async_step_wake(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Optional wake button and timing."""
        if user_input is not None:
            options = {
                CONF_WAKE_TIMEOUT: int(user_input[CONF_WAKE_TIMEOUT]),
                CONF_REPRESS_INTERVAL: int(user_input[CONF_REPRESS_INTERVAL]),
                CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
                CONF_EXCLUDE_SYSTEM_APPS: DEFAULT_EXCLUDE_SYSTEM_APPS,
                CONF_APP_OVERRIDES: {},
            }
            if user_input.get(CONF_WAKE_BUTTON):
                options[CONF_WAKE_BUTTON] = user_input[CONF_WAKE_BUTTON]
            return self.async_create_entry(title=self._title, data=self._data, options=options)
        return self.async_show_form(
            step_id="wake", data_schema=wake_schema(), description_placeholders=WAKE_LINKS
        )

    # ---------------------------------------------------------------- reauth

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Credentials were rejected (ADB key or remote pairing)."""
        self._data = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Reconnect ADB (accept the prompt on the TV), then pair the remote again."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _async_adb_identify(
                    self.hass, self._data[CONF_HOST], int(self._data.get(CONF_ADB_PORT, DEFAULT_ADB_PORT))
                )
            except AdbAuthTimeout:
                errors["base"] = "adb_auth_timeout"
            except AdbUnreachable:
                errors["base"] = "cannot_connect"
            else:
                if self._data.get(CONF_USE_REMOTE):
                    return await self.async_step_reauth_pair()
                return self.async_update_reload_and_abort(self._get_reauth_entry())
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"host": self._data.get(CONF_HOST, "")},
        )

    @callback
    def async_remove(self) -> None:
        """Close a pairing connection left open by an abandoned flow."""
        if self._pairing is not None:
            self._pairing.close()
            self._pairing = None


class AndroidTVPilotOptionsFlow(OptionsFlow):
    """Settings and per-app overrides."""

    def __init__(self) -> None:
        """Initialize."""
        self._package: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Menu."""
        return self.async_show_menu(step_id="init", menu_options=["settings", "app_override"])

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Wake, volume, polling and app list settings."""
        options = dict(self.config_entry.options)
        if user_input is not None:
            for key in (CONF_WAKE_BUTTON, CONF_VOLUME_ENTITY):
                if user_input.get(key):
                    options[key] = user_input[key]
                else:
                    options.pop(key, None)
            options[CONF_WAKE_TIMEOUT] = int(user_input[CONF_WAKE_TIMEOUT])
            options[CONF_REPRESS_INTERVAL] = int(user_input[CONF_REPRESS_INTERVAL])
            options[CONF_POLL_INTERVAL] = int(user_input[CONF_POLL_INTERVAL])
            options[CONF_EXCLUDE_SYSTEM_APPS] = bool(user_input[CONF_EXCLUDE_SYSTEM_APPS])
            return self.async_create_entry(data=options)

        schema = wake_schema().extend(
            {
                vol.Optional(CONF_VOLUME_ENTITY): EntitySelector(EntitySelectorConfig(domain="media_player")),
                vol.Required(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): _seconds(2, 120),
                vol.Required(
                    CONF_EXCLUDE_SYSTEM_APPS, default=DEFAULT_EXCLUDE_SYSTEM_APPS
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(
            step_id="settings",
            data_schema=self.add_suggested_values_to_schema(schema, options),
            description_placeholders=WAKE_LINKS,
        )

    async def async_step_app_override(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick the app to customise."""
        if user_input is not None:
            self._package = str(user_input[CONF_PACKAGE]).strip()
            return await self.async_step_app_override_edit()
        hub = getattr(self.config_entry, "runtime_data", None)
        apps = list(getattr(hub, "apps", []) or [])
        choices = [SelectOptionDict(value=app.package, label=f"{app.label} ({app.package})") for app in apps]
        for package in self.config_entry.options.get(CONF_APP_OVERRIDES, {}):
            if package not in {c["value"] for c in choices}:
                choices.append(SelectOptionDict(value=package, label=package))
        schema = vol.Schema(
            {
                vol.Required(CONF_PACKAGE): SelectSelector(
                    SelectSelectorConfig(options=choices, custom_value=True, mode=SelectSelectorMode.DROPDOWN)
                )
            }
        )
        return self.async_show_form(step_id="app_override", data_schema=schema)

    async def async_step_app_override_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Label, icon URL and hidden flag for one package (empty = remove override)."""
        options = dict(self.config_entry.options)
        overrides: dict[str, Any] = dict(options.get(CONF_APP_OVERRIDES, {}))
        assert self._package is not None
        if user_input is not None:
            label = str(user_input.get(CONF_LABEL) or "").strip()
            icon_url = str(user_input.get(CONF_ICON_URL) or "").strip()
            hidden = {"show": False, "hide": True}.get(user_input.get(CONF_HIDDEN, "auto"))
            if label or icon_url or hidden is not None:
                overrides[self._package] = {
                    CONF_LABEL: label or None,
                    CONF_ICON_URL: icon_url or None,
                    CONF_HIDDEN: hidden,
                }
            else:
                overrides.pop(self._package, None)
            options[CONF_APP_OVERRIDES] = overrides
            return self.async_create_entry(data=options)

        current = overrides.get(self._package, {})
        schema = vol.Schema(
            {
                vol.Optional(CONF_LABEL): TextSelector(),
                vol.Optional(CONF_ICON_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
                vol.Required(CONF_HIDDEN, default="auto"): SelectSelector(
                    SelectSelectorConfig(
                        options=["auto", "show", "hide"],
                        translation_key="hidden_mode",
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        suggested = {k: v for k, v in current.items() if v is not None and k != CONF_HIDDEN}
        suggested[CONF_HIDDEN] = {None: "auto", False: "show", True: "hide"}[current.get(CONF_HIDDEN)]
        return self.async_show_form(
            step_id="app_override_edit",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            description_placeholders={"package": self._package},
        )
