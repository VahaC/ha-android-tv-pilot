"""Translated exceptions shared by entities, services and the websocket API."""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    WS_ERR_FAILED,
    WS_ERR_NOT_FOUND,
    WS_ERR_TV_UNREACHABLE,
    WS_ERR_UNSUPPORTED,
)


class PilotError(HomeAssistantError):
    """Base error with a translation key and a websocket error code."""

    ws_code = WS_ERR_FAILED

    def __init__(self, translation_key: str, **placeholders: str) -> None:
        """Initialize with a translation key from strings.json ``exceptions``."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=placeholders or None,
        )


class TvUnreachableError(PilotError):
    """The TV cannot be reached on any transport."""

    ws_code = WS_ERR_TV_UNREACHABLE


class UnsupportedError(PilotError):
    """The request cannot be done with the transports available."""

    ws_code = WS_ERR_UNSUPPORTED


class NotFoundError(PilotError):
    """Unknown entry, app or key."""

    ws_code = WS_ERR_NOT_FOUND


class CommandFailedError(PilotError):
    """The TV answered but the command failed."""

    ws_code = WS_ERR_FAILED
