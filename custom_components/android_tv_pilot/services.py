"""Domain services (target the media_player / remote entity or the device)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import inspect
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import config_validation as cv, service
import voluptuous as vol

from .const import (
    ATTR_ACTION,
    ATTR_COMMAND,
    ATTR_ENTER,
    ATTR_KEY,
    ATTR_PACKAGE,
    ATTR_TEXT,
    ATTR_URL,
    DOMAIN,
    KEY_ACTIONS,
    SERVICE_ADB_COMMAND,
    SERVICE_LAUNCH_APP,
    SERVICE_OPEN_URL,
    SERVICE_REFRESH_APPS,
    SERVICE_SEND_KEY,
    SERVICE_SEND_TEXT,
)

if TYPE_CHECKING:
    from .hub import AndroidTVPilotHub

TARGET = cv.TARGET_SERVICE_FIELDS

SEND_KEY_SCHEMA = vol.Schema(
    {
        **TARGET,
        vol.Required(ATTR_KEY): vol.Any(cv.string, int),
        vol.Optional(ATTR_ACTION, default="press"): vol.In(KEY_ACTIONS),
    }
)
SEND_TEXT_SCHEMA = vol.Schema(
    {
        **TARGET,
        vol.Required(ATTR_TEXT): str,
        vol.Optional(ATTR_ENTER, default=False): cv.boolean,
    }
)
LAUNCH_APP_SCHEMA = vol.Schema({**TARGET, vol.Required(ATTR_PACKAGE): cv.string})
OPEN_URL_SCHEMA = vol.Schema(
    {**TARGET, vol.Required(ATTR_URL): cv.string, vol.Optional(ATTR_PACKAGE): cv.string}
)
ADB_COMMAND_SCHEMA = vol.Schema({**TARGET, vol.Required(ATTR_COMMAND): cv.string})
REFRESH_APPS_SCHEMA = vol.Schema({**TARGET})


def _first_param(func: Callable[..., Any]) -> str | None:
    try:
        return next(iter(inspect.signature(func).parameters), None)
    except (TypeError, ValueError):
        return None


# Home Assistant before 2025.x: async_extract_config_entry_ids(hass, service_call).
_EXTRACT_TAKES_HASS = _first_param(service.async_extract_config_entry_ids) == "hass"
# async_register_admin_service gained supports_response in 2024.x; check, do not guess.
_ADMIN_SUPPORTS_RESPONSE = (
    "supports_response" in inspect.signature(service.async_register_admin_service).parameters
)


async def _async_hubs(hass: HomeAssistant, call: ServiceCall) -> list[AndroidTVPilotHub]:
    """Resolve the call target to loaded hubs of this integration."""
    if _EXTRACT_TAKES_HASS:
        entry_ids = await service.async_extract_config_entry_ids(hass, call)  # type: ignore[call-arg]
    else:
        entry_ids = await service.async_extract_config_entry_ids(call)
    hubs = []
    for entry_id in entry_ids:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry and entry.domain == DOMAIN and entry.state is ConfigEntryState.LOADED:
            hubs.append(entry.runtime_data)
    if not hubs:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_target")
    return hubs


def _for_each(
    hass: HomeAssistant, action: Callable[[AndroidTVPilotHub, ServiceCall], Awaitable[Any]]
) -> Callable[[ServiceCall], Awaitable[None]]:
    async def handler(call: ServiceCall) -> None:
        for hub in await _async_hubs(hass, call):
            await action(hub, call)

    return handler


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services once per Home Assistant instance."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND_KEY):
        return

    async def send_key(hub: AndroidTVPilotHub, call: ServiceCall) -> None:
        await hub.async_send_key(call.data[ATTR_KEY], call.data[ATTR_ACTION])

    async def send_text(hub: AndroidTVPilotHub, call: ServiceCall) -> None:
        await hub.async_send_text(call.data[ATTR_TEXT], call.data[ATTR_ENTER])

    async def launch_app(hub: AndroidTVPilotHub, call: ServiceCall) -> None:
        await hub.async_launch_app(call.data[ATTR_PACKAGE])

    async def open_url(hub: AndroidTVPilotHub, call: ServiceCall) -> None:
        await hub.async_open_url(call.data[ATTR_URL], call.data.get(ATTR_PACKAGE))

    async def refresh_apps(hub: AndroidTVPilotHub, call: ServiceCall) -> None:
        await hub.async_refresh_apps()

    async def adb_command(call: ServiceCall) -> ServiceResponse:
        """Run a raw shell command (intentionally unquoted; admin only)."""
        if not _ADMIN_SUPPORTS_RESPONSE and call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None or not user.is_admin:
                raise Unauthorized(context=call.context)
        hubs = await _async_hubs(hass, call)
        if len(hubs) != 1:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="single_target")
        output = await hubs[0].async_adb_shell(call.data[ATTR_COMMAND], timeout=30.0)
        if call.return_response:
            return {"output": output}
        return None

    hass.services.async_register(DOMAIN, SERVICE_SEND_KEY, _for_each(hass, send_key), SEND_KEY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SEND_TEXT, _for_each(hass, send_text), SEND_TEXT_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_LAUNCH_APP, _for_each(hass, launch_app), LAUNCH_APP_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_OPEN_URL, _for_each(hass, open_url), OPEN_URL_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH_APPS, _for_each(hass, refresh_apps), REFRESH_APPS_SCHEMA
    )
    # Raw shell on the TV: admin users only.
    if _ADMIN_SUPPORTS_RESPONSE:
        service.async_register_admin_service(
            hass,
            DOMAIN,
            SERVICE_ADB_COMMAND,
            adb_command,
            ADB_COMMAND_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
    else:  # older Home Assistant: same admin check, done in the handler
        hass.services.async_register(
            DOMAIN,
            SERVICE_ADB_COMMAND,
            adb_command,
            ADB_COMMAND_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
