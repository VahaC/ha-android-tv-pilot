"""Wake state machine.

Pure asyncio, no Home Assistant imports, so it is unit-testable with fakes.

Rules:
- reachable + screen on            -> no-op
- reachable + screen off/unknown   -> WAKEUP key
- unreachable + wake button        -> wake_state "waking", press the button, poll for
  connectivity, re-press every ``repress_interval`` until ``timeout``; on connect send
  WAKEUP if the screen is still off; "idle" on success, "failed" on timeout
- unreachable + no wake button     -> WakeError("no_wake_button")
- concurrent callers share one in-flight wake task
- a cancelled caller does not cancel the shared wake; ``async_cancel`` does
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import time

_LOGGER = logging.getLogger(__name__)

WAKE_IDLE = "idle"
WAKE_WAKING = "waking"
WAKE_FAILED = "failed"


class WakeError(Exception):
    """Wake failed; ``translation_key`` names the translated message."""

    def __init__(self, translation_key: str, **placeholders: str) -> None:
        """Initialize."""
        super().__init__(translation_key)
        self.translation_key = translation_key
        self.placeholders = placeholders


@dataclass(slots=True)
class WakeConfig:
    """Wake settings."""

    has_wake_button: bool
    timeout: float = 40.0
    repress_interval: float = 8.0
    probe_interval: float = 1.0


@dataclass(slots=True)
class WakeHooks:
    """Transport operations injected by the hub (or by tests)."""

    # Try to (re)connect quickly; True if the TV answers on ADB or the remote protocol.
    probe: Callable[[], Awaitable[bool]]
    # Current screen state: True on, False off, None unknown.
    screen_on: Callable[[], Awaitable[bool | None]]
    press_wake_button: Callable[[], Awaitable[None]]
    send_wakeup: Callable[[], Awaitable[None]]
    # Cheap, synchronous: is a transport connected right now (no I/O)?
    reachable_now: Callable[[], bool] = lambda: False


def _consume_result(task: asyncio.Task[None]) -> None:
    """Retrieve the exception so an unawaited failure is not logged as unhandled."""
    if not task.cancelled():
        task.exception()


class WakeController:
    """Turns the TV on from any state."""

    def __init__(
        self,
        config: WakeConfig,
        hooks: WakeHooks,
        on_change: Callable[[], None] | None = None,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        """Initialize."""
        self.config = config
        self._hooks = hooks
        self._on_change = on_change or (lambda: None)
        self._monotonic = monotonic
        self._sleep = sleep
        self._now = now
        self.wake_state: str = WAKE_IDLE
        self.wake_started_at: datetime | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def in_progress(self) -> bool:
        """Return True while a wake task runs."""
        return self._task is not None and not self._task.done()

    def _set_state(self, state: str, started_at: datetime | None = None) -> None:
        self.wake_state = state
        self.wake_started_at = started_at
        self._on_change()

    def clear_failed(self) -> None:
        """The TV became reachable by some other path: forget a previous failure."""
        if self.wake_state == WAKE_FAILED:
            self._set_state(WAKE_IDLE)

    async def async_turn_on(self) -> None:
        """Turn the TV on; concurrent calls share one task.

        Raises WakeError; ``wake_cancelled`` when the shared wake was cancelled by
        :meth:`async_cancel` (unload) while this caller itself was not cancelled.
        """
        if not self.in_progress:
            self._task = asyncio.get_running_loop().create_task(self._run())
            self._task.add_done_callback(_consume_result)
        task = self._task
        assert task is not None
        try:
            # shield: cancelling one caller must not abort the wake for the others.
            await asyncio.shield(task)
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise  # this caller was cancelled
            raise WakeError("wake_cancelled") from None

    async def async_cancel(self) -> None:
        """Cancel any in-flight wake (used on unload)."""
        task, self._task = self._task, None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, WakeError):
                pass
            except Exception:
                _LOGGER.debug("Wake task ended with an error", exc_info=True)

    async def _run(self) -> None:
        if self.wake_state == WAKE_FAILED:
            self._set_state(WAKE_IDLE)
        # Not known to be reachable: show "waking" right away, before the probes.
        if not self._hooks.reachable_now():
            self._set_state(WAKE_WAKING, self._now())
        try:
            if await self._hooks.probe():
                if await self._hooks.screen_on() is not True:
                    await self._hooks.send_wakeup()
                if self.wake_state == WAKE_WAKING:
                    self._set_state(WAKE_IDLE)
                return

            if not self.config.has_wake_button:
                if self.wake_state == WAKE_WAKING:
                    self._set_state(WAKE_IDLE)
                raise WakeError("no_wake_button")

            if self.wake_state != WAKE_WAKING:
                self._set_state(WAKE_WAKING, self._now())
            start = self._monotonic()
            deadline = start + self.config.timeout
            next_press = start
            while True:
                now = self._monotonic()
                if now >= next_press:
                    try:
                        await self._hooks.press_wake_button()
                    except asyncio.CancelledError:
                        raise
                    except WakeError:
                        # e.g. the wake entity is missing/unavailable: retrying cannot help
                        self._set_state(WAKE_FAILED)
                        raise
                    except Exception as err:  # noqa: BLE001
                        _LOGGER.warning("Triggering the wake entity failed: %s", err)
                    next_press = now + self.config.repress_interval
                if await self._hooks.probe():
                    break
                now = self._monotonic()
                if now >= deadline:
                    self._set_state(WAKE_FAILED)
                    raise WakeError("wake_timeout", timeout=str(int(self.config.timeout)))
                await self._sleep(max(0.0, min(self.config.probe_interval, deadline - now, next_press - now)))
            if await self._hooks.screen_on() is not True:
                await self._hooks.send_wakeup()
            self._set_state(WAKE_IDLE)
        except WakeError:
            raise
        except BaseException:
            if self.wake_state == WAKE_WAKING:
                self._set_state(WAKE_IDLE)
            raise
