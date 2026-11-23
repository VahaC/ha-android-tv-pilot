"""ADB over TCP: client wrapper, shell command builders and pure output parsers.

Everything above the ``AdbClient`` class is pure (no I/O, no Home Assistant) and is
unit-tested with real-world outputs from Android 9 (Xiaomi Mi TV / MediaTek) and
Android TV 11/12.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
import logging
import os
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shell quoting and validation
# ---------------------------------------------------------------------------

_PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")
# Characters `input text` handles without help (besides letters/digits).
_INPUT_TEXT_SAFE = re.compile(r"^[\x20-\x7e]*$")


class UnsafeArgumentError(ValueError):
    """Raised when an argument cannot be passed to the TV safely."""


class NonAsciiTextError(ValueError):
    """Raised when text cannot be typed through ``adb shell input text``."""


def shell_quote(value: str) -> str:
    """Quote one argument for the Android (mksh/toybox) POSIX shell.

    Every shell argument that comes from a user or the card goes through here.
    """
    if "\x00" in value:
        raise UnsafeArgumentError("NUL byte in shell argument")
    if value == "":
        return "''"
    return "'" + value.replace("'", "'\"'\"'") + "'"


def validate_package(package: str) -> str:
    """Return the package name if it is a syntactically valid Android package."""
    package = package.strip()
    if not _PACKAGE_RE.match(package):
        raise UnsafeArgumentError(f"Invalid package name: {package!r}")
    return package


def is_ascii_text(text: str) -> bool:
    """Return True if ``input text`` can type the text."""
    return bool(_INPUT_TEXT_SAFE.match(text))


def input_text_command(text: str) -> str:
    """Build an ``input text`` command.

    ``input text`` turns ``%s`` into a space and cannot type non-ASCII characters,
    so spaces become ``%s`` and the whole value is shell-quoted.
    """
    if not text:
        raise ValueError("empty text")
    if not is_ascii_text(text):
        raise NonAsciiTextError(text)
    return "input text " + shell_quote(text.replace(" ", "%s"))


def launch_app_commands(package: str) -> list[str]:
    """Commands to launch an app: leanback launcher category first, then launcher."""
    pkg = shell_quote(validate_package(package))
    return [
        f"monkey -p {pkg} -c android.intent.category.LEANBACK_LAUNCHER 1",
        f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1",
    ]


def open_url_command(url: str, package: str | None = None) -> str:
    """Build an ``am start`` VIEW intent for a URL or deep link."""
    url = url.strip()
    if not url or not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", url):
        raise UnsafeArgumentError(f"Not a URL: {url!r}")
    cmd = f"am start -a android.intent.action.VIEW -d {shell_quote(url)}"
    if package:
        cmd += " " + shell_quote(validate_package(package))
    return cmd


def monkey_succeeded(output: str) -> bool:
    """Return True if ``monkey`` actually injected the launch event."""
    lowered = output.lower()
    return "no activities found" not in lowered and "aborted" not in lowered


def am_start_succeeded(output: str) -> bool:
    """Return True if ``am start`` resolved the intent."""
    return "Error:" not in output and "Exception" not in output


# ---------------------------------------------------------------------------
# Combined poll command
# ---------------------------------------------------------------------------

SECTION_MARK = "@@ATVP:"

POLL_COMMAND = " ; ".join(
    [
        f"echo {SECTION_MARK}POWER",
        "dumpsys power 2>/dev/null | grep -E 'mWakefulness=|Display Power: state='",
        f"echo {SECTION_MARK}WINDOW",
        "dumpsys window windows 2>/dev/null | grep -E 'mCurrentFocus|mFocusedApp'",
        f"echo {SECTION_MARK}ACTIVITY",
        "dumpsys activity activities 2>/dev/null | grep -E 'mResumedActivity|ResumedActivity' | head -n 3",
        f"echo {SECTION_MARK}MEDIA",
        "dumpsys media_session 2>/dev/null | grep -E 'package=|active=|state=PlaybackState'",
        f"echo {SECTION_MARK}AUDIO",
        "dumpsys audio 2>/dev/null | grep -A 8 -- '- STREAM_MUSIC:'",
        f"echo {SECTION_MARK}END",
    ]
)

APPS_COMMAND = " ; ".join(
    [
        f"echo {SECTION_MARK}LEANBACK",
        "cmd package query-activities --brief -a android.intent.action.MAIN"
        " -c android.intent.category.LEANBACK_LAUNCHER 2>/dev/null",
        f"echo {SECTION_MARK}LAUNCHER",
        "cmd package query-activities --brief -a android.intent.action.MAIN"
        " -c android.intent.category.LAUNCHER 2>/dev/null",
        f"echo {SECTION_MARK}SYSTEM",
        "pm list packages -s 2>/dev/null",
        f"echo {SECTION_MARK}THIRD",
        "pm list packages -3 2>/dev/null",
        f"echo {SECTION_MARK}END",
    ]
)

DEVICE_INFO_COMMAND = " ; ".join(
    [
        "echo serial=$(getprop ro.serialno)",
        "echo manufacturer=$(getprop ro.product.manufacturer)",
        "echo model=$(getprop ro.product.model)",
        "echo release=$(getprop ro.build.version.release)",
        "echo eth=$(cat /sys/class/net/eth0/address 2>/dev/null)",
        "echo wlan=$(cat /sys/class/net/wlan0/address 2>/dev/null)",
    ]
)


def split_sections(output: str) -> dict[str, str]:
    """Split combined command output into ``{SECTION: text}``."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith(SECTION_MARK):
            current = stripped[len(SECTION_MARK) :]
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FocusInfo:
    """Focused app and activity."""

    package: str | None = None
    activity: str | None = None


@dataclass(slots=True)
class VolumeInfo:
    """STREAM_MUSIC volume."""

    level: int | None = None
    max: int | None = None
    muted: bool | None = None


@dataclass(slots=True)
class MediaSession:
    """One media session from ``dumpsys media_session``."""

    package: str
    active: bool = False
    state: int | None = None


@dataclass(slots=True)
class PollResult:
    """Parsed result of one poll cycle."""

    wakefulness: str | None = None
    screen_on: bool | None = None
    focus: FocusInfo = field(default_factory=FocusInfo)
    playback: str | None = None  # "playing" | "paused" | "idle" | None
    volume: VolumeInfo = field(default_factory=VolumeInfo)


@dataclass(slots=True)
class AppsResult:
    """Parsed result of the app discovery command."""

    launchable: list[str]
    system: set[str]
    used_fallback: bool


@dataclass(slots=True)
class DeviceInfoResult:
    """Identity of the TV."""

    serial: str | None
    manufacturer: str | None
    model: str | None
    release: str | None
    mac: str | None


_WAKE_RE = re.compile(r"mWakefulness=(\w+)")
_DISPLAY_RE = re.compile(r"Display Power: state=(\w+)")


def parse_power(text: str) -> tuple[str | None, bool | None]:
    """Parse ``dumpsys power`` lines into (wakefulness, screen_on).

    ``Awake`` and ``Dreaming`` (screensaver) mean the panel is lit.
    """
    wakefulness = None
    if m := _WAKE_RE.search(text):
        wakefulness = m.group(1)
    if wakefulness is not None:
        return wakefulness, wakefulness in ("Awake", "Dreaming")
    if m := _DISPLAY_RE.search(text):
        return None, m.group(1).upper() == "ON"
    return None, None


# "u0 com.pkg/com.pkg.Activity" or "u0 com.pkg/.Activity" inside a record.
_COMPONENT_RE = re.compile(r"\bu\d+\s+([A-Za-z][\w]*(?:\.[\w]+)+)/([\w.$]+)")
# Windows without a component, e.g. "Window{1a2b u0 StatusBar}".
_WINDOW_ONLY_RE = re.compile(r"Window\{\w+\s+u\d+\s+([^\s}/]+)\}")


def _expand_activity(package: str, activity: str) -> str:
    if activity.startswith("."):
        return package + activity
    return activity


def parse_component(line: str) -> FocusInfo | None:
    """Extract package/activity from a WindowManager or ActivityManager record."""
    if m := _COMPONENT_RE.search(line):
        package, activity = m.group(1), m.group(2)
        return FocusInfo(package, _expand_activity(package, activity))
    return None


def parse_focus(window_text: str, activity_text: str = "") -> FocusInfo:
    """Parse the focused app.

    Handles both formats:
    - Android 9: ``mCurrentFocus=Window{... u0 pkg/activity}`` and
      ``mFocusedApp=AppWindowToken{... token=Token{... ActivityRecord{... u0 pkg/act t1}}}``
    - Android 10+: ``mFocusedApp=ActivityRecord{... u0 pkg/.act t1}``

    mCurrentFocus wins (it is the visible window), then mFocusedApp, then the
    ActivityManager resumed activity. Focus on a window without a component
    (StatusBar, NotificationShade, null) falls through to mFocusedApp.
    """
    current: FocusInfo | None = None
    focused_app: FocusInfo | None = None
    for line in window_text.splitlines():
        if "mCurrentFocus" in line and current is None:
            current = parse_component(line)
        elif "mFocusedApp" in line and focused_app is None:
            focused_app = parse_component(line)
    if current:
        return current
    if focused_app:
        return focused_app
    for line in activity_text.splitlines():
        if result := parse_component(line):
            return result
    return FocusInfo()


_STATE_RE = re.compile(r"state=PlaybackState \{state=(?:[A-Z_]+\()?(\d+)\)?")

PLAYING_STATES = {3, 4, 5, 6, 9, 10, 11}  # playing, ff, rewind, buffering, skipping...
PAUSED_STATES = {2}


def parse_media_sessions(text: str) -> list[MediaSession]:
    """Parse grep'ed ``dumpsys media_session`` output into sessions."""
    sessions: list[MediaSession] = []
    current: MediaSession | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("package="):
            current = MediaSession(package=line.split("=", 1)[1].strip())
            sessions.append(current)
        elif current is None:
            continue
        elif line.startswith("active="):
            current.active = line.split("=", 1)[1].strip().lower() == "true"
        elif m := _STATE_RE.search(line):
            current.state = int(m.group(1))
    return sessions


def playback_from_sessions(sessions: list[MediaSession], app_id: str | None) -> str | None:
    """Pick the playback state: the foreground app's session first, else any active."""

    def to_state(code: int | None) -> str | None:
        if code is None:
            return None
        if code in PLAYING_STATES:
            return "playing"
        if code in PAUSED_STATES:
            return "paused"
        return "idle"

    if app_id:
        for s in sessions:
            if s.package == app_id and s.state is not None:
                return to_state(s.state)
    for s in sessions:
        if s.active and s.state in PLAYING_STATES:
            return "playing"
    return None


_DEVICE_VOL_RE = re.compile(r"\d+\s+\(([^)]+)\):\s*(\d+)")


def parse_audio(text: str) -> VolumeInfo:
    """Parse the STREAM_MUSIC block of ``dumpsys audio``.

    Example (Android 9 and 11)::

        - STREAM_MUSIC:
           Muted: false
           Min: 0
           Max: 15
           Current: 2 (speaker): 7, 400 (hdmi): 10, 40000000 (default): 9
           Devices: speaker
    """
    info = VolumeInfo()
    per_device: dict[str, int] = {}
    devices: list[str] = []
    started = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("- STREAM_MUSIC"):
            started = True
            continue
        if not started:
            continue
        if line.startswith("- STREAM_"):
            break
        key, _, value = line.partition(":")
        value = value.strip()
        if key == "Muted":
            info.muted = value.lower() == "true"
        elif key == "Max":
            with contextlib.suppress(ValueError, IndexError):
                info.max = int(value.split()[0])
        elif key == "Current":
            for name, vol in _DEVICE_VOL_RE.findall(value):
                per_device[name.strip()] = int(vol)
        elif key == "Devices":
            devices = [d.strip() for d in re.split(r"[ ,]+", value) if d.strip()]
        elif key == "streamVolume":
            with contextlib.suppress(ValueError):
                info.level = int(value)
    if info.level is None and per_device:
        for dev in devices:
            if dev in per_device:
                info.level = per_device[dev]
                break
        else:
            info.level = next(iter(per_device.values()))
    return info


def parse_poll(output: str) -> PollResult:
    """Parse the output of :data:`POLL_COMMAND`."""
    sections = split_sections(output)
    result = PollResult()
    result.wakefulness, result.screen_on = parse_power(sections.get("POWER", ""))
    result.focus = parse_focus(sections.get("WINDOW", ""), sections.get("ACTIVITY", ""))
    result.playback = playback_from_sessions(
        parse_media_sessions(sections.get("MEDIA", "")), result.focus.package
    )
    result.volume = parse_audio(sections.get("AUDIO", ""))
    return result


_PKG_LINE_RE = re.compile(r"^package:(?:.*=)?([A-Za-z][\w]*(?:\.[\w]+)+)\s*$")
_ACTIVITY_COMPONENT_RE = re.compile(r"^\s*([A-Za-z][\w]*(?:\.[\w]+)+)/[\w.$]+\s*$")
_PACKAGE_NAME_RE = re.compile(r"\bpackageName=([A-Za-z][\w]*(?:\.[\w]+)+)")


def parse_package_list(text: str) -> list[str]:
    """Parse ``pm list packages`` output (``package:com.x`` or ``package:/path=com.x``)."""
    packages: list[str] = []
    for line in text.splitlines():
        if m := _PKG_LINE_RE.match(line.strip()):
            packages.append(m.group(1))
    return packages


def parse_query_activities(text: str) -> list[str]:
    """Parse ``cmd package query-activities`` (``--brief``, ``--components`` or full)."""
    seen: dict[str, None] = {}
    for line in text.splitlines():
        if (m := _ACTIVITY_COMPONENT_RE.match(line)) or (m := _PACKAGE_NAME_RE.search(line)):
            seen.setdefault(m.group(1))
    return list(seen)


def parse_apps(output: str) -> AppsResult:
    """Parse :data:`APPS_COMMAND` output.

    Leanback launcher apps come first, then normal launcher apps. When
    ``query-activities`` is unavailable, third-party packages are used instead.
    """
    sections = split_sections(output)
    launchable: dict[str, None] = {}
    for name in ("LEANBACK", "LAUNCHER"):
        for pkg in parse_query_activities(sections.get(name, "")):
            launchable.setdefault(pkg)
    used_fallback = False
    if not launchable:
        used_fallback = True
        for pkg in parse_package_list(sections.get("THIRD", "")):
            launchable.setdefault(pkg)
    system = set(parse_package_list(sections.get("SYSTEM", "")))
    return AppsResult(list(launchable), system, used_fallback)


def parse_device_info(output: str) -> DeviceInfoResult:
    """Parse :data:`DEVICE_INFO_COMMAND` output."""
    values: dict[str, str] = {}
    for line in output.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key.strip()] = value.strip()

    def clean(v: str | None) -> str | None:
        return v if v and v.lower() not in ("unknown", "null") else None

    mac = None
    for key in ("eth", "wlan"):
        candidate = clean(values.get(key))
        if (
            candidate
            and re.match(r"^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$", candidate)
            and candidate != "00:00:00:00:00:00"
        ):
            mac = candidate.lower()
            break
    return DeviceInfoResult(
        serial=clean(values.get("serial")),
        manufacturer=clean(values.get("manufacturer")),
        model=clean(values.get("model")),
        release=clean(values.get("release")),
        mac=mac,
    )


# ---------------------------------------------------------------------------
# Key generation (run in an executor)
# ---------------------------------------------------------------------------


def ensure_adb_key(path: str) -> None:
    """Generate an ADB RSA key pair at ``path`` / ``path.pub`` if missing. Blocking."""
    if os.path.isfile(path) and os.path.isfile(path + ".pub"):
        return
    from adb_shell.auth.keygen import keygen  # noqa: PLC0415

    keygen(path)
    for p in (path, path + ".pub"):
        with contextlib.suppress(OSError):
            os.chmod(p, 0o600)


def load_adb_signer(path: str) -> Any:
    """Load the ADB signer from disk. Blocking."""
    from adb_shell.auth.sign_pythonrsa import PythonRSASigner  # noqa: PLC0415

    with open(path + ".pub", encoding="utf-8") as f:
        pub = f.read()
    with open(path, encoding="utf-8") as f:
        priv = f.read()
    return PythonRSASigner(pub, priv)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class AdbError(Exception):
    """Base ADB error."""


class AdbUnreachable(AdbError):
    """The TV did not answer on the ADB port."""


class AdbAuthTimeout(AdbError):
    """The TV answered but did not accept our key in time.

    adb-shell 0.4.4 never reports an explicit rejection: when the key is unknown (never
    allowed, or authorisations were revoked) it sends the public key, the TV shows
    "Allow USB debugging?", and the read times out unless someone accepts. So this is
    both "waiting for the user" and "rejected"; callers decide by repetition.
    """


# Default per-packet timeout for commands that do not pass their own.
DEFAULT_COMMAND_TIMEOUT = 10.0


class AdbClient:
    """Serialized async ADB client over TCP (``adb-shell``)."""

    def __init__(
        self,
        host: str,
        port: int,
        signer: Any,
        *,
        connect_timeout: float = 3.0,
        auth_timeout: float = 10.0,
    ) -> None:
        """Initialize."""
        self.host = host
        self.port = port
        self._signer = signer
        self._connect_timeout = connect_timeout
        self._auth_timeout = auth_timeout
        self._device: Any = None
        self._lock = asyncio.Lock()
        self.auth_prompted = False

    @property
    def connected(self) -> bool:
        """Return True if an ADB session is established."""
        return self._device is not None and bool(self._device.available)

    async def async_connect(
        self, *, connect_timeout: float | None = None, auth_timeout: float | None = None
    ) -> None:
        """Connect and authenticate.

        ``connect_timeout`` only bounds the TCP connect and the handshake; commands use
        their own timeout (see :meth:`_run`). Raises AdbUnreachable or AdbAuthTimeout.
        """
        from adb_shell.adb_device_async import AdbDeviceTcpAsync  # noqa: PLC0415
        from adb_shell.exceptions import (  # noqa: PLC0415
            AdbConnectionError,
            AdbTimeoutError,
            DeviceAuthError,
            InvalidResponseError,
            TcpTimeoutException,
        )

        async with self._lock:
            if self.connected:
                return
            await self._close_locked()
            self.auth_prompted = False
            device = AdbDeviceTcpAsync(
                self.host,
                self.port,
                default_transport_timeout_s=DEFAULT_COMMAND_TIMEOUT,
            )

            def _on_auth_prompt(_: Any) -> None:
                self.auth_prompted = True

            try:
                await device.connect(
                    rsa_keys=[self._signer],
                    transport_timeout_s=connect_timeout or self._connect_timeout,
                    auth_timeout_s=auth_timeout or self._auth_timeout,
                    auth_callback=_on_auth_prompt,
                )
            except (
                DeviceAuthError,
                OSError,
                TimeoutError,
                TcpTimeoutException,
                AdbTimeoutError,
                AdbConnectionError,
                InvalidResponseError,
            ) as err:
                await _safe_close(device)
                if self.auth_prompted:
                    raise AdbAuthTimeout(str(err)) from err
                raise AdbUnreachable(str(err)) from err
            except asyncio.CancelledError:
                await _safe_close(device)
                raise
            self._device = device

    async def async_close(self) -> None:
        """Close the connection."""
        async with self._lock:
            await self._close_locked()

    async def _close_locked(self) -> None:
        if self._device is not None:
            device, self._device = self._device, None
            await _safe_close(device)

    async def async_shell(self, command: str, timeout: float = 10.0) -> str:
        """Run a shell command and return its decoded output."""
        return await self._run("shell", command, timeout)

    async def async_exec_out(self, command: str, timeout: float = 15.0) -> bytes:
        """Run a command through ``exec:`` and return raw bytes (binary safe)."""
        return await self._run("exec_out", command, timeout)

    async def _run(self, method: str, command: str, timeout: float) -> Any:
        if not self.connected:
            raise AdbUnreachable("not connected")
        async with self._lock:
            device = self._device
            if device is None:
                raise AdbUnreachable("not connected")
            try:
                # The per-command timeout bounds every packet read as well as the
                # whole command: a command may stay silent longer than the connect
                # timeout (screencap, app discovery, user commands).
                kwargs = {
                    "transport_timeout_s": timeout,
                    "read_timeout_s": timeout,
                    "timeout_s": timeout,
                }
                if method == "shell":
                    result = await device.shell(command, **kwargs)
                else:
                    result = await device.exec_out(command, decode=False, **kwargs)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                _LOGGER.debug("ADB %s failed: %s", method, err)
                await self._close_locked()
                raise AdbUnreachable(str(err)) from err
            return result if result is not None else ("" if method == "shell" else b"")


async def _safe_close(device: Any) -> None:
    try:
        await device.close()
    except Exception:
        _LOGGER.debug("Error closing ADB device", exc_info=True)
