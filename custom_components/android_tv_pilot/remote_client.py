"""Wrapper around ``androidtvremote2`` (Android TV Remote protocol v2).

API verified against androidtvremote2 0.3.3:
- ``AndroidTVRemote(client_name, certfile, keyfile, host, api_port, pair_port, loop, enable_ime)``
- ``async_connect()`` raises CannotConnect / ConnectionClosed / InvalidAuth
- ``keep_reconnecting(invalid_auth_callback)``, ``disconnect()``
- ``async_start_pairing()``, ``async_finish_pairing(code)``
- ``send_key_command(key, direction)`` with direction "SHORT" / "START_LONG" / "END_LONG"
- ``send_text(text)``, ``send_launch_app_command(app_link_or_id)``
- callbacks: is_on, current_app, volume_info (TypedDict level/max/muted), is_available
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
import logging
import os
from typing import Any

from .const import REMOTE_CLIENT_NAME

_LOGGER = logging.getLogger(__name__)


def ensure_remote_cert(certfile: str, keyfile: str) -> None:
    """Generate the remote-protocol client certificate if missing. Blocking."""
    if os.path.isfile(certfile) and os.path.isfile(keyfile):
        return
    from androidtvremote2.certificate_generator import (  # noqa: PLC0415
        generate_selfsigned_cert,
    )

    cert_pem, key_pem = generate_selfsigned_cert(REMOTE_CLIENT_NAME)
    with open(certfile, "wb") as f:
        f.write(cert_pem)
    with open(keyfile, "wb") as f:
        f.write(key_pem)
    for p in (certfile, keyfile):
        with contextlib.suppress(OSError):
            os.chmod(p, 0o600)


def create_remote(
    host: str, certfile: str, keyfile: str, loop: asyncio.AbstractEventLoop | None = None
) -> Any:
    """Create an ``AndroidTVRemote`` instance."""
    from androidtvremote2 import AndroidTVRemote  # noqa: PLC0415

    return AndroidTVRemote(
        client_name=REMOTE_CLIENT_NAME,
        certfile=certfile,
        keyfile=keyfile,
        host=host,
        loop=loop,
        enable_ime=True,
    )


class RemoteUnreachable(Exception):
    """The remote protocol port is not reachable."""


class RemoteAuthError(Exception):
    """Pairing is needed (again)."""


class RemoteClient:
    """Connection manager for the remote protocol with push callbacks."""

    def __init__(
        self,
        host: str,
        certfile: str,
        keyfile: str,
        *,
        on_update: Callable[[], None],
        on_invalid_auth: Callable[[], None],
    ) -> None:
        """Initialize."""
        self._host = host
        self._certfile = certfile
        self._keyfile = keyfile
        self._on_update = on_update
        self._on_invalid_auth = on_invalid_auth
        self._api: Any = None
        self.available = False
        self.is_on: bool | None = None
        self.current_app: str | None = None
        self.volume_level: int | None = None
        self.volume_max: int | None = None
        self.volume_muted: bool | None = None
        self.device_info: dict[str, str] | None = None
        self._connect_lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        """Return True if commands can be sent."""
        return self._api is not None and self.available

    async def async_connect(self, timeout: float = 5.0) -> None:
        """Connect; raises RemoteUnreachable or RemoteAuthError."""
        async with self._connect_lock:
            await self._async_connect_locked(timeout)

    async def _async_connect_locked(self, timeout: float) -> None:
        from androidtvremote2 import (  # noqa: PLC0415
            CannotConnect,
            ConnectionClosed,
            InvalidAuth,
        )

        if self.connected:
            return
        if self._api is None:
            self._api = create_remote(self._host, self._certfile, self._keyfile)
            self._api.add_is_on_updated_callback(self._is_on_updated)
            self._api.add_current_app_updated_callback(self._current_app_updated)
            self._api.add_volume_info_updated_callback(self._volume_updated)
            self._api.add_is_available_updated_callback(self._available_updated)
        else:
            # Stop the library's own reconnect loop before a fresh attempt.
            self._api.disconnect()
        try:
            async with asyncio.timeout(timeout):
                await self._api.async_connect()
        except InvalidAuth as err:
            raise RemoteAuthError(str(err)) from err
        except (CannotConnect, ConnectionClosed, TimeoutError) as err:
            raise RemoteUnreachable(str(err)) from err
        self.available = True
        self.is_on = self._api.is_on
        self.current_app = self._api.current_app
        if (vol := self._api.volume_info) is not None:
            self._volume_updated(vol)
        self.device_info = self._api.device_info
        self._api.keep_reconnecting(self._invalid_auth)
        self._on_update()

    def disconnect(self) -> None:
        """Disconnect and stop reconnecting."""
        if self._api is not None:
            self._api.disconnect()
        self.available = False

    def _invalid_auth(self) -> None:
        self.available = False
        self._on_invalid_auth()

    def _is_on_updated(self, is_on: bool) -> None:
        self.is_on = is_on
        self._on_update()

    def _current_app_updated(self, app: str) -> None:
        self.current_app = app or None
        self._on_update()

    def _volume_updated(self, info: dict[str, Any]) -> None:
        self.volume_level = info.get("level")
        self.volume_max = info.get("max")
        self.volume_muted = info.get("muted")
        self._on_update()

    def _available_updated(self, available: bool) -> None:
        self.available = available
        self._on_update()

    def send_key(self, key: str | int, direction: str = "SHORT") -> None:
        """Send a key; raises ValueError for keys unknown to the protocol."""
        if not self.connected:
            raise RemoteUnreachable("not connected")
        from androidtvremote2 import ConnectionClosed  # noqa: PLC0415

        try:
            self._api.send_key_command(key, direction)
        except ConnectionClosed as err:
            raise RemoteUnreachable(str(err)) from err

    def send_launch(self, app_link_or_id: str) -> None:
        """Launch an app by package or open a deep link via the remote protocol."""
        if not self.connected:
            raise RemoteUnreachable("not connected")
        from androidtvremote2 import ConnectionClosed  # noqa: PLC0415

        try:
            self._api.send_launch_app_command(app_link_or_id)
        except ConnectionClosed as err:
            raise RemoteUnreachable(str(err)) from err

    def send_text(self, text: str) -> None:
        """Send text through the IME channel."""
        if not self.connected:
            raise RemoteUnreachable("not connected")
        from androidtvremote2 import ConnectionClosed  # noqa: PLC0415

        try:
            self._api.send_text(text)
        except ConnectionClosed as err:
            raise RemoteUnreachable(str(err)) from err


class RemotePairing:
    """One pairing session used by the config flow."""

    def __init__(self, host: str, certfile: str, keyfile: str) -> None:
        """Initialize."""
        self._api = create_remote(host, certfile, keyfile)

    async def async_start(self) -> None:
        """Ask the TV to show a PIN; raises RemoteUnreachable."""
        from androidtvremote2 import CannotConnect, ConnectionClosed  # noqa: PLC0415

        try:
            async with asyncio.timeout(10):
                await self._api.async_start_pairing()
        except (CannotConnect, ConnectionClosed, TimeoutError) as err:
            raise RemoteUnreachable(str(err)) from err

    async def async_finish(self, pin: str) -> None:
        """Send the PIN; raises RemoteAuthError on a wrong PIN, RemoteUnreachable if closed."""
        from androidtvremote2 import ConnectionClosed, InvalidAuth  # noqa: PLC0415

        try:
            async with asyncio.timeout(15):
                await self._api.async_finish_pairing(pin)
        except InvalidAuth as err:
            raise RemoteAuthError(str(err)) from err
        except (ConnectionClosed, TimeoutError) as err:
            raise RemoteUnreachable(str(err)) from err

    def close(self) -> None:
        """Close any open pairing connection."""
        self._api.disconnect()
