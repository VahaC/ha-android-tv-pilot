"""Canonical key vocabulary mapped to both transports.

Every key name used by services, the remote entity and the card resolves here to:
- a remote-protocol key name (``androidtvremote2`` RemoteKeyCode, without ``KEYCODE_``)
- an Android ``KeyEvent`` code for ``adb shell input keyevent``.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

# name -> (remote protocol key name, android keycode)
KEYMAP: dict[str, tuple[str, int]] = {
    "UP": ("DPAD_UP", 19),
    "DOWN": ("DPAD_DOWN", 20),
    "LEFT": ("DPAD_LEFT", 21),
    "RIGHT": ("DPAD_RIGHT", 22),
    "CENTER": ("DPAD_CENTER", 23),
    "BACK": ("BACK", 4),
    "HOME": ("HOME", 3),
    "MENU": ("MENU", 82),
    "SETTINGS": ("SETTINGS", 176),
    "POWER": ("POWER", 26),
    "WAKEUP": ("WAKEUP", 224),
    "SLEEP": ("SLEEP", 223),
    "VOLUME_UP": ("VOLUME_UP", 24),
    "VOLUME_DOWN": ("VOLUME_DOWN", 25),
    "MUTE": ("VOLUME_MUTE", 164),
    "PLAY": ("MEDIA_PLAY", 126),
    "PAUSE": ("MEDIA_PAUSE", 127),
    "PLAY_PAUSE": ("MEDIA_PLAY_PAUSE", 85),
    "STOP": ("MEDIA_STOP", 86),
    "NEXT": ("MEDIA_NEXT", 87),
    "PREVIOUS": ("MEDIA_PREVIOUS", 88),
    "REWIND": ("MEDIA_REWIND", 89),
    "FAST_FORWARD": ("MEDIA_FAST_FORWARD", 90),
    "CHANNEL_UP": ("CHANNEL_UP", 166),
    "CHANNEL_DOWN": ("CHANNEL_DOWN", 167),
    "INFO": ("INFO", 165),
    "GUIDE": ("GUIDE", 172),
    "SEARCH": ("SEARCH", 84),
    "ASSIST": ("ASSIST", 219),
    "TV": ("TV", 170),
    "INPUT": ("TV_INPUT", 178),
    "CAPTIONS": ("CAPTIONS", 175),
    "DELETE": ("DEL", 67),
    "ENTER": ("ENTER", 66),
    "TAB": ("TAB", 61),
    "ESCAPE": ("ESCAPE", 111),
    **{str(n): (str(n), 7 + n) for n in range(10)},
    "RED": ("PROG_RED", 183),
    "GREEN": ("PROG_GREEN", 184),
    "YELLOW": ("PROG_YELLOW", 185),
    "BLUE": ("PROG_BLUE", 186),
}

KEY_VOCABULARY: tuple[str, ...] = tuple(KEYMAP)

# Keys that auto-repeat while held with action "down" (until "up").
REPEATABLE_KEYS: frozenset[str] = frozenset(
    {
        "UP",
        "DOWN",
        "LEFT",
        "RIGHT",
        "VOLUME_UP",
        "VOLUME_DOWN",
        "DELETE",
        "CHANNEL_UP",
        "CHANNEL_DOWN",
        "REWIND",
        "FAST_FORWARD",
    }
)

_KEYCODE_RE = re.compile(r"^KEYCODE_[A-Z0-9_]+$")
_NUMBER_RE = re.compile(r"^\d{1,4}$")


@dataclass(frozen=True, slots=True)
class ResolvedKey:
    """A key resolved for both transports."""

    name: str
    # Remote protocol key: a RemoteKeyCode name (str) or a raw code (int).
    remote: str | int
    # ADB keyevent argument: an int code or a KEYCODE_* name.
    adb: str | int


class UnknownKeyError(ValueError):
    """Raised when a key name is not in the vocabulary."""


def resolve_key(key: str | int) -> ResolvedKey:
    """Resolve a vocabulary key, a ``KEYCODE_*`` name or a numeric code."""
    if isinstance(key, int):
        if key < 0:
            raise UnknownKeyError(str(key))
        return ResolvedKey(str(key), key, key)
    name = str(key).strip().upper()
    if name in KEYMAP:
        remote, code = KEYMAP[name]
        return ResolvedKey(name, remote, code)
    if _KEYCODE_RE.match(name):
        return ResolvedKey(name, name.removeprefix("KEYCODE_"), name)
    if _NUMBER_RE.match(name):
        code = int(name)
        return ResolvedKey(name, code, code)
    raise UnknownKeyError(str(key))


def adb_keyevent_command(key: ResolvedKey, *, longpress: bool = False) -> str:
    """Build the ``input keyevent`` shell command for a resolved key.

    Only values produced by :func:`resolve_key` reach this function; they are
    validated against ``^KEYCODE_[A-Z0-9_]+$`` or are ints, so no quoting is needed.
    """
    flag = "--longpress " if longpress else ""
    return f"input keyevent {flag}{key.adb}"
