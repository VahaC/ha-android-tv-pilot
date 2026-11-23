"""Key vocabulary mapping."""

from __future__ import annotations

import pytest

from custom_components.android_tv_pilot.keys import (
    KEY_VOCABULARY,
    UnknownKeyError,
    adb_keyevent_command,
    resolve_key,
)

CONTRACT_KEYS = [
    "UP",
    "DOWN",
    "LEFT",
    "RIGHT",
    "CENTER",
    "BACK",
    "HOME",
    "MENU",
    "SETTINGS",
    "POWER",
    "WAKEUP",
    "SLEEP",
    "VOLUME_UP",
    "VOLUME_DOWN",
    "MUTE",
    "PLAY",
    "PAUSE",
    "PLAY_PAUSE",
    "STOP",
    "NEXT",
    "PREVIOUS",
    "REWIND",
    "FAST_FORWARD",
    "CHANNEL_UP",
    "CHANNEL_DOWN",
    "INFO",
    "GUIDE",
    "SEARCH",
    "ASSIST",
    "TV",
    "INPUT",
    "CAPTIONS",
    "DELETE",
    "ENTER",
    "TAB",
    "ESCAPE",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "RED",
    "GREEN",
    "YELLOW",
    "BLUE",
]


def test_vocabulary_matches_contract() -> None:
    assert set(KEY_VOCABULARY) == set(CONTRACT_KEYS)


def test_every_key_exists_in_remote_protocol() -> None:
    remotemessage = pytest.importorskip("androidtvremote2.remotemessage_pb2")
    for name in KEY_VOCABULARY:
        key = resolve_key(name)
        assert remotemessage.RemoteKeyCode.Value("KEYCODE_" + key.remote) >= 0, name


def test_remote_codes_equal_android_codes() -> None:
    """The remote protocol enum uses Android KeyEvent numbers; both maps must agree."""
    remotemessage = pytest.importorskip("androidtvremote2.remotemessage_pb2")
    for name in KEY_VOCABULARY:
        key = resolve_key(name)
        assert remotemessage.RemoteKeyCode.Value("KEYCODE_" + key.remote) == key.adb, name


@pytest.mark.parametrize(
    ("key", "remote", "adb"),
    [
        ("CENTER", "DPAD_CENTER", 23),
        ("center", "DPAD_CENTER", 23),
        ("MUTE", "VOLUME_MUTE", 164),
        ("0", "0", 7),
        ("9", "9", 16),
        ("KEYCODE_MEDIA_RECORD", "MEDIA_RECORD", "KEYCODE_MEDIA_RECORD"),
        ("130", 130, 130),
        (85, 85, 85),
    ],
)
def test_resolve(key: str | int, remote: str | int, adb: str | int) -> None:
    resolved = resolve_key(key)
    assert resolved.remote == remote
    assert resolved.adb == adb


@pytest.mark.parametrize("bad", ["JUMP", "KEYCODE_x;reboot", "KEYCODE_", "12345", "-1", "", -5])
def test_unknown(bad: str | int) -> None:
    with pytest.raises(UnknownKeyError):
        resolve_key(bad)


def test_adb_command() -> None:
    assert adb_keyevent_command(resolve_key("HOME")) == "input keyevent 3"
    assert adb_keyevent_command(resolve_key("CENTER"), longpress=True) == "input keyevent --longpress 23"
    assert adb_keyevent_command(resolve_key("KEYCODE_F1")) == "input keyevent KEYCODE_F1"


@pytest.mark.parametrize(
    ("name", "android_code"), [("KEYCODE_I", 37), ("KEYCODE_C", 31), ("KEYCODE_M", 41), ("KEYCODE_T", 48)]
)
def test_kodi_keycode_passthrough_both_transports(name: str, android_code: int) -> None:
    """Kodi shortcuts from the card: ``KEYCODE_I`` etc. work over the remote protocol and ADB."""
    remote_mod = pytest.importorskip("androidtvremote2.remote")
    key = resolve_key(name)
    # ADB: passed through by name
    assert adb_keyevent_command(key) == f"input keyevent {name}"

    # Remote protocol: run the real androidtvremote2 0.3.3 conversion on what we send.
    sent: list = []

    class _Proto:
        def _reset_idle_disconnect_task(self) -> None:
            pass

        def _send_message(self, msg) -> None:
            sent.append(msg)

    remote_mod.RemoteProtocol.send_key_command(_Proto(), key.remote, "SHORT")
    assert sent[0].remote_key_inject.key_code == android_code


def test_unknown_remote_key_raises_value_error_for_adb_fallback() -> None:
    """A KEYCODE_* the remote enum lacks raises ValueError, which makes the hub fall back to ADB."""
    remote_mod = pytest.importorskip("androidtvremote2.remote")

    class _Proto:
        def _reset_idle_disconnect_task(self) -> None:
            pass

        def _send_message(self, msg) -> None:
            raise AssertionError("must not send")

    with pytest.raises(ValueError):
        remote_mod.RemoteProtocol.send_key_command(_Proto(), resolve_key("KEYCODE_NOT_A_KEY").remote, "SHORT")
