"""Home Assistant level tests: setup, entities, services, websocket, screenshot, wake."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.android_tv_pilot.const import DOMAIN
from custom_components.android_tv_pilot.remote_client import RemoteUnreachable

from .fakes import PNG, FakeAdb

ENTRY_DATA = {
    "host": "192.0.2.10",
    "adb_port": 5555,
    "use_remote": False,
    "serial": "SERIAL123",
    "mac": "aa:bb:cc:dd:ee:ff",
    "manufacturer": "Xiaomi",
    "model": "MiTV-MSSP1",
    "sw_version": "Android 9",
}
MP = "media_player.living_room_tv"
REMOTE = "remote.living_room_tv"


@pytest.fixture(autouse=True)
def _fake_transports() -> AsyncGenerator[None]:
    FakeAdb.instances.clear()
    FakeAdb.online = False
    FakeAdb.screen_on = True
    FakeAdb.auth_fail = False
    FakeAdb.connect_calls = 0
    FakeAdb.responses = {}
    with (
        patch("custom_components.android_tv_pilot.AdbClient", FakeAdb),
        patch("custom_components.android_tv_pilot.ensure_adb_key"),
        patch("custom_components.android_tv_pilot.load_adb_signer", return_value=object()),
        patch("custom_components.android_tv_pilot.hub.RECONNECT_BACKOFF", (0.05,)),
    ):
        yield


async def _settle(hass: HomeAssistant) -> None:
    for _ in range(5):
        await asyncio.sleep(0.01)
        await hass.async_block_till_done()


async def _setup(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room TV",
        unique_id="SERIAL123",
        data=ENTRY_DATA,
        options=options or {"poll_interval": 5},
    )
    entry.add_to_hass(hass)
    if (wake := entry.options.get("wake_button")) and hass.states.get(wake) is None:
        hass.states.async_set(wake, "unknown")  # the wake entity exists
    assert await hass.config_entries.async_setup(entry.entry_id)
    await _settle(hass)
    return entry


async def _unload(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_tv_off_is_off_not_unavailable(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    state = hass.states.get(MP)
    assert state is not None
    assert state.state == "off"
    attrs = state.attributes
    assert attrs["entry_id"] == entry.entry_id
    assert attrs["power_state"] == "off"
    assert attrs["wake_state"] == "idle"
    assert attrs["wake_started_at"] is None
    assert attrs["wake_timeout"] == 40
    assert attrs["adb_connected"] is False
    assert attrs["remote_connected"] is False
    assert attrs["has_wake_button"] is False
    assert attrs["volume_entity"] is None
    assert hass.states.get(REMOTE).state == "off"

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call("media_player", "turn_on", {"entity_id": MP}, blocking=True)
    assert err.value.translation_key == "no_wake_button"
    await _unload(hass, entry)


async def test_tv_on_state_apps_and_commands(hass: HomeAssistant) -> None:
    FakeAdb.online = True
    entry = await _setup(hass)
    adb = FakeAdb.instances[-1]

    state = hass.states.get(MP)
    assert state.state == "playing"
    assert state.attributes["power_state"] == "on"
    assert state.attributes["app_id"] == "com.google.android.youtube.tv"
    assert state.attributes["app_name"] == "YouTube"
    assert state.attributes["source"] == "YouTube"
    assert state.attributes["source_list"] == ["Netflix", "YouTube"]
    assert state.attributes["volume_level"] == pytest.approx(6 / 15)
    assert hass.states.get(REMOTE).attributes["activity_list"] == ["Netflix", "YouTube"]

    await hass.services.async_call(DOMAIN, "send_key", {"entity_id": MP, "key": "CENTER"}, blocking=True)
    assert adb.commands[-1] == "input keyevent 23"
    await hass.services.async_call(
        DOMAIN, "send_key", {"entity_id": REMOTE, "key": "HOME", "action": "long"}, blocking=True
    )
    assert adb.commands[-1] == "input keyevent --longpress 3"

    await hass.services.async_call(
        "remote", "send_command", {"entity_id": REMOTE, "command": ["UP", "DOWN"]}, blocking=True
    )
    assert adb.commands[-2:] == ["input keyevent 19", "input keyevent 20"]

    await hass.services.async_call(DOMAIN, "send_text", {"entity_id": MP, "text": "hi there"}, blocking=True)
    assert adb.commands[-1] == "input text 'hi%sthere'"
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN, "send_text", {"entity_id": MP, "text": "Привіт"}, blocking=True
        )
    assert err.value.translation_key == "non_ascii_text"

    await hass.services.async_call(
        "media_player", "select_source", {"entity_id": MP, "source": "Netflix"}, blocking=True
    )
    assert adb.commands[-1] == "monkey -p 'com.netflix.ninja' -c android.intent.category.LEANBACK_LAUNCHER 1"

    await hass.services.async_call(
        DOMAIN, "open_url", {"entity_id": MP, "url": "https://youtu.be/x"}, blocking=True
    )
    assert "am start -a android.intent.action.VIEW -d 'https://youtu.be/x'" in adb.commands

    response = await hass.services.async_call(
        DOMAIN,
        "adb_command",
        {"entity_id": MP, "command": "getprop ro.product.model"},
        blocking=True,
        return_response=True,
    )
    assert response == {"output": "MiTV-MSSP1\n"}

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(DOMAIN, "send_key", {"entity_id": MP, "key": "JUMP"}, blocking=True)
    assert err.value.translation_key == "unknown_key"

    await hass.services.async_call("media_player", "turn_off", {"entity_id": MP}, blocking=True)
    assert adb.commands[-1] == "input keyevent 223"
    assert hass.states.get(MP).state == "off"
    assert hass.states.get(MP).attributes["power_state"] == "asleep"

    await _unload(hass, entry)


async def test_turn_on_from_asleep_sends_wakeup(hass: HomeAssistant) -> None:
    FakeAdb.online = True
    FakeAdb.screen_on = False
    entry = await _setup(hass)
    assert hass.states.get(MP).attributes["power_state"] == "asleep"
    await hass.services.async_call("media_player", "turn_on", {"entity_id": MP}, blocking=True)
    assert "input keyevent 224" in FakeAdb.instances[-1].commands
    await _settle(hass)
    assert hass.states.get(MP).attributes["power_state"] == "on"
    await _unload(hass, entry)


async def test_turn_on_from_deep_standby_presses_wake_button(hass: HomeAssistant) -> None:
    presses: list[ServiceCall] = []

    async def press(call: ServiceCall) -> None:
        presses.append(call)
        FakeAdb.online = True  # the BLE wake brought the TV back
        FakeAdb.screen_on = True

    hass.services.async_register("button", "press", press)
    entry = await _setup(
        hass, {"wake_button": "button.wake_the_tv", "wake_timeout": 10, "repress_interval": 8}
    )
    assert hass.states.get(MP).attributes["has_wake_button"] is True
    await hass.services.async_call("media_player", "turn_on", {"entity_id": MP}, blocking=True)
    assert len(presses) == 1
    assert presses[0].data["entity_id"] == "button.wake_the_tv"
    await _settle(hass)
    state = hass.states.get(MP)
    assert state.attributes["wake_state"] == "idle"
    assert state.attributes["power_state"] == "on"
    await _unload(hass, entry)


async def test_wake_timeout_marks_failed(hass: HomeAssistant) -> None:
    async def press(call: ServiceCall) -> None:
        return None  # the TV never answers

    hass.services.async_register("button", "press", press)
    entry = await _setup(
        hass, {"wake_button": "button.wake_the_tv", "wake_timeout": 1, "repress_interval": 1}
    )
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call("media_player", "turn_on", {"entity_id": MP}, blocking=True)
    assert err.value.translation_key == "wake_timeout"
    assert hass.states.get(MP).attributes["wake_state"] == "failed"
    await _unload(hass, entry)


async def test_websocket_api_and_screenshot(hass: HomeAssistant, hass_ws_client, hass_client) -> None:
    FakeAdb.online = True
    entry = await _setup(hass)
    adb = FakeAdb.instances[-1]
    ws = await hass_ws_client(hass)

    await ws.send_json({"id": 1, "type": f"{DOMAIN}/apps", "entry_id": entry.entry_id})
    msg = await ws.receive_json()
    assert msg["success"], msg
    apps = msg["result"]["apps"]
    assert [a["package"] for a in apps] == ["com.netflix.ninja", "com.google.android.youtube.tv"]
    assert apps[1] == {
        "package": "com.google.android.youtube.tv",
        "label": "YouTube",
        "color": "#FF0000",
        "icon": "mdi:youtube",
        "icon_url": None,
        "hidden": False,
        "system": True,
    }

    await ws.send_json(
        {"id": 2, "type": f"{DOMAIN}/send_key", "entry_id": entry.entry_id, "key": "LEFT", "action": "press"}
    )
    msg = await ws.receive_json()
    assert msg["success"] and msg["result"] == {}
    assert adb.commands[-1] == "input keyevent 21"

    await ws.send_json({"id": 3, "type": f"{DOMAIN}/send_key", "entry_id": "nope", "key": "LEFT"})
    msg = await ws.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"

    await ws.send_json({"id": 4, "type": f"{DOMAIN}/send_key", "entry_id": entry.entry_id, "key": "JUMP"})
    msg = await ws.receive_json()
    assert msg["error"]["code"] == "not_found"

    await ws.send_json({"id": 5, "type": f"{DOMAIN}/send_text", "entry_id": entry.entry_id, "text": "Ї"})
    msg = await ws.receive_json()
    assert msg["error"]["code"] == "unsupported"

    await ws.send_json(
        {"id": 6, "type": f"{DOMAIN}/launch_app", "entry_id": entry.entry_id, "package": "com.netflix.ninja"}
    )
    assert (await ws.receive_json())["success"]

    await ws.send_json(
        {"id": 7, "type": f"{DOMAIN}/open_url", "entry_id": entry.entry_id, "url": "https://example.com"}
    )
    assert (await ws.receive_json())["success"]

    await ws.send_json({"id": 8, "type": f"{DOMAIN}/screenshot_url", "entry_id": entry.entry_id})
    msg = await ws.receive_json()
    assert msg["success"], msg
    url = msg["result"]["url"]
    assert url.startswith(f"/api/android_tv_pilot/screenshot/{entry.entry_id}?authSig=")

    client = await hass_client()
    resp = await client.get(url)
    assert resp.status == 200
    assert resp.headers["Content-Type"] == "image/png"
    assert await resp.read() == PNG
    # second request within 2 s is served from the cache
    await client.get(f"/api/android_tv_pilot/screenshot/{entry.entry_id}")
    assert adb.commands.count("screencap -p") == 1

    await _unload(hass, entry)


async def test_websocket_tv_unreachable(hass: HomeAssistant, hass_ws_client) -> None:
    entry = await _setup(hass)
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": f"{DOMAIN}/send_key", "entry_id": entry.entry_id, "key": "UP"})
    msg = await ws.receive_json()
    assert msg["error"]["code"] == "tv_unreachable"
    await _unload(hass, entry)


async def test_options_overrides_apply_live(hass: HomeAssistant) -> None:
    FakeAdb.online = True
    entry = await _setup(hass)
    hass.config_entries.async_update_entry(
        entry,
        options={**entry.options, "app_overrides": {"com.netflix.ninja": {"label": "Кіно", "hidden": False}}},
    )
    await _settle(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert "Кіно" in hass.states.get(MP).attributes["source_list"]
    await _unload(hass, entry)


class FakeRemote:
    """Stands in for ``RemoteClient`` (paired remote protocol)."""

    def __init__(self, host, certfile, keyfile, *, on_update, on_invalid_auth) -> None:
        self.on_update = on_update
        self.available = False
        self.is_on: bool | None = None
        self.current_app: str | None = None
        self.volume_level = self.volume_max = self.volume_muted = None
        self.keys: list[tuple] = []
        self.texts: list[str] = []

    @property
    def connected(self) -> bool:
        return self.available

    async def async_connect(self, timeout: float = 5.0) -> None:
        self.available = True
        self.is_on = True
        self.current_app = "com.netflix.ninja"
        self.on_update()

    def disconnect(self) -> None:
        self.available = False

    def send_key(self, key, direction="SHORT") -> None:
        if key == "NOT_A_REMOTE_KEY":
            raise ValueError(key)
        self.keys.append((key, direction))

    def send_text(self, text: str) -> None:
        self.texts.append(text)

    def send_launch(self, link: str) -> None:
        self.keys.append(("launch", link))


async def test_remote_protocol_is_preferred(hass: HomeAssistant) -> None:
    remotes: list[FakeRemote] = []

    def factory(*args, **kwargs) -> FakeRemote:
        remotes.append(FakeRemote(*args, **kwargs))
        return remotes[-1]

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room TV",
        unique_id="SERIAL123",
        data={**ENTRY_DATA, "use_remote": True},
        options={},
    )
    entry.add_to_hass(hass)
    with (
        patch("custom_components.android_tv_pilot.RemoteClient", side_effect=factory),
        patch("custom_components.android_tv_pilot.ensure_remote_cert"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await _settle(hass)
    remote = remotes[0]
    state = hass.states.get(MP)
    assert state.attributes["remote_connected"] is True
    assert state.attributes["adb_connected"] is False
    assert state.attributes["power_state"] == "on"
    assert state.attributes["app_id"] == "com.netflix.ninja"

    await hass.services.async_call(DOMAIN, "send_key", {"entity_id": MP, "key": "UP"}, blocking=True)
    assert remote.keys[-1] == ("DPAD_UP", "SHORT")
    with patch("custom_components.android_tv_pilot.hub.LONG_PRESS_SECONDS", 0.01):
        await hass.services.async_call(
            DOMAIN, "send_key", {"entity_id": MP, "key": "CENTER", "action": "long"}, blocking=True
        )
    assert remote.keys[-2:] == [("DPAD_CENTER", "START_LONG"), ("DPAD_CENTER", "END_LONG")]
    await hass.services.async_call(
        DOMAIN, "send_text", {"entity_id": MP, "text": "Привіт", "enter": True}, blocking=True
    )
    assert remote.texts == ["Привіт"]
    assert remote.keys[-1] == ("ENTER", "SHORT")
    await hass.services.async_call(
        DOMAIN, "launch_app", {"entity_id": MP, "package": "org.xbmc.kodi"}, blocking=True
    )
    assert remote.keys[-1] == ("launch", "org.xbmc.kodi")
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN, "adb_command", {"entity_id": MP, "command": "ls"}, blocking=True, return_response=True
        )
    assert err.value.translation_key == "adb_required"

    await hass.services.async_call("media_player", "turn_off", {"entity_id": MP}, blocking=True)
    assert remote.keys[-1] == ("POWER", "SHORT")
    await _unload(hass, entry)


async def test_adb_auth_timeouts_start_reauth_once_and_back_off(hass: HomeAssistant) -> None:
    """Revoked authorisation: the TV keeps prompting; after 2 timeouts reauth starts once, then back off."""
    FakeAdb.online = True
    FakeAdb.auth_fail = True
    entry = await _setup(hass)  # attempt 1 (warning, 60 s backoff)
    hub = entry.runtime_data
    assert FakeAdb.connect_calls == 1
    for _ in range(5):  # backoff: kicks do not re-prompt the TV
        hub.kick()
        await _settle(hass)
    assert FakeAdb.connect_calls == 1
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    hub._auth_backoff_until = 0  # backoff elapsed
    hub.kick()
    await _settle(hass)
    assert FakeAdb.connect_calls == 2
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"

    hub._auth_backoff_until = 0
    hub.kick()
    await _settle(hass)
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1  # started once
    await _unload(hass, entry)


async def test_failed_wake_is_cleared_when_tv_becomes_reachable(hass: HomeAssistant) -> None:
    async def press(call: ServiceCall) -> None:
        return None

    hass.services.async_register("button", "press", press)
    entry = await _setup(
        hass, {"wake_button": "button.wake_the_tv", "wake_timeout": 1, "repress_interval": 1}
    )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("media_player", "turn_on", {"entity_id": MP}, blocking=True)
    assert hass.states.get(MP).attributes["wake_state"] == "failed"
    FakeAdb.online = True  # the user turned the TV on with its own remote
    entry.runtime_data.kick()
    await _settle(hass)
    assert hass.states.get(MP).attributes["wake_state"] == "idle"
    assert hass.states.get(MP).attributes["power_state"] == "on"
    await _unload(hass, entry)


async def test_unload_during_wake_gives_wake_cancelled(hass: HomeAssistant) -> None:
    async def press(call: ServiceCall) -> None:
        return None

    hass.services.async_register("button", "press", press)
    entry = await _setup(
        hass, {"wake_button": "button.wake_the_tv", "wake_timeout": 120, "repress_interval": 60}
    )
    call = hass.async_create_task(
        hass.services.async_call("media_player", "turn_on", {"entity_id": MP}, blocking=True)
    )
    await asyncio.sleep(0.05)
    assert hass.states.get(MP).attributes["wake_state"] == "waking"
    assert hass.states.get(MP).attributes["power_state"] == "waking"
    await _unload(hass, entry)
    with pytest.raises(HomeAssistantError) as err:
        await call
    assert err.value.translation_key == "wake_cancelled"


async def test_remote_turn_on_with_activity_after_cold_start(hass: HomeAssistant) -> None:
    async def press(call: ServiceCall) -> None:
        FakeAdb.online = True

    hass.services.async_register("button", "press", press)
    entry = await _setup(hass, {"wake_button": "button.wake_the_tv"})
    hub = entry.runtime_data
    assert hub.apps == []
    await hass.services.async_call(
        "remote", "turn_on", {"entity_id": REMOTE, "activity": "YouTube"}, blocking=True
    )
    assert (
        "monkey -p 'com.google.android.youtube.tv' -c android.intent.category.LEANBACK_LAUNCHER 1"
        in FakeAdb.instances[-1].commands
    )
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "media_player", "select_source", {"entity_id": MP, "source": "No Such App"}, blocking=True
        )
    assert err.value.translation_key == "unknown_app"
    await _unload(hass, entry)


async def test_volume_set_uses_adb_scale_and_checks_output(hass: HomeAssistant) -> None:
    FakeAdb.online = True
    entry = await _setup(hass)
    hub = entry.runtime_data
    adb = FakeAdb.instances[-1]
    # the remote protocol reported a 0..100 scale; ADB STREAM_MUSIC is 0..15
    hub.state.remote_volume_level, hub.state.remote_volume_max = 50, 100
    await hass.services.async_call(
        "media_player", "volume_set", {"entity_id": MP, "volume_level": 0.5}, blocking=True
    )
    assert adb.commands[-1] == "media volume --stream 3 --set 8 2>&1"
    assert hub.state.adb_volume_level == 8

    FakeAdb.responses = {
        "media volume --stream 3 --set 3 2>&1": "/system/bin/sh: media: not found\n",
        "cmd media_session volume --stream 3 --set 3 2>&1": "",
    }
    await hass.services.async_call(
        "media_player", "volume_set", {"entity_id": MP, "volume_level": 0.2}, blocking=True
    )
    assert adb.commands[-1] == "cmd media_session volume --stream 3 --set 3 2>&1"
    assert hub.state.adb_volume_level == 3

    FakeAdb.responses = {
        "media volume --stream 3 --set 15 2>&1": "Error: bad stream\n",
        "cmd media_session volume --stream 3 --set 15 2>&1": "Unknown command: volume\n",
    }
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "media_player", "volume_set", {"entity_id": MP, "volume_level": 1.0}, blocking=True
        )
    assert err.value.translation_key == "volume_set_failed"
    assert hub.state.adb_volume_level == 3  # unchanged on error
    await _unload(hass, entry)


async def test_adb_command_is_admin_only(hass: HomeAssistant, hass_read_only_user, hass_admin_user) -> None:
    FakeAdb.online = True
    entry = await _setup(hass)
    data = {"entity_id": MP, "command": "getprop ro.product.model"}
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "adb_command",
            data,
            blocking=True,
            return_response=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    response = await hass.services.async_call(
        DOMAIN,
        "adb_command",
        data,
        blocking=True,
        return_response=True,
        context=Context(user_id=hass_admin_user.id),
    )
    assert response == {"output": "MiTV-MSSP1\n"}
    await _unload(hass, entry)


async def test_kodi_keycodes_over_adb(hass: HomeAssistant, hass_ws_client) -> None:
    FakeAdb.online = True
    entry = await _setup(hass)
    ws = await hass_ws_client(hass)
    for i, name in enumerate(("KEYCODE_I", "KEYCODE_C", "KEYCODE_M", "KEYCODE_T"), start=1):
        await ws.send_json({"id": i, "type": f"{DOMAIN}/send_key", "entry_id": entry.entry_id, "key": name})
        assert (await ws.receive_json())["success"]
        assert FakeAdb.instances[-1].commands[-1] == f"input keyevent {name}"
    await _unload(hass, entry)


async def test_key_repeat_lifecycle(hass: HomeAssistant, hass_ws_client) -> None:
    FakeAdb.online = True
    with (
        patch("custom_components.android_tv_pilot.hub.REPEAT_DELAY", 0.02),
        patch("custom_components.android_tv_pilot.hub.REPEAT_INTERVAL", 0.01),
    ):
        entry = await _setup(hass)
        hub = entry.runtime_data
        adb = FakeAdb.instances[-1]
        ws = await hass_ws_client(hass)

        async def send(msg_id: int, key: str, action: str) -> None:
            await ws.send_json(
                {
                    "id": msg_id,
                    "type": f"{DOMAIN}/send_key",
                    "entry_id": entry.entry_id,
                    "key": key,
                    "action": action,
                }
            )
            assert (await ws.receive_json())["success"]

        await send(1, "RIGHT", "up")  # up without an active repeat: silent no-op
        assert hub.repeating_key is None

        await send(2, "RIGHT", "down")
        await asyncio.sleep(0.1)
        assert adb.commands.count("input keyevent 22") >= 3
        assert hub.repeating_key == "RIGHT"
        await send(3, "LEFT", "up")  # up for another key does not stop it
        assert hub.repeating_key == "RIGHT"
        await send(4, "RIGHT", "down")  # a second down restarts cleanly
        assert hub.repeating_key == "RIGHT"
        await send(5, "RIGHT", "up")
        assert hub.repeating_key is None
        count = adb.commands.count("input keyevent 22")
        await asyncio.sleep(0.05)
        assert adb.commands.count("input keyevent 22") == count

        await send(6, "HOME", "down")  # non-repeatable key: single press
        assert hub.repeating_key is None

        await send(7, "DOWN", "down")  # websocket disconnect stops its repeat
        assert hub.repeating_key == "DOWN"
        await ws.close()
        await _settle(hass)
        assert hub.repeating_key is None

        await hub.async_send_key("UP", "down")  # TV becoming unreachable stops it
        assert hub.repeating_key == "UP"
        FakeAdb.online = False
        await adb.async_close()
        hub.kick()
        await _settle(hass)
        assert hub.repeating_key is None

        FakeAdb.online = True  # unload stops it
        hub.kick()
        await _settle(hass)
        await hub.async_send_key("UP", "down")
        assert hub.repeating_key == "UP"
        await _unload(hass, entry)
        assert hub.repeating_key is None


async def test_kodi_keycodes_and_repeat_over_remote_protocol(hass: HomeAssistant) -> None:
    remotes: list[FakeRemote] = []

    def factory(*args, **kwargs) -> FakeRemote:
        remotes.append(FakeRemote(*args, **kwargs))
        return remotes[-1]

    entry = MockConfigEntry(
        domain=DOMAIN, title="Living room TV", unique_id="SERIAL123", data={**ENTRY_DATA, "use_remote": True}
    )
    entry.add_to_hass(hass)
    with (
        patch("custom_components.android_tv_pilot.RemoteClient", side_effect=factory),
        patch("custom_components.android_tv_pilot.ensure_remote_cert"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await _settle(hass)
    remote = remotes[0]
    for name, sent in (("KEYCODE_I", "I"), ("KEYCODE_C", "C"), ("KEYCODE_M", "M"), ("KEYCODE_T", "T")):
        await hass.services.async_call(DOMAIN, "send_key", {"entity_id": MP, "key": name}, blocking=True)
        assert remote.keys[-1] == (sent, "SHORT")
    await _unload(hass, entry)


async def test_poll_never_waits_for_remote_reconnect(hass: HomeAssistant) -> None:
    """ADB up, remote port down: the poll loop must not block on remote connect attempts."""
    FakeAdb.online = True
    calls: list[float] = []

    class SlowRemote(FakeRemote):
        async def async_connect(self, timeout: float = 5.0) -> None:
            calls.append(timeout)
            await asyncio.sleep(timeout)
            raise RemoteUnreachable("port closed")

    entry = MockConfigEntry(
        domain=DOMAIN, title="Living room TV", unique_id="SERIAL123", data={**ENTRY_DATA, "use_remote": True}
    )
    entry.add_to_hass(hass)
    with (
        patch("custom_components.android_tv_pilot.RemoteClient", SlowRemote),
        patch("custom_components.android_tv_pilot.ensure_remote_cert"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await _settle(hass)
    hub = entry.runtime_data
    loop = asyncio.get_running_loop()
    start = loop.time()
    assert await hub._async_ensure_connected() is True
    assert loop.time() - start < 0.5
    assert calls == [4.0]  # only the background remote task tried
    await _unload(hass, entry)
