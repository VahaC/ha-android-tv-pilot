"""Wake state machine with fake transports and a fake clock."""

from __future__ import annotations

import asyncio

import pytest

from custom_components.android_tv_pilot.power import (
    WAKE_FAILED,
    WAKE_IDLE,
    WAKE_WAKING,
    WakeConfig,
    WakeController,
    WakeError,
    WakeHooks,
)


class FakeTV:
    """A TV that comes online after ``online_after`` seconds of fake time."""

    def __init__(
        self, *, reachable: bool = False, screen: bool | None = False, online_after: float | None = None
    ):
        self.now = 0.0
        self.reachable = reachable
        self.screen = screen
        self.online_after = online_after
        self.presses: list[float] = []
        self.wakeups = 0
        self.probes = 0
        self.states: list[str] = []
        self.started: list[object] = []
        self.state_at_probe: list[str] = []
        self.ctrl: WakeController

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += max(seconds, 0.001)
        await asyncio.sleep(0)

    async def probe(self) -> bool:
        self.probes += 1
        self.state_at_probe.append(self.ctrl.wake_state)
        if self.online_after is not None and self.presses and self.now - self.presses[0] >= self.online_after:
            self.reachable = True
        return self.reachable

    async def screen_on(self) -> bool | None:
        return self.screen

    async def press(self) -> None:
        self.presses.append(self.now)

    async def wakeup(self) -> None:
        self.wakeups += 1
        self.screen = True

    def controller(
        self, *, has_button: bool = True, timeout: float = 40, interval: float = 8
    ) -> WakeController:
        ctrl: WakeController

        def on_change() -> None:
            self.states.append(ctrl.wake_state)
            self.started.append(ctrl.wake_started_at)

        ctrl = WakeController(
            WakeConfig(has_wake_button=has_button, timeout=timeout, repress_interval=interval),
            WakeHooks(
                probe=self.probe,
                screen_on=self.screen_on,
                press_wake_button=self.press,
                send_wakeup=self.wakeup,
                reachable_now=lambda: self.reachable,
            ),
            on_change,
            monotonic=self.monotonic,
            sleep=self.sleep,
        )
        self.ctrl = ctrl
        return ctrl


async def test_reachable_and_awake_is_noop() -> None:
    tv = FakeTV(reachable=True, screen=True)
    await tv.controller().async_turn_on()
    assert tv.presses == []
    assert tv.wakeups == 0
    assert tv.states == []


async def test_reachable_and_asleep_sends_wakeup() -> None:
    tv = FakeTV(reachable=True, screen=False)
    await tv.controller().async_turn_on()
    assert tv.presses == []
    assert tv.wakeups == 1


async def test_reachable_unknown_screen_sends_wakeup() -> None:
    tv = FakeTV(reachable=True, screen=None)
    await tv.controller().async_turn_on()
    assert tv.wakeups == 1


async def test_unreachable_without_button_raises() -> None:
    tv = FakeTV()
    ctrl = tv.controller(has_button=False)
    with pytest.raises(WakeError) as err:
        await ctrl.async_turn_on()
    assert err.value.translation_key == "no_wake_button"
    assert ctrl.wake_state == WAKE_IDLE


async def test_deep_standby_wakes_with_repress() -> None:
    tv = FakeTV(online_after=20)
    ctrl = tv.controller(timeout=40, interval=8)
    await ctrl.async_turn_on()
    # pressed at 0, 8, 16 (online at 20)
    assert [round(p) for p in tv.presses] == [0, 8, 16]
    assert tv.wakeups == 1  # screen was still off after connecting
    assert tv.states == [WAKE_WAKING, WAKE_IDLE]
    assert ctrl.wake_state == WAKE_IDLE
    assert tv.started[0] is not None  # set while waking
    assert ctrl.wake_started_at is None  # cleared when idle again


async def test_screen_already_on_after_wake_no_wakeup_key() -> None:
    tv = FakeTV(online_after=3, screen=True)
    await tv.controller().async_turn_on()
    assert tv.wakeups == 0


async def test_timeout_sets_failed_then_cleared_on_next_attempt() -> None:
    tv = FakeTV()
    ctrl = tv.controller(timeout=20, interval=8)
    with pytest.raises(WakeError) as err:
        await ctrl.async_turn_on()
    assert err.value.translation_key == "wake_timeout"
    assert err.value.placeholders == {"timeout": "20"}
    assert ctrl.wake_state == WAKE_FAILED
    assert [round(p) for p in tv.presses] == [0, 8, 16]
    assert 20 <= tv.now < 21

    tv.reachable = True
    tv.screen = True
    await ctrl.async_turn_on()
    assert ctrl.wake_state == WAKE_IDLE


async def test_concurrent_calls_share_one_task() -> None:
    tv = FakeTV(online_after=10)
    ctrl = tv.controller()
    await asyncio.gather(ctrl.async_turn_on(), ctrl.async_turn_on(), ctrl.async_turn_on())
    assert [round(p) for p in tv.presses] == [0, 8]
    assert tv.wakeups == 1


async def test_cancelled_caller_does_not_cancel_shared_wake() -> None:
    tv = FakeTV(online_after=10)
    ctrl = tv.controller()
    first = asyncio.ensure_future(ctrl.async_turn_on())
    await asyncio.sleep(0)
    second = asyncio.ensure_future(ctrl.async_turn_on())
    await asyncio.sleep(0)
    first.cancel()
    await second
    assert ctrl.wake_state == WAKE_IDLE
    assert tv.wakeups == 1


async def test_async_cancel_resets_state() -> None:
    tv = FakeTV()  # never comes online

    async def slow_sleep(seconds: float) -> None:
        tv.now += seconds
        await asyncio.sleep(0.01)

    ctrl = tv.controller(timeout=1000)
    ctrl._sleep = slow_sleep
    task = asyncio.ensure_future(ctrl.async_turn_on())
    await asyncio.sleep(0.05)
    assert ctrl.wake_state == WAKE_WAKING
    await ctrl.async_cancel()
    assert ctrl.wake_state == WAKE_IDLE
    assert not ctrl.in_progress
    # the caller was not cancelled itself: it gets a WakeError, not CancelledError
    with pytest.raises(WakeError) as err:
        await task
    assert err.value.translation_key == "wake_cancelled"


async def test_wake_button_failure_is_retried() -> None:
    tv = FakeTV(online_after=None)
    calls = 0

    async def flaky_press() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("ble busy")
        tv.presses.append(tv.now)
        tv.reachable = True

    ctrl = tv.controller(interval=5)
    ctrl._hooks.press_wake_button = flaky_press
    await ctrl.async_turn_on()
    assert calls == 2
    assert ctrl.wake_state == WAKE_IDLE


async def test_caller_cancellation_still_propagates() -> None:
    tv = FakeTV()

    async def slow_sleep(seconds: float) -> None:
        tv.now += seconds
        await asyncio.sleep(0.01)

    ctrl = tv.controller(timeout=1000)
    ctrl._sleep = slow_sleep
    task = asyncio.ensure_future(ctrl.async_turn_on())
    await asyncio.sleep(0.03)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert ctrl.in_progress  # the shared wake keeps running for other callers
    await ctrl.async_cancel()


async def test_waking_is_shown_before_the_first_probe() -> None:
    tv = FakeTV(online_after=5)
    await tv.controller().async_turn_on()
    assert tv.state_at_probe[0] == WAKE_WAKING


async def test_probe_finds_tv_reachable_goes_back_to_idle() -> None:
    tv = FakeTV(reachable=False, screen=True)

    async def probe() -> bool:
        tv.state_at_probe.append(tv.ctrl.wake_state)
        return True  # e.g. ADB was just down between polls

    ctrl = tv.controller()
    ctrl._hooks.probe = probe
    await ctrl.async_turn_on()
    assert tv.state_at_probe == [WAKE_WAKING]
    assert tv.states == [WAKE_WAKING, WAKE_IDLE]
    assert tv.presses == []


async def test_known_reachable_never_shows_waking() -> None:
    tv = FakeTV(reachable=True, screen=False)
    await tv.controller().async_turn_on()
    assert tv.state_at_probe == [WAKE_IDLE]
    assert WAKE_WAKING not in tv.states


async def test_no_button_unreachable_returns_to_idle() -> None:
    tv = FakeTV()
    ctrl = tv.controller(has_button=False)
    with pytest.raises(WakeError):
        await ctrl.async_turn_on()
    assert tv.states == [WAKE_WAKING, WAKE_IDLE]


async def test_clear_failed() -> None:
    tv = FakeTV()
    ctrl = tv.controller(timeout=5, interval=8)
    with pytest.raises(WakeError):
        await ctrl.async_turn_on()
    assert ctrl.wake_state == WAKE_FAILED
    ctrl.clear_failed()
    assert ctrl.wake_state == WAKE_IDLE
    ctrl.clear_failed()  # no-op when not failed
    assert ctrl.wake_state == WAKE_IDLE
