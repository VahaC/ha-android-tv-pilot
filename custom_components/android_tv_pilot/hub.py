"""Connection hub: owns the ADB and remote-protocol clients, state, apps and wake."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Hashable
import contextlib
from dataclasses import dataclass
import logging
import re
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from .adb import (
    APPS_COMMAND,
    POLL_COMMAND,
    AdbAuthTimeout,
    AdbClient,
    AdbUnreachable,
    AppsResult,
    NonAsciiTextError,
    UnsafeArgumentError,
    am_start_succeeded,
    input_text_command,
    launch_app_commands,
    monkey_succeeded,
    open_url_command,
    parse_apps,
    parse_poll,
    validate_package,
)
from .apps import AppEntry, KnownAppsProvider, build_app_list, find_app, prettify_package
from .const import (
    CONF_APP_OVERRIDES,
    CONF_EXCLUDE_SYSTEM_APPS,
    CONF_POLL_INTERVAL,
    CONF_REPRESS_INTERVAL,
    CONF_VOLUME_ENTITY,
    CONF_WAKE_BUTTON,
    CONF_WAKE_TIMEOUT,
    DEFAULT_EXCLUDE_SYSTEM_APPS,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_REPRESS_INTERVAL,
    DEFAULT_WAKE_TIMEOUT,
    POWER_ASLEEP,
    POWER_OFF,
    POWER_ON,
    POWER_WAKING,
)
from .errors import (
    CommandFailedError,
    NotFoundError,
    TvUnreachableError,
    UnsupportedError,
)
from .keys import REPEATABLE_KEYS, ResolvedKey, UnknownKeyError, adb_keyevent_command, resolve_key
from .power import WAKE_WAKING, WakeConfig, WakeController, WakeError, WakeHooks
from .remote_client import RemoteAuthError, RemoteClient, RemoteUnreachable
from .wake_entity import async_trigger_wake_entity

_LOGGER = logging.getLogger(__name__)

RECONNECT_BACKOFF = (5, 10, 20, 30, 60)
REMOTE_BACKOFF = (2, 5, 10, 30, 60)
REMOTE_CHECK_INTERVAL = 10.0
# Runtime ADB auth wait (setup and reauth wait 30 s): short, so the ADB lock is not
# held long while the TV shows "Allow USB debugging?".
RUNTIME_AUTH_TIMEOUT = 5.0
# After this many auth timeouts in a row the key is treated as rejected.
AUTH_FAILURES_BEFORE_REAUTH = 2
AUTH_BACKOFF = (60, 300, 900)
LONG_PRESS_SECONDS = 1.0
REPEAT_DELAY = 0.4
REPEAT_INTERVAL = 0.12
REPEAT_SAFETY_LIMIT = 15.0
SCREENSHOT_CACHE_SECONDS = 2.0
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_SHELL_ERROR_RE = re.compile(r"(?i)\b(error|exception|not found|unknown command|usage:)")


@dataclass(slots=True)
class TvState:
    """Merged TV state from ADB polling and remote-protocol pushes.

    Volume is kept per transport: ADB STREAM_MUSIC and the remote protocol's
    volume_info may use different scales.
    """

    screen_on: bool | None = None
    wakefulness: str | None = None
    app_id: str | None = None
    app_activity: str | None = None
    playback: str | None = None
    adb_volume_level: int | None = None
    adb_volume_max: int | None = None
    adb_volume_muted: bool | None = None
    remote_volume_level: int | None = None
    remote_volume_max: int | None = None
    remote_volume_muted: bool | None = None


class AndroidTVPilotHub:
    """One TV."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        adb: AdbClient,
        remote: RemoteClient | None,
        known_apps: KnownAppsProvider,
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.adb = adb
        self.remote = remote
        self.known_apps = known_apps
        self.state = TvState()
        self.started_options: dict[str, Any] = dict(entry.options)
        self.apps: list[AppEntry] = []
        self._apps_raw: AppsResult | None = None
        self._listeners: list[Callable[[], None]] = []
        self._run_task: asyncio.Task[None] | None = None
        self._remote_task: asyncio.Task[None] | None = None
        self._apps_task: asyncio.Task[None] | None = None
        self._repeat_task: asyncio.Task[None] | None = None
        self._repeat_key: str | None = None
        self._repeat_owner: Hashable | None = None
        self._kick = asyncio.Event()
        self._remote_kick = asyncio.Event()
        self._online: bool | None = None
        self._reauth_started = False
        self._auth_failures = 0
        self._auth_backoff_until = 0.0
        self._shot_lock = asyncio.Lock()
        self._shot_cache: tuple[float, bytes] | None = None
        self.wake = WakeController(
            self._wake_config(),
            WakeHooks(
                probe=self._async_probe,
                screen_on=self._async_screen_on,
                press_wake_button=self._async_press_wake_button,
                send_wakeup=self._async_send_wakeup,
                reachable_now=lambda: self.reachable,
            ),
            self._notify,
        )

    # ------------------------------------------------------------------ options

    @property
    def wake_button(self) -> str | None:
        """Configured wake button entity."""
        return self.entry.options.get(CONF_WAKE_BUTTON) or None

    @property
    def wake_timeout(self) -> int:
        """Wake timeout in seconds."""
        return int(self.entry.options.get(CONF_WAKE_TIMEOUT, DEFAULT_WAKE_TIMEOUT))

    @property
    def volume_entity(self) -> str | None:
        """External volume entity."""
        return self.entry.options.get(CONF_VOLUME_ENTITY) or None

    @property
    def poll_interval(self) -> float:
        """ADB poll interval."""
        return float(self.entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))

    def _wake_config(self) -> WakeConfig:
        return WakeConfig(
            has_wake_button=self.wake_button is not None,
            timeout=float(self.wake_timeout),
            repress_interval=float(self.entry.options.get(CONF_REPRESS_INTERVAL, DEFAULT_REPRESS_INTERVAL)),
        )

    # ------------------------------------------------------------ lifecycle

    async def async_start(self) -> None:
        """Start background connection handling (never blocks setup on the TV)."""
        self._run_task = self.entry.async_create_background_task(
            self.hass, self._async_run(), f"android_tv_pilot run {self.entry.title}"
        )
        if self.remote is not None:
            self._remote_task = self.entry.async_create_background_task(
                self.hass, self._async_remote_loop(), f"android_tv_pilot remote {self.entry.title}"
            )

    async def async_stop(self) -> None:
        """Stop every task and close every connection."""
        await self.wake.async_cancel()
        self.stop_repeat()
        for task in (self._run_task, self._remote_task, self._apps_task, self._repeat_task):
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        self._run_task = self._remote_task = self._apps_task = self._repeat_task = None
        if self.remote is not None:
            self.remote.disconnect()
        await self.adb.async_close()
        self._listeners.clear()

    @callback
    def async_add_listener(self, update_callback: Callable[[], None]) -> CALLBACK_TYPE:
        """Listen for state changes."""
        self._listeners.append(update_callback)

        @callback
        def remove() -> None:
            if update_callback in self._listeners:
                self._listeners.remove(update_callback)

        return remove

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    def kick(self) -> None:
        """Ask the poll loop to refresh now."""
        self._kick.set()

    # ------------------------------------------------------------ derived state

    @property
    def adb_connected(self) -> bool:
        """ADB session up."""
        return self.adb.connected

    @property
    def remote_connected(self) -> bool:
        """Remote protocol up."""
        return self.remote is not None and self.remote.connected

    @property
    def reachable(self) -> bool:
        """Any transport up."""
        return self.adb_connected or self.remote_connected

    @property
    def power_state(self) -> str:
        """``off`` / ``waking`` / ``on`` / ``asleep`` (card contract)."""
        if self.wake.wake_state == WAKE_WAKING:
            return POWER_WAKING
        if not self.reachable:
            return POWER_OFF
        if self.state.screen_on is False:
            return POWER_ASLEEP
        return POWER_ON

    @property
    def is_launcher(self) -> bool:
        """True if the home screen is in front."""
        return self.state.app_id is None or self.state.app_id in self.known_apps.launcher_packages()

    @property
    def volume_level(self) -> float | None:
        """Volume 0..1 from the transport that reports it (remote protocol first)."""
        s = self.state
        if self.remote_connected and s.remote_volume_level is not None and s.remote_volume_max:
            return max(0.0, min(1.0, s.remote_volume_level / s.remote_volume_max))
        if s.adb_volume_level is not None and s.adb_volume_max:
            return max(0.0, min(1.0, s.adb_volume_level / s.adb_volume_max))
        return None

    @property
    def volume_muted(self) -> bool | None:
        """Mute state (remote protocol first)."""
        s = self.state
        if self.remote_connected and s.remote_volume_muted is not None:
            return s.remote_volume_muted
        return s.adb_volume_muted

    def app_label(self, package: str | None) -> str | None:
        """Label for a package (from the app list or metadata)."""
        if package is None:
            return None
        if app := find_app(self.apps, package):
            return app.label
        meta = self.known_apps.get(package)
        if meta and meta.label:
            return meta.label
        return prettify_package(package)

    # --------------------------------------------------------------- main loop

    async def _async_run(self) -> None:
        failures = 0
        while True:
            reachable = await self._async_ensure_connected()
            if reachable:
                failures = 0
                self.wake.clear_failed()
                if self._online is not True:
                    if self._online is False:
                        _LOGGER.info("%s is reachable again", self.entry.title)
                    self._online = True
                    self._remote_kick.set()
                    self.async_schedule_apps_refresh()
                if self.adb_connected:
                    await self._async_poll()
                delay = self.poll_interval
            else:
                if self._online is True:
                    _LOGGER.warning(
                        "%s is unreachable (deep standby or offline); will keep retrying quietly",
                        self.entry.title,
                    )
                    self.state = TvState()
                    self.stop_repeat()
                self._online = False
                delay = RECONNECT_BACKOFF[min(failures, len(RECONNECT_BACKOFF) - 1)]
                failures += 1
            self._notify()
            self._kick.clear()
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout(delay):
                    await self._kick.wait()

    async def _async_connect_adb(self, *, fast: bool = False) -> None:
        """Connect ADB unless connected or backing off after auth failures."""
        if self.adb.connected or time.monotonic() < self._auth_backoff_until:
            return
        try:
            await self.adb.async_connect(
                connect_timeout=2.0 if fast else 3.0, auth_timeout=RUNTIME_AUTH_TIMEOUT
            )
        except AdbAuthTimeout:
            self._on_adb_auth_timeout()
        except AdbUnreachable:
            pass
        else:
            self._auth_failures = 0

    @callback
    def _on_adb_auth_timeout(self) -> None:
        """The TV answered but did not accept our key (prompt shown, nobody accepted)."""
        self._auth_failures += 1
        step = min(self._auth_failures - 1, len(AUTH_BACKOFF) - 1)
        self._auth_backoff_until = time.monotonic() + AUTH_BACKOFF[step]
        if self._auth_failures == 1:
            _LOGGER.warning(
                "%s asks to allow USB debugging: accept the dialog on the TV and tick"
                " 'Always allow from this computer'. Next ADB attempt in %s s",
                self.entry.title,
                AUTH_BACKOFF[step],
            )
        if self._auth_failures >= AUTH_FAILURES_BEFORE_REAUTH:
            self._start_reauth()

    async def _async_ensure_connected(self, *, fast: bool = False) -> bool:
        """Connect ADB if down (the remote protocol has its own task). Returns ``reachable``.

        With ``fast`` (wake probes) the remote protocol is also tried inline when ADB
        is down, since either transport proves the TV is awake.
        """
        await self._async_connect_adb(fast=fast)
        if fast and not self.adb.connected:
            await self._async_connect_remote(timeout=2.0)
        return self.reachable

    async def _async_connect_remote(self, timeout: float) -> bool:
        if self.remote is None or self._reauth_started:
            return False
        if self.remote.connected:
            return True
        try:
            await self.remote.async_connect(timeout=timeout)
        except RemoteAuthError:
            self._start_reauth()
            return False
        except RemoteUnreachable:
            return False
        return True

    async def _async_remote_loop(self) -> None:
        """Keep the remote protocol connected, with backoff, outside the poll loop."""
        failures = 0
        while True:
            if (self.remote is not None and self.remote.connected) or await self._async_connect_remote(
                timeout=4.0
            ):
                failures = 0
                delay = REMOTE_CHECK_INTERVAL
            else:
                delay = REMOTE_BACKOFF[min(failures, len(REMOTE_BACKOFF) - 1)]
                failures += 1
            self._remote_kick.clear()
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout(delay):
                    await self._remote_kick.wait()

    @callback
    def _start_reauth(self) -> None:
        if self._reauth_started:
            return
        self._reauth_started = True
        _LOGGER.warning(
            "%s does not accept the stored credentials; re-authentication needed", self.entry.title
        )
        self.entry.async_start_reauth(self.hass)

    @callback
    def on_remote_invalid_auth(self) -> None:
        """Remote-protocol callback (runs in the event loop): pairing lost."""
        self._start_reauth()

    @callback
    def on_remote_update(self) -> None:
        """Remote-protocol push: merge is_on / current_app / volume."""
        remote = self.remote
        if remote is None:
            return
        if remote.available:
            self.wake.clear_failed()
        else:
            self._remote_kick.set()
            if not self.adb_connected:
                self.stop_repeat()
        if remote.is_on is not None and remote.available:
            self.state.screen_on = remote.is_on
        if remote.current_app and remote.current_app != self.state.app_id:
            self.state.app_id = remote.current_app
            self.state.app_activity = None
            self.state.playback = None
        if remote.volume_level is not None:
            self.state.remote_volume_level = remote.volume_level
            self.state.remote_volume_max = remote.volume_max
            self.state.remote_volume_muted = remote.volume_muted
        self._notify()

    async def _async_poll(self) -> None:
        try:
            output = await self.adb.async_shell(POLL_COMMAND, timeout=8.0)
        except AdbUnreachable:
            return
        result = parse_poll(output)
        if result.screen_on is not None:
            self.state.screen_on = result.screen_on
        self.state.wakefulness = result.wakefulness
        if result.focus.package:
            self.state.app_id = result.focus.package
            self.state.app_activity = result.focus.activity
        self.state.playback = result.playback
        if result.volume.level is not None:
            self.state.adb_volume_level = result.volume.level
        if result.volume.max is not None:
            self.state.adb_volume_max = result.volume.max
        if result.volume.muted is not None:
            self.state.adb_volume_muted = result.volume.muted

    # -------------------------------------------------------------- wake hooks

    async def _async_probe(self) -> bool:
        return await self._async_ensure_connected(fast=True)

    async def _async_screen_on(self) -> bool | None:
        if self.adb_connected:
            await self._async_poll()
            if self.state.screen_on is not None:
                return self.state.screen_on
        if self.remote_connected and self.remote is not None:
            return self.remote.is_on
        return None

    async def _async_press_wake_button(self) -> None:
        """Trigger the wake entity with the action that fits its domain."""
        if not self.wake_button:
            return
        await async_trigger_wake_entity(
            self.hass, self.wake_button, float(self._wake_config().repress_interval)
        )

    async def _async_send_wakeup(self) -> None:
        await self.async_send_key("WAKEUP")
        self.state.screen_on = True
        self._notify()

    # ------------------------------------------------------------------ power

    async def async_turn_on(self) -> None:
        """Turn on from any state."""
        self.wake.config = self._wake_config()
        try:
            await self.wake.async_turn_on()
        except WakeError as err:
            if err.translation_key == "wake_cancelled":
                raise CommandFailedError("wake_cancelled") from err
            if err.translation_key == "no_wake_button":
                raise TvUnreachableError("no_wake_button") from err
            if err.translation_key == "wake_entity_unavailable":
                raise CommandFailedError("wake_entity_unavailable", **err.placeholders) from err
            raise TvUnreachableError("wake_timeout", timeout=str(self.wake_timeout)) from err
        finally:
            self._notify()
        self.kick()

    async def async_turn_off(self) -> None:
        """Put the TV to sleep (POWER key via remote if awake, else ADB SLEEP)."""
        if not self.reachable or self.state.screen_on is False:
            return
        self.stop_repeat()
        if self.remote_connected and self.remote is not None:
            try:
                self.remote.send_key("POWER")
            except RemoteUnreachable:
                await self._adb_key(resolve_key("SLEEP"))
        else:
            await self._adb_key(resolve_key("SLEEP"))
        self.state.screen_on = False
        self.state.playback = None
        self._notify()
        self.kick()

    # ------------------------------------------------------------------- keys

    def _require_reachable(self) -> None:
        if not self.reachable:
            raise TvUnreachableError("tv_unreachable")

    async def _adb_key(self, key: ResolvedKey, *, longpress: bool = False) -> None:
        if not self.adb_connected:
            raise TvUnreachableError("tv_unreachable")
        try:
            await self.adb.async_shell(adb_keyevent_command(key, longpress=longpress))
        except AdbUnreachable as err:
            raise TvUnreachableError("tv_unreachable") from err

    def _remote_key(self, key: ResolvedKey, direction: str) -> bool:
        """Send via remote; False if the remote cannot send this key."""
        if not self.remote_connected or self.remote is None:
            return False
        try:
            self.remote.send_key(key.remote, direction)
        except (ValueError, RemoteUnreachable):
            return False
        return True

    async def _press(self, key: ResolvedKey) -> None:
        if not self._remote_key(key, "SHORT"):
            await self._adb_key(key)

    async def _long_press(self, key: ResolvedKey, hold: float) -> None:
        if self._remote_key(key, "START_LONG"):
            try:
                await asyncio.sleep(hold)
            finally:
                self._remote_key(key, "END_LONG")
            return
        await self._adb_key(key, longpress=True)

    async def async_send_key(
        self,
        key: str | int,
        action: str = "press",
        hold_secs: float | None = None,
        *,
        owner: Hashable | None = None,
    ) -> None:
        """Send a key (``press`` / ``long`` / ``down`` / ``up``).

        ``down`` on a repeatable key presses once and keeps repeating until ``up`` for
        the same key, a new ``down``, the owner going away (:meth:`stop_repeat`), the TV
        becoming unreachable, unload, or the 15 s safety stop. ``up`` without an active
        repeat of that key is a silent no-op.
        """
        try:
            resolved = resolve_key(key)
        except UnknownKeyError as err:
            raise NotFoundError("unknown_key", key=str(key)) from err
        if action == "up":
            if self._repeat_key == resolved.name:
                self.stop_repeat()
            return
        self._require_reachable()
        if action == "long":
            await self._long_press(resolved, hold_secs or LONG_PRESS_SECONDS)
        elif action == "down":
            self.stop_repeat()
            await self._press(resolved)
            if resolved.name in REPEATABLE_KEYS:
                self._repeat_key = resolved.name
                self._repeat_owner = owner
                self._repeat_task = self.entry.async_create_background_task(
                    self.hass, self._async_repeat(resolved), "android_tv_pilot key repeat"
                )
        else:
            await self._press(resolved)

    @property
    def repeating_key(self) -> str | None:
        """Key currently auto-repeating (``down`` without ``up`` yet)."""
        if self._repeat_task is None or self._repeat_task.done():
            return None
        return self._repeat_key

    @callback
    def stop_repeat(self, owner: Hashable | None = None) -> None:
        """Stop the auto-repeat (only the one started by ``owner`` when given)."""
        if owner is not None and owner != self._repeat_owner:
            return
        if self._repeat_task is not None and not self._repeat_task.done():
            self._repeat_task.cancel()
        self._repeat_task = None
        self._repeat_key = None
        self._repeat_owner = None

    async def _async_repeat(self, key: ResolvedKey) -> None:
        start = time.monotonic()
        await asyncio.sleep(REPEAT_DELAY)
        while time.monotonic() - start < REPEAT_SAFETY_LIMIT:
            if not self.reachable:
                return
            try:
                await self._press(key)  # awaited: presses cannot pile up
            except Exception:  # noqa: BLE001
                return
            await asyncio.sleep(REPEAT_INTERVAL)

    # ------------------------------------------------------------------- text

    async def async_send_text(self, text: str, enter: bool = False) -> None:
        """Type text: remote IME first, ADB ``input text`` as fallback."""
        if not text and not enter:
            return
        self._require_reachable()
        if text:
            sent = False
            if self.remote_connected and self.remote is not None:
                try:
                    self.remote.send_text(text)
                    sent = True
                except (RemoteUnreachable, ValueError):
                    sent = False
            if not sent:
                if not self.adb_connected:
                    raise TvUnreachableError("tv_unreachable")
                try:
                    command = input_text_command(text)
                except NonAsciiTextError as err:
                    raise UnsupportedError("non_ascii_text") from err
                await self.async_adb_shell(command)
        if enter:
            await self.async_send_key("ENTER")

    # ------------------------------------------------------------- apps / urls

    async def async_launch_app(self, package: str) -> None:
        """Launch an app by package."""
        self._require_reachable()
        try:
            commands = launch_app_commands(package)
        except UnsafeArgumentError as err:
            raise NotFoundError("invalid_package", package=package) from err
        if self.adb_connected:
            for command in commands:
                output = await self.async_adb_shell(command)
                if monkey_succeeded(output):
                    self._after_app_change(package)
                    return
            raise CommandFailedError("launch_failed", package=package)
        if self.remote is not None and self.remote_connected:
            try:
                self.remote.send_launch(package)
            except RemoteUnreachable as err:
                raise TvUnreachableError("tv_unreachable") from err
            self._after_app_change(package)
            return
        raise TvUnreachableError("tv_unreachable")

    async def async_open_url(self, url: str, package: str | None = None) -> None:
        """Open a URL / deep link."""
        self._require_reachable()
        try:
            command = open_url_command(url, package)
        except UnsafeArgumentError as err:
            raise NotFoundError("invalid_url", url=url) from err
        if self.adb_connected:
            output = await self.async_adb_shell(command)
            if not am_start_succeeded(output):
                raise CommandFailedError("open_url_failed", url=url)
            self.kick()
            return
        if self.remote is not None and self.remote_connected and not package:
            try:
                self.remote.send_launch(url)
            except RemoteUnreachable as err:
                raise TvUnreachableError("tv_unreachable") from err
            self.kick()
            return
        raise TvUnreachableError("tv_unreachable")

    def _after_app_change(self, package: str) -> None:
        self.state.app_id = package
        self.state.app_activity = None
        self.state.playback = None
        self._notify()
        self.kick()

    async def async_select_source(self, label_or_package: str) -> None:
        """Launch by label or package.

        If the label is unknown (e.g. right after a cold start the app list is still
        empty), the app list is loaded once before resolving.
        """
        app = find_app(self.apps, label_or_package)
        if app is None and self.adb_connected:
            if self._apps_task is not None and not self._apps_task.done():
                with contextlib.suppress(Exception):
                    await asyncio.shield(self._apps_task)
                app = find_app(self.apps, label_or_package)
            if app is None:
                with contextlib.suppress(TvUnreachableError, UnsupportedError):
                    await self.async_refresh_apps()
                app = find_app(self.apps, label_or_package)
        if app is not None:
            await self.async_launch_app(app.package)
            return
        try:
            package = validate_package(label_or_package)
        except UnsafeArgumentError as err:
            raise NotFoundError("unknown_app", app=label_or_package) from err
        await self.async_launch_app(package)

    @callback
    def async_schedule_apps_refresh(self) -> None:
        """Refresh the app list in the background."""
        if self._apps_task is not None and not self._apps_task.done():
            return
        self._apps_task = self.entry.async_create_background_task(
            self.hass, self._async_refresh_apps_quiet(), "android_tv_pilot apps refresh"
        )

    async def _async_refresh_apps_quiet(self) -> None:
        try:
            await self.async_refresh_apps()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("App list refresh failed: %s", err)

    async def async_refresh_apps(self) -> list[AppEntry]:
        """Query launchable apps over ADB (cached result kept when offline)."""
        if not self.adb_connected:
            if self._apps_raw is None:
                raise TvUnreachableError("tv_unreachable")
            return self.apps
        output = await self.async_adb_shell(APPS_COMMAND, timeout=20.0)
        self._apps_raw = parse_apps(output)
        self.rebuild_apps()
        return self.apps

    @callback
    def rebuild_apps(self) -> None:
        """Rebuild the app list from the cached raw result and current options."""
        if self._apps_raw is None:
            return
        self.apps = build_app_list(
            self._apps_raw.launchable,
            self._apps_raw.system,
            self.known_apps,
            self.entry.options.get(CONF_APP_OVERRIDES, {}),
            exclude_system_apps=self.entry.options.get(CONF_EXCLUDE_SYSTEM_APPS, DEFAULT_EXCLUDE_SYSTEM_APPS),
        )
        self._notify()

    # ------------------------------------------------------------------ shell

    async def async_adb_shell(self, command: str, timeout: float = 10.0) -> str:
        """Run a shell command over ADB."""
        if not self.adb_connected:
            if self.remote_connected:
                raise UnsupportedError("adb_required")
            raise TvUnreachableError("tv_unreachable")
        try:
            return await self.adb.async_shell(command, timeout=timeout)
        except AdbUnreachable as err:
            raise TvUnreachableError("tv_unreachable") from err

    async def async_set_volume_level(self, level: float) -> None:
        """Set TV volume (0..1) over ADB, scaled by the ADB STREAM_MUSIC maximum."""
        if not self.adb_connected:
            if self.remote_connected:
                raise UnsupportedError("adb_required")
            raise TvUnreachableError("tv_unreachable")
        if not self.state.adb_volume_max:
            await self._async_poll()
        maximum = self.state.adb_volume_max
        if not maximum:
            raise UnsupportedError("volume_max_unknown")
        target = int(max(0, min(maximum, round(level * maximum))))
        # `media` exists up to Android 11; `cmd media_session` on newer releases.
        for command in (
            f"media volume --stream 3 --set {target} 2>&1",
            f"cmd media_session volume --stream 3 --set {target} 2>&1",
        ):
            output = await self.async_adb_shell(command)
            if not _SHELL_ERROR_RE.search(output):
                break
            _LOGGER.debug("Volume command %r failed: %s", command, output.strip())
        else:
            raise CommandFailedError("volume_set_failed")
        self.state.adb_volume_level = target
        self._notify()

    async def async_screenshot(self) -> bytes:
        """PNG screenshot; one capture in flight, cached for 2 seconds."""
        if (cache := self._shot_cache) and time.monotonic() - cache[0] < SCREENSHOT_CACHE_SECONDS:
            return cache[1]
        async with self._shot_lock:
            if (cache := self._shot_cache) and time.monotonic() - cache[0] < SCREENSHOT_CACHE_SECONDS:
                return cache[1]
            if not self.adb_connected:
                if self.remote_connected:
                    raise UnsupportedError("adb_required")
                raise TvUnreachableError("tv_unreachable")
            try:
                data = await self.adb.async_exec_out("screencap -p", timeout=15.0)
            except AdbUnreachable as err:
                raise TvUnreachableError("tv_unreachable") from err
            start = data.find(PNG_SIGNATURE)
            if start < 0:
                raise CommandFailedError("screenshot_failed")
            data = data[start:]
            self._shot_cache = (time.monotonic(), data)
            return data
