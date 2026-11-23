"""ADB output parsers, with sample outputs from Android 9 (Xiaomi Mi TV / MediaTek) and Android TV 11/12."""

from __future__ import annotations

import pytest

from custom_components.android_tv_pilot.adb import (
    SECTION_MARK,
    NonAsciiTextError,
    UnsafeArgumentError,
    am_start_succeeded,
    input_text_command,
    launch_app_commands,
    monkey_succeeded,
    open_url_command,
    parse_apps,
    parse_audio,
    parse_device_info,
    parse_focus,
    parse_media_sessions,
    parse_package_list,
    parse_poll,
    parse_power,
    parse_query_activities,
    playback_from_sessions,
    shell_quote,
    split_sections,
    validate_package,
)

# ----------------------------------------------------------------- samples

# Xiaomi Mi TV 4S (Android 9, MediaTek), YouTube playing
A9_POWER = """  mWakefulness=Awake
  Display Power: state=ON
"""
A9_POWER_ASLEEP = """  mWakefulness=Asleep
  Display Power: state=OFF
"""
A9_WINDOW = """  mCurrentFocus=Window{3c1a0e5 u0 com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity}
  mFocusedApp=AppWindowToken{8f2b1d4 token=Token{a1c3e07 ActivityRecord{5d0e7c6 u0 com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity t412}}}
"""
A9_WINDOW_SCREEN_OFF = """  mCurrentFocus=null
  mFocusedApp=AppWindowToken{1e3b9a2 token=Token{4a7d1f0 ActivityRecord{9b2c4e1 u0 com.mitv.tvhome.atv/com.mitv.tvhome.atv.MainActivity t2}}}
"""
A9_ACTIVITY = """    mResumedActivity: ActivityRecord{5d0e7c6 u0 com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity t412}
"""
A9_MEDIA = """      package=com.google.android.youtube.tv
      active=true
      state=PlaybackState {state=3, position=125431, buffered position=0, speed=1.0, updated=81234567, actions=3669967, custom actions=[], active item id=-1, error=null}
      package=com.xiaomi.mitv.mediaexplorer
      active=false
      state=PlaybackState {state=0, position=0, buffered position=0, speed=0.0, updated=0, actions=0, custom actions=[], active item id=-1, error=null}
"""
A9_AUDIO = """- STREAM_MUSIC:
   Muted: false
   Min: 0
   Max: 100
   Current: 2 (speaker): 24, 400 (hdmi): 30, 40000000 (default): 15
   Devices: speaker
- STREAM_ALARM:
   Muted: false
"""

# Android TV 12 (Google TV style), Netflix paused
A12_WINDOW = """  mCurrentFocus=Window{4d3ae6b u0 com.netflix.ninja/com.netflix.ninja.MainActivity}
  mFocusedApp=ActivityRecord{e3f0a7d u0 com.netflix.ninja/.MainActivity t45}
"""
A12_WINDOW_NOTIFICATION = """  mCurrentFocus=Window{9a8b7c6 u0 NotificationShade}
  mFocusedApp=ActivityRecord{e3f0a7d u0 com.netflix.ninja/.MainActivity t45}
"""
A12_ACTIVITY = """  ResumedActivity: ActivityRecord{e3f0a7d u0 com.netflix.ninja/.MainActivity t45}
  topResumedActivity=ActivityRecord{e3f0a7d u0 com.netflix.ninja/.MainActivity t45}
"""
A12_MEDIA = """    package=com.netflix.ninja
    active=true
    state=PlaybackState {state=PAUSED(2), position=845000, buffered position=0, speed=0.0, updated=1234, actions=823, custom actions=[], active item id=-1, error=null}
"""
A12_AUDIO = """- STREAM_MUSIC:
   Muted: true
   Muted Internally: false
   Min: 0
   Max: 15
   streamVolume:9
   Current: 400 (hdmi): 9, 40000000 (default): 4
   Devices: hdmi
"""

A9_QUERY_BRIEF = """3 activities found:
  Activity #0:
    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=false
    com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity
  Activity #1:
    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=false
    com.netflix.ninja/.MainActivity
  Activity #2:
    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=false
    com.android.tv.settings/.MainSettings
"""
QUERY_FULL = """1 activities found:
  Activity #0:
    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=false
    ActivityInfo:
      name=org.videolan.vlc.StartActivity
      packageName=org.videolan.vlc
      enabled=true exported=true directBootAware=false
"""
PM_SYSTEM = """package:com.google.android.youtube.tv
package:com.netflix.ninja
package:com.android.tv.settings
package:com.mediatek.wwtv.tvcenter
"""
PM_THIRD = """package:org.videolan.vlc
package:org.jellyfin.androidtv
"""


def combined(**sections: str) -> str:
    """Build combined command output with section marks."""
    parts = []
    for name, text in sections.items():
        parts.append(f"{SECTION_MARK}{name}\n{text}")
    parts.append(f"{SECTION_MARK}END\n")
    return "".join(parts)


# ------------------------------------------------------------------- power


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (A9_POWER, ("Awake", True)),
        (A9_POWER_ASLEEP, ("Asleep", False)),
        ("  mWakefulness=Dreaming\n", ("Dreaming", True)),
        ("  mWakefulness=Dozing\n", ("Dozing", False)),
        ("  Display Power: state=ON\n", (None, True)),
        ("", (None, None)),
    ],
)
def test_parse_power(text: str, expected: tuple) -> None:
    assert parse_power(text) == expected


# ------------------------------------------------------------------- focus


def test_focus_android9() -> None:
    focus = parse_focus(A9_WINDOW, A9_ACTIVITY)
    assert focus.package == "com.google.android.youtube.tv"
    assert focus.activity == "com.google.android.apps.youtube.tv.activity.ShellActivity"


def test_focus_android9_null_current_focus_uses_focused_app() -> None:
    focus = parse_focus(A9_WINDOW_SCREEN_OFF)
    assert focus.package == "com.mitv.tvhome.atv"
    assert focus.activity == "com.mitv.tvhome.atv.MainActivity"


def test_focus_android12_short_activity_is_expanded() -> None:
    focus = parse_focus(A12_WINDOW)
    assert focus.package == "com.netflix.ninja"
    assert focus.activity == "com.netflix.ninja.MainActivity"


def test_focus_android12_notification_shade_falls_back() -> None:
    focus = parse_focus(A12_WINDOW_NOTIFICATION)
    assert focus.package == "com.netflix.ninja"
    assert focus.activity == "com.netflix.ninja.MainActivity"


def test_focus_activity_fallback_when_window_empty() -> None:
    assert parse_focus("", A12_ACTIVITY).package == "com.netflix.ninja"
    assert parse_focus("", A9_ACTIVITY).package == "com.google.android.youtube.tv"


def test_focus_nothing() -> None:
    focus = parse_focus("  mCurrentFocus=null\n  mFocusedApp=null\n", "")
    assert focus.package is None
    assert focus.activity is None


# ------------------------------------------------------------------- media


def test_media_sessions_android9() -> None:
    sessions = parse_media_sessions(A9_MEDIA)
    assert [(s.package, s.active, s.state) for s in sessions] == [
        ("com.google.android.youtube.tv", True, 3),
        ("com.xiaomi.mitv.mediaexplorer", False, 0),
    ]
    assert playback_from_sessions(sessions, "com.google.android.youtube.tv") == "playing"


def test_media_sessions_android12_named_state() -> None:
    sessions = parse_media_sessions(A12_MEDIA)
    assert sessions[0].state == 2
    assert playback_from_sessions(sessions, "com.netflix.ninja") == "paused"


def test_playback_other_app_active_session() -> None:
    sessions = parse_media_sessions(A9_MEDIA)
    assert playback_from_sessions(sessions, "com.android.tv.settings") == "playing"
    assert playback_from_sessions([], "x.y") is None
    stopped = parse_media_sessions("package=a.b\nactive=true\nstate=PlaybackState {state=1, position=0}")
    assert playback_from_sessions(stopped, "a.b") == "idle"


# ------------------------------------------------------------------- audio


def test_audio_android9_per_device() -> None:
    vol = parse_audio(A9_AUDIO)
    assert (vol.level, vol.max, vol.muted) == (24, 100, False)


def test_audio_android12_stream_volume() -> None:
    vol = parse_audio(A12_AUDIO)
    assert (vol.level, vol.max, vol.muted) == (9, 15, True)


def test_audio_missing() -> None:
    vol = parse_audio("")
    assert (vol.level, vol.max, vol.muted) == (None, None, None)


# -------------------------------------------------------------------- poll


def test_parse_poll_android9_playing() -> None:
    out = combined(POWER=A9_POWER, WINDOW=A9_WINDOW, ACTIVITY=A9_ACTIVITY, MEDIA=A9_MEDIA, AUDIO=A9_AUDIO)
    result = parse_poll(out)
    assert result.screen_on is True
    assert result.wakefulness == "Awake"
    assert result.focus.package == "com.google.android.youtube.tv"
    assert result.playback == "playing"
    assert result.volume.level == 24


def test_parse_poll_android12_paused() -> None:
    out = combined(
        POWER="  mWakefulness=Awake\n",
        WINDOW=A12_WINDOW,
        ACTIVITY=A12_ACTIVITY,
        MEDIA=A12_MEDIA,
        AUDIO=A12_AUDIO,
    )
    result = parse_poll(out)
    assert result.focus.package == "com.netflix.ninja"
    assert result.playback == "paused"
    assert result.volume.muted is True


def test_parse_poll_asleep_and_garbage() -> None:
    result = parse_poll(combined(POWER=A9_POWER_ASLEEP, WINDOW="", ACTIVITY="", MEDIA="", AUDIO=""))
    assert result.screen_on is False
    assert result.focus.package is None
    assert parse_poll("garbage\n").screen_on is None


def test_split_sections_ignores_preamble() -> None:
    out = f"junk\n{SECTION_MARK}A\nline1\nline2\n{SECTION_MARK}B\n"
    assert split_sections(out) == {"A": "line1\nline2", "B": ""}


# -------------------------------------------------------------------- apps


def test_query_activities_brief_and_full() -> None:
    assert parse_query_activities(A9_QUERY_BRIEF) == [
        "com.google.android.youtube.tv",
        "com.netflix.ninja",
        "com.android.tv.settings",
    ]
    assert parse_query_activities(QUERY_FULL) == ["org.videolan.vlc"]
    assert parse_query_activities("No activities found\n") == []


def test_package_list_formats() -> None:
    assert parse_package_list(PM_THIRD) == ["org.videolan.vlc", "org.jellyfin.androidtv"]
    assert parse_package_list("package:/data/app/x/base.apk=com.example.app\n") == ["com.example.app"]


def test_parse_apps_leanback_then_launcher() -> None:
    out = combined(
        LEANBACK=A9_QUERY_BRIEF, LAUNCHER=QUERY_FULL + A9_QUERY_BRIEF, SYSTEM=PM_SYSTEM, THIRD=PM_THIRD
    )
    result = parse_apps(out)
    assert result.launchable == [
        "com.google.android.youtube.tv",
        "com.netflix.ninja",
        "com.android.tv.settings",
        "org.videolan.vlc",
    ]
    assert "com.netflix.ninja" in result.system
    assert result.used_fallback is False


def test_parse_apps_fallback_when_query_unsupported() -> None:
    out = combined(
        LEANBACK="Unknown command: query-activities\n", LAUNCHER="", SYSTEM=PM_SYSTEM, THIRD=PM_THIRD
    )
    result = parse_apps(out)
    assert result.used_fallback is True
    assert result.launchable == ["org.videolan.vlc", "org.jellyfin.androidtv"]


# ------------------------------------------------------------- device info


def test_device_info() -> None:
    out = (
        "serial=0123456789ABCDEF\nmanufacturer=Xiaomi\nmodel=MiTV-MSSP1\nrelease=9\n"
        "eth=00:00:00:00:00:00\nwlan=AA:BB:CC:DD:EE:FF\n"
    )
    info = parse_device_info(out)
    assert info.serial == "0123456789ABCDEF"
    assert info.model == "MiTV-MSSP1"
    assert info.mac == "aa:bb:cc:dd:ee:ff"
    empty = parse_device_info("serial=\nmanufacturer=unknown\neth=\nwlan=\n")
    assert empty.serial is None
    assert empty.manufacturer is None
    assert empty.mac is None


# ------------------------------------------------- quoting / commands / text


@pytest.mark.parametrize(
    ("value", "quoted"),
    [
        ("simple", "'simple'"),
        ("", "''"),
        ("it's", "'it'\"'\"'s'"),
        ("a; rm -rf /", "'a; rm -rf /'"),
        ("$(reboot)`id`", "'$(reboot)`id`'"),
    ],
)
def test_shell_quote(value: str, quoted: str) -> None:
    assert shell_quote(value) == quoted


def test_shell_quote_rejects_nul() -> None:
    with pytest.raises(UnsafeArgumentError):
        shell_quote("a\x00b")


def test_input_text_escaping() -> None:
    assert input_text_command("hello world") == "input text 'hello%sworld'"
    assert input_text_command("it's & ok") == "input text 'it'\"'\"'s%s&%sok'"
    with pytest.raises(NonAsciiTextError):
        input_text_command("Привіт")
    with pytest.raises(NonAsciiTextError):
        input_text_command("tab\there")
    with pytest.raises(ValueError):
        input_text_command("")


def test_validate_package() -> None:
    assert validate_package(" com.netflix.ninja ") == "com.netflix.ninja"
    for bad in ("netflix", "com.x;reboot", "com..x", "1com.x", "com.x y"):
        with pytest.raises(UnsafeArgumentError):
            validate_package(bad)


def test_launch_commands() -> None:
    assert launch_app_commands("com.netflix.ninja") == [
        "monkey -p 'com.netflix.ninja' -c android.intent.category.LEANBACK_LAUNCHER 1",
        "monkey -p 'com.netflix.ninja' -c android.intent.category.LAUNCHER 1",
    ]
    assert monkey_succeeded("Events injected: 1\n## Network stats: elapsed time=12ms")
    assert not monkey_succeeded("** No activities found to run, monkey aborted.")


def test_open_url_command() -> None:
    cmd = open_url_command("https://youtu.be/x?a=1&b='2'", "com.google.android.youtube.tv")
    assert cmd == (
        "am start -a android.intent.action.VIEW -d "
        "'https://youtu.be/x?a=1&b='\"'\"'2'\"'\"'' 'com.google.android.youtube.tv'"
    )
    assert open_url_command("netflix://title/80057281").endswith("'netflix://title/80057281'")
    for bad in ("", "not a url", "; reboot"):
        with pytest.raises(UnsafeArgumentError):
            open_url_command(bad)
    assert am_start_succeeded("Starting: Intent { act=android.intent.action.VIEW dat=https://... }")
    assert not am_start_succeeded("Error: Activity not started, unable to resolve Intent")
