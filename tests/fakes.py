"""Fake transports for Home Assistant level tests."""

from __future__ import annotations

from custom_components.android_tv_pilot.adb import SECTION_MARK, AdbAuthTimeout, AdbUnreachable

POLL_AWAKE_YOUTUBE = (
    f"{SECTION_MARK}POWER\n  mWakefulness=Awake\n"
    f"{SECTION_MARK}WINDOW\n"
    "  mCurrentFocus=Window{3c1a0e5 u0 com.google.android.youtube.tv/"
    "com.google.android.apps.youtube.tv.activity.ShellActivity}\n"
    f"{SECTION_MARK}ACTIVITY\n"
    f"{SECTION_MARK}MEDIA\n"
    "      package=com.google.android.youtube.tv\n      active=true\n"
    "      state=PlaybackState {state=3, position=1, buffered position=0, speed=1.0}\n"
    f"{SECTION_MARK}AUDIO\n- STREAM_MUSIC:\n   Muted: false\n   Max: 15\n"
    "   Current: 400 (hdmi): 6\n   Devices: hdmi\n"
    f"{SECTION_MARK}END\n"
)

POLL_ASLEEP = (
    f"{SECTION_MARK}POWER\n  mWakefulness=Asleep\n"
    f"{SECTION_MARK}WINDOW\n  mCurrentFocus=null\n"
    f"{SECTION_MARK}ACTIVITY\n{SECTION_MARK}MEDIA\n{SECTION_MARK}AUDIO\n{SECTION_MARK}END\n"
)

APPS_OUTPUT = (
    f"{SECTION_MARK}LEANBACK\n"
    "2 activities found:\n  Activity #0:\n    priority=0\n"
    "    com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity\n"
    "  Activity #1:\n    priority=0\n    com.netflix.ninja/.MainActivity\n"
    f"{SECTION_MARK}LAUNCHER\n"
    f"{SECTION_MARK}SYSTEM\npackage:com.google.android.youtube.tv\n"
    f"{SECTION_MARK}THIRD\npackage:com.netflix.ninja\n"
    f"{SECTION_MARK}END\n"
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


class FakeAdb:
    """Stands in for ``AdbClient``."""

    instances: list[FakeAdb] = []
    online = False
    screen_on = True
    auth_fail = False
    connect_calls = 0
    responses: dict[str, str] = {}

    def __init__(self, host: str, port: int, signer: object, **kwargs: object) -> None:
        self.host = host
        self.port = port
        self._connected = False
        self.auth_prompted = False
        self.commands: list[str] = []
        FakeAdb.instances.append(self)

    @property
    def connected(self) -> bool:
        return self._connected

    async def async_connect(self, **kwargs: object) -> None:
        FakeAdb.connect_calls += 1
        if not FakeAdb.online:
            raise AdbUnreachable("timeout")
        if FakeAdb.auth_fail:
            self.auth_prompted = True
            raise AdbAuthTimeout("prompt not accepted")
        self._connected = True

    async def async_close(self) -> None:
        self._connected = False

    async def async_shell(self, command: str, timeout: float = 10.0) -> str:
        if not self._connected:
            raise AdbUnreachable("not connected")
        self.commands.append(command)
        if command in FakeAdb.responses:
            return FakeAdb.responses[command]
        if command.startswith("echo @@ATVP:POWER"):
            return POLL_AWAKE_YOUTUBE if FakeAdb.screen_on else POLL_ASLEEP
        if command.startswith("echo @@ATVP:LEANBACK"):
            return APPS_OUTPUT
        if command.startswith("monkey"):
            return "Events injected: 1\n"
        if command.startswith("am start"):
            return "Starting: Intent { act=android.intent.action.VIEW }\n"
        if command == "input keyevent 224":
            FakeAdb.screen_on = True
        if command == "input keyevent 223":
            FakeAdb.screen_on = False
        if command == "getprop ro.product.model":
            return "MiTV-MSSP1\n"
        return ""

    async def async_exec_out(self, command: str, timeout: float = 15.0) -> bytes:
        if not self._connected:
            raise AdbUnreachable("not connected")
        self.commands.append(command)
        return PNG
