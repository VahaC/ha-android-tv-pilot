"""App metadata providers and list building."""

from __future__ import annotations

import json
import re

from custom_components.android_tv_pilot.apps import (
    KNOWN_APPS_PATH,
    AppMetadata,
    KnownAppsProvider,
    build_app_list,
    find_app,
    hash_color,
    prettify_package,
)


def known() -> KnownAppsProvider:
    return KnownAppsProvider.load()


def test_known_apps_file_is_valid() -> None:
    data = json.loads(KNOWN_APPS_PATH.read_text(encoding="utf-8"))
    apps = data["apps"]
    packages = [a["package"] for a in apps]
    assert len(packages) == len(set(packages)), "duplicate packages"
    non_launcher = [a for a in apps if not a.get("launcher")]
    assert len(non_launcher) >= 40
    for app in apps:
        assert re.match(r"^[A-Za-z][\w]*(\.[\w]+)+$", app["package"])
        assert app["label"]
        assert re.match(r"^#[0-9A-F]{6}$", app["color"]), app
        assert app.get("icon") is None or app["icon"].startswith("mdi:")


def test_prettify_package() -> None:
    assert prettify_package("com.example.my_cool_app") == "My Cool App"
    assert prettify_package("com.someVendor.tv") == "Some Vendor"
    assert prettify_package("org.jellyfin.androidtv") == "Jellyfin"
    assert prettify_package("tv.app") == "App"


def test_hash_color_is_stable() -> None:
    assert hash_color("com.x.y") == hash_color("com.x.y")
    assert re.match(r"^#[0-9A-F]{6}$", hash_color("com.x.y"))
    assert hash_color("com.x.y") != hash_color("com.x.z")


def test_build_app_list_metadata_and_sorting() -> None:
    apps = build_app_list(
        [
            "org.videolan.vlc",
            "com.netflix.ninja",
            "com.example.unknown_thing",
            "com.google.android.tvlauncher",
        ],
        {"com.netflix.ninja", "com.google.android.tvlauncher"},
        known(),
        None,
        exclude_system_apps=True,
    )
    by_pkg = {a.package: a for a in apps}
    assert [a.label for a in apps] == sorted((a.label for a in apps), key=str.casefold)
    netflix = by_pkg["com.netflix.ninja"]
    assert (netflix.label, netflix.color, netflix.icon, netflix.system, netflix.hidden) == (
        "Netflix",
        "#E50914",
        "mdi:netflix",
        True,
        False,  # system but in the catalogue -> visible
    )
    unknown = by_pkg["com.example.unknown_thing"]
    assert unknown.label == "Unknown Thing"
    assert unknown.icon is None
    assert unknown.icon_url is None
    assert by_pkg["com.google.android.tvlauncher"].hidden is True  # launchers are hidden
    assert set(netflix.as_dict()) == {"package", "label", "color", "icon", "icon_url", "hidden", "system"}


def test_exclude_system_apps() -> None:
    args = (["com.mediatek.wwtv.tvcenter", "org.videolan.vlc"], {"com.mediatek.wwtv.tvcenter"}, known(), None)
    hidden = {a.package: a.hidden for a in build_app_list(*args, exclude_system_apps=True)}
    assert hidden == {"com.mediatek.wwtv.tvcenter": True, "org.videolan.vlc": False}
    shown = {a.package: a.hidden for a in build_app_list(*args, exclude_system_apps=False)}
    assert shown["com.mediatek.wwtv.tvcenter"] is False


def test_overrides_win() -> None:
    overrides = {
        "com.netflix.ninja": {"label": "Кіно", "icon_url": "https://x/icon.png", "hidden": True},
        "com.mediatek.wwtv.tvcenter": {"label": None, "icon_url": None, "hidden": False},
    }
    apps = build_app_list(
        ["com.netflix.ninja", "com.mediatek.wwtv.tvcenter"],
        {"com.mediatek.wwtv.tvcenter"},
        known(),
        overrides,
        exclude_system_apps=True,
    )
    by_pkg = {a.package: a for a in apps}
    assert by_pkg["com.netflix.ninja"].label == "Кіно"
    assert by_pkg["com.netflix.ninja"].icon_url == "https://x/icon.png"
    assert by_pkg["com.netflix.ninja"].color == "#E50914"
    assert by_pkg["com.netflix.ninja"].hidden is True
    assert by_pkg["com.mediatek.wwtv.tvcenter"].hidden is False  # explicitly shown


def test_extra_provider_slot() -> None:
    class ApkProvider:
        def get(self, package: str) -> AppMetadata | None:
            return AppMetadata(label="From APK", icon_url="/local/x.png") if package == "a.b" else None

    apps = build_app_list(
        ["a.b"], set(), known(), None, exclude_system_apps=True, extra_providers=[ApkProvider()]
    )
    assert apps[0].label == "From APK"
    assert apps[0].icon_url == "/local/x.png"


def test_find_app() -> None:
    apps = build_app_list(["com.netflix.ninja"], set(), known(), None, exclude_system_apps=True)
    assert find_app(apps, "netflix").package == "com.netflix.ninja"
    assert find_app(apps, "com.netflix.ninja").label == "Netflix"
    assert find_app(apps, "nope") is None
