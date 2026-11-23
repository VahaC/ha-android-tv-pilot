"""RemoteClient wrapper against a fake androidtvremote2.AndroidTVRemote."""

from __future__ import annotations

from unittest.mock import patch

import pytest

androidtvremote2 = pytest.importorskip("androidtvremote2")

from custom_components.android_tv_pilot import remote_client
from custom_components.android_tv_pilot.remote_client import (
    RemoteAuthError,
    RemoteClient,
    RemoteUnreachable,
)


class FakeApi:
    """Mimics the subset of AndroidTVRemote 0.3.3 that RemoteClient uses."""

    def __init__(self, fail: Exception | None = None) -> None:
        self.fail = fail
        self.is_on = True
        self.current_app = "com.netflix.ninja"
        self.volume_info = {"level": 7, "max": 100, "muted": False}
        self.device_info = {"manufacturer": "Xiaomi", "model": "MiTV", "sw_version": "9"}
        self.callbacks: dict[str, object] = {}
        self.keys: list[tuple] = []
        self.texts: list[str] = []
        self.launched: list[str] = []
        self.reconnecting = False
        self.disconnects = 0

    def add_is_on_updated_callback(self, cb) -> None:
        self.callbacks["is_on"] = cb

    def add_current_app_updated_callback(self, cb) -> None:
        self.callbacks["app"] = cb

    def add_volume_info_updated_callback(self, cb) -> None:
        self.callbacks["volume"] = cb

    def add_is_available_updated_callback(self, cb) -> None:
        self.callbacks["available"] = cb

    async def async_connect(self) -> None:
        if self.fail:
            raise self.fail

    def keep_reconnecting(self, invalid_auth_callback=None) -> None:
        self.reconnecting = True
        self.callbacks["invalid_auth"] = invalid_auth_callback

    def disconnect(self) -> None:
        self.disconnects += 1

    def send_key_command(self, key, direction="SHORT") -> None:
        self.keys.append((key, direction))

    def send_text(self, text: str) -> None:
        self.texts.append(text)

    def send_launch_app_command(self, link: str) -> None:
        self.launched.append(link)


def make(api: FakeApi) -> tuple[RemoteClient, list[str]]:
    events: list[str] = []
    client = RemoteClient(
        "192.0.2.10",
        "cert.pem",
        "key.pem",
        on_update=lambda: events.append("update"),
        on_invalid_auth=lambda: events.append("invalid_auth"),
    )
    return client, events


async def test_connect_and_push_updates() -> None:
    api = FakeApi()
    with patch.object(remote_client, "create_remote", return_value=api):
        client, events = make(api)
        await client.async_connect()
    assert client.connected
    assert (client.is_on, client.current_app, client.volume_level, client.volume_max) == (
        True,
        "com.netflix.ninja",
        7,
        100,
    )
    assert api.reconnecting
    api.callbacks["is_on"](False)
    api.callbacks["app"]("com.google.android.youtube.tv")
    api.callbacks["volume"]({"level": 3, "max": 100, "muted": True})
    assert (client.is_on, client.current_app, client.volume_muted) == (
        False,
        "com.google.android.youtube.tv",
        True,
    )
    api.callbacks["available"](False)
    assert not client.connected
    api.callbacks["invalid_auth"]()
    assert "invalid_auth" in events


async def test_send_key_text_launch() -> None:
    api = FakeApi()
    with patch.object(remote_client, "create_remote", return_value=api):
        client, _ = make(api)
        await client.async_connect()
    client.send_key("DPAD_CENTER")
    client.send_key("DPAD_CENTER", "START_LONG")
    client.send_text("Привіт")
    client.send_launch("com.netflix.ninja")
    assert api.keys == [("DPAD_CENTER", "SHORT"), ("DPAD_CENTER", "START_LONG")]
    assert api.texts == ["Привіт"]
    assert api.launched == ["com.netflix.ninja"]


async def test_errors_are_mapped() -> None:
    api = FakeApi(fail=androidtvremote2.InvalidAuth("need to pair"))
    with patch.object(remote_client, "create_remote", return_value=api):
        client, _ = make(api)
        with pytest.raises(RemoteAuthError):
            await client.async_connect()
        api.fail = androidtvremote2.CannotConnect("no route")
        with pytest.raises(RemoteUnreachable):
            await client.async_connect()
    assert api.disconnects == 1  # the second attempt stopped the old reconnect loop first
    with pytest.raises(RemoteUnreachable):
        client.send_key("HOME")


def test_real_library_has_the_methods_we_use() -> None:
    cls = androidtvremote2.AndroidTVRemote
    for name in (
        "async_connect",
        "keep_reconnecting",
        "disconnect",
        "async_start_pairing",
        "async_finish_pairing",
        "send_key_command",
        "send_text",
        "send_launch_app_command",
        "add_is_on_updated_callback",
        "add_current_app_updated_callback",
        "add_volume_info_updated_callback",
        "add_is_available_updated_callback",
    ):
        assert callable(getattr(cls, name)), name
