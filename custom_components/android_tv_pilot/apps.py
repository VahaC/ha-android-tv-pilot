"""App discovery results and app metadata (labels, colours, icons).

Metadata comes from a chain of providers behind :class:`AppMetadataProvider`:
user overrides -> bundled ``known_apps.json`` -> fallback (prettified package name,
colour hashed from the package). An APK-based provider can be added to the chain
later without touching callers.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import colorsys
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Protocol

KNOWN_APPS_PATH = Path(__file__).parent / "known_apps.json"

_GENERIC_SEGMENTS = {
    "android",
    "app",
    "apps",
    "tv",
    "atv",
    "androidtv",
    "leanback",
    "mobile",
    "client",
    "player",
    "ott",
    "livingroom",
    "application",
    "release",
    "prod",
}


@dataclass(slots=True, frozen=True)
class AppMetadata:
    """Display metadata for one package. ``None`` fields mean "not provided"."""

    label: str | None = None
    color: str | None = None
    icon: str | None = None
    icon_url: str | None = None
    hidden: bool | None = None
    launcher: bool | None = None


@dataclass(slots=True)
class AppEntry:
    """One app as exposed to the card (websocket ``android_tv_pilot/apps``)."""

    package: str
    label: str
    color: str
    icon: str | None
    icon_url: str | None
    hidden: bool
    system: bool

    def as_dict(self) -> dict[str, Any]:
        """Return the contract dict."""
        return asdict(self)


class AppMetadataProvider(Protocol):
    """Source of app metadata."""

    def get(self, package: str) -> AppMetadata | None:
        """Return metadata for a package or None."""


class KnownAppsProvider:
    """Metadata from the bundled ``known_apps.json``."""

    def __init__(self, data: Mapping[str, Any]) -> None:
        """Initialize from parsed JSON."""
        self._apps: dict[str, AppMetadata] = {}
        for item in data.get("apps", []):
            self._apps[item["package"]] = AppMetadata(
                label=item.get("label"),
                color=item.get("color"),
                icon=item.get("icon"),
                launcher=bool(item.get("launcher", False)),
            )

    @classmethod
    def load(cls, path: Path = KNOWN_APPS_PATH) -> KnownAppsProvider:
        """Load from disk. Blocking: call in an executor."""
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def get(self, package: str) -> AppMetadata | None:
        """Return metadata for a known package."""
        return self._apps.get(package)

    def __contains__(self, package: str) -> bool:
        """Return True if the package is known."""
        return package in self._apps

    def launcher_packages(self) -> set[str]:
        """Packages known to be home-screen launchers."""
        return {p for p, m in self._apps.items() if m.launcher}


class OverridesProvider:
    """User overrides from config entry options: ``{pkg: {label, icon_url, hidden}}``."""

    def __init__(self, overrides: Mapping[str, Mapping[str, Any]] | None) -> None:
        """Initialize."""
        self._overrides = dict(overrides or {})

    def get(self, package: str) -> AppMetadata | None:
        """Return the override for a package."""
        if (o := self._overrides.get(package)) is None:
            return None
        return AppMetadata(
            label=o.get("label") or None,
            icon_url=o.get("icon_url") or None,
            hidden=o.get("hidden"),
        )


class FallbackProvider:
    """Always answers: prettified package name and a hashed colour."""

    def get(self, package: str) -> AppMetadata:
        """Return fallback metadata."""
        return AppMetadata(label=prettify_package(package), color=hash_color(package))


def prettify_package(package: str) -> str:
    """Turn ``com.example.my_cool_app.tv`` into ``My Cool App``."""
    segments = [s for s in package.split(".") if s]
    chosen = None
    for seg in reversed(segments[1:] or segments):
        if seg.lower() not in _GENERIC_SEGMENTS:
            chosen = seg
            break
    if chosen is None:
        chosen = segments[-1] if segments else package
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", chosen)
    words = re.sub(r"[_\-]+", " ", words).strip()
    return " ".join(w[:1].upper() + w[1:] for w in words.split()) or package


def hash_color(package: str) -> str:
    """Stable, readable colour derived from the package name."""
    digest = hashlib.sha1(package.encode("utf-8")).digest()
    hue = int.from_bytes(digest[:2], "big") / 65535.0
    r, g, b = colorsys.hls_to_rgb(hue, 0.45, 0.6)
    return f"#{round(r * 255):02X}{round(g * 255):02X}{round(b * 255):02X}"


def resolve_metadata(package: str, providers: Iterable[AppMetadataProvider]) -> AppMetadata:
    """Merge providers in priority order: the first non-None value per field wins."""
    fields = {"label": None, "color": None, "icon": None, "icon_url": None, "hidden": None}
    for provider in providers:
        meta = provider.get(package)
        if meta is None:
            continue
        for name, value in fields.items():
            if value is None:
                fields[name] = getattr(meta, name)
    fallback = FallbackProvider().get(package)
    return AppMetadata(
        label=fields["label"] or fallback.label,
        color=fields["color"] or fallback.color,
        icon=fields["icon"],
        icon_url=fields["icon_url"],
        hidden=fields["hidden"],
    )


def build_app_list(
    launchable: Iterable[str],
    system_packages: set[str],
    known: KnownAppsProvider,
    overrides: Mapping[str, Mapping[str, Any]] | None,
    *,
    exclude_system_apps: bool,
    extra_providers: Iterable[AppMetadataProvider] = (),
) -> list[AppEntry]:
    """Build the app list for the card, sorted by label (case-insensitive).

    ``exclude_system_apps`` hides system packages unless they are in the bundled
    catalogue (so preinstalled YouTube, Netflix or Settings stay visible) or the user
    explicitly un-hid them. Hidden apps stay in the list with ``hidden: true`` so the
    card and the options flow can show them.
    """
    override_provider = OverridesProvider(overrides)
    providers: list[AppMetadataProvider] = [override_provider, *extra_providers, known]
    launchers = known.launcher_packages()
    result: list[AppEntry] = []
    seen: set[str] = set()
    for package in launchable:
        if package in seen:
            continue
        seen.add(package)
        meta = resolve_metadata(package, providers)
        is_system = package in system_packages
        hidden = meta.hidden
        if hidden is None:
            hidden = package in launchers or (exclude_system_apps and is_system and package not in known)
        result.append(
            AppEntry(
                package=package,
                label=meta.label or package,
                color=meta.color or hash_color(package),
                icon=meta.icon,
                icon_url=meta.icon_url,
                hidden=bool(hidden),
                system=is_system,
            )
        )
    result.sort(key=lambda a: (a.label.casefold(), a.package))
    return result


def find_app(apps: Iterable[AppEntry], label_or_package: str) -> AppEntry | None:
    """Find an app by package (exact) or label (case-insensitive)."""
    apps = list(apps)
    for app in apps:
        if app.package == label_or_package:
            return app
    folded = label_or_package.casefold()
    for app in apps:
        if app.label.casefold() == folded:
            return app
    return None
