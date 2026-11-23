"""Websocket commands for the card and the authenticated screenshot view."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import contextlib
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import TYPE_CHECKING, Any

from aiohttp import web
from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
import voluptuous as vol

from .const import (
    DOMAIN,
    KEY_ACTIONS,
    SCREENSHOT_URL,
    WS_ERR_FAILED,
    WS_ERR_NOT_FOUND,
)
from .errors import PilotError

if TYPE_CHECKING:
    from .hub import AndroidTVPilotHub

_LOGGER = logging.getLogger(__name__)

SIGNED_PATH_EXPIRY = timedelta(seconds=30)


def get_hub(hass: HomeAssistant, entry_id: str) -> AndroidTVPilotHub | None:
    """Return the hub of a loaded entry of this domain."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        return None
    return entry.runtime_data


@callback
def async_setup_websocket_api(hass: HomeAssistant) -> None:
    """Register websocket commands and the screenshot view."""
    websocket_api.async_register_command(hass, ws_apps)
    websocket_api.async_register_command(hass, ws_send_key)
    websocket_api.async_register_command(hass, ws_send_text)
    websocket_api.async_register_command(hass, ws_launch_app)
    websocket_api.async_register_command(hass, ws_open_url)
    websocket_api.async_register_command(hass, ws_screenshot_url)
    hass.http.register_view(ScreenshotView())


async def _run(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    action: Callable[[AndroidTVPilotHub], Awaitable[dict[str, Any]]],
) -> None:
    hub = get_hub(hass, msg["entry_id"])
    if hub is None:
        connection.send_error(
            msg["id"], WS_ERR_NOT_FOUND, f"No loaded Android TV Pilot entry {msg['entry_id']}"
        )
        return
    try:
        result = await action(hub)
    except PilotError as err:
        connection.send_error(msg["id"], err.ws_code, str(err))
        return
    except Exception as err:
        _LOGGER.debug("Websocket command %s failed", msg["type"], exc_info=True)
        connection.send_error(msg["id"], WS_ERR_FAILED, str(err) or type(err).__name__)
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/apps", vol.Required("entry_id"): str})
@websocket_api.async_response
async def ws_apps(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the app list (refreshes it first if never loaded)."""

    async def action(hub: AndroidTVPilotHub) -> dict[str, Any]:
        if not hub.apps:
            with contextlib.suppress(PilotError):
                await hub.async_refresh_apps()
        return {"apps": [app.as_dict() for app in hub.apps]}

    await _run(hass, connection, msg, action)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/send_key",
        vol.Required("entry_id"): str,
        vol.Required("key"): vol.Any(str, int),
        vol.Optional("action", default="press"): vol.In(KEY_ACTIONS),
    }
)
@websocket_api.async_response
async def ws_send_key(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send one key (fast path for the D-pad)."""

    owner = ("ws", id(connection))

    async def action(hub: AndroidTVPilotHub) -> dict[str, Any]:
        await hub.async_send_key(msg["key"], msg["action"], owner=owner)
        if msg["action"] == "down" and hub.repeating_key is not None:
            entry_id = msg["entry_id"]

            @callback
            def _stop_on_close() -> None:
                if (current := get_hub(hass, entry_id)) is not None:
                    current.stop_repeat(owner=owner)

            # Called when this websocket connection closes: stop its key repeat.
            connection.subscriptions[(DOMAIN, "key_repeat", entry_id)] = _stop_on_close
        return {}

    await _run(hass, connection, msg, action)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/send_text",
        vol.Required("entry_id"): str,
        vol.Required("text"): str,
        vol.Optional("enter", default=False): bool,
    }
)
@websocket_api.async_response
async def ws_send_text(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Type text."""

    async def action(hub: AndroidTVPilotHub) -> dict[str, Any]:
        await hub.async_send_text(msg["text"], msg["enter"])
        return {}

    await _run(hass, connection, msg, action)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/launch_app",
        vol.Required("entry_id"): str,
        vol.Required("package"): str,
    }
)
@websocket_api.async_response
async def ws_launch_app(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Launch an app."""

    async def action(hub: AndroidTVPilotHub) -> dict[str, Any]:
        await hub.async_launch_app(msg["package"])
        return {}

    await _run(hass, connection, msg, action)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/open_url",
        vol.Required("entry_id"): str,
        vol.Required("url"): str,
        vol.Optional("package"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def ws_open_url(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Open a URL or deep link."""

    async def action(hub: AndroidTVPilotHub) -> dict[str, Any]:
        await hub.async_open_url(msg["url"], msg.get("package") or None)
        return {}

    await _run(hass, connection, msg, action)


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/screenshot_url", vol.Required("entry_id"): str}
)
@callback
def ws_screenshot_url(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return a signed URL (30 s) for the screenshot view."""
    if get_hub(hass, msg["entry_id"]) is None:
        connection.send_error(
            msg["id"], WS_ERR_NOT_FOUND, f"No loaded Android TV Pilot entry {msg['entry_id']}"
        )
        return
    path = async_sign_path(
        hass,
        SCREENSHOT_URL.format(entry_id=msg["entry_id"]),
        SIGNED_PATH_EXPIRY,
        refresh_token_id=connection.refresh_token_id,
    )
    connection.send_result(msg["id"], {"url": path})


class ScreenshotView(HomeAssistantView):
    """GET /api/android_tv_pilot/screenshot/{entry_id} -> image/png (auth or signed path)."""

    url = SCREENSHOT_URL
    name = "api:android_tv_pilot:screenshot"
    requires_auth = True

    async def get(self, request: web.Request, entry_id: str) -> web.StreamResponse:
        """Capture (or reuse a <2 s old) screenshot."""
        hass: HomeAssistant = request.app[_hass_key()]
        hub = get_hub(hass, entry_id)
        if hub is None:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="not_found")
        try:
            png = await hub.async_screenshot()
        except PilotError as err:
            status = (
                HTTPStatus.SERVICE_UNAVAILABLE
                if err.ws_code in ("tv_unreachable", "unsupported")
                else HTTPStatus.BAD_GATEWAY
            )
            return web.Response(status=status, text=err.ws_code)
        return web.Response(
            body=png,
            content_type="image/png",
            headers={"Cache-Control": "no-store"},
        )


def _hass_key() -> Any:
    """The aiohttp app key holding ``hass`` (``KEY_HASS`` on current HA)."""
    try:
        from homeassistant.helpers.http import KEY_HASS  # noqa: PLC0415
    except ImportError:  # pragma: no cover - very old HA
        return "hass"
    return KEY_HASS
