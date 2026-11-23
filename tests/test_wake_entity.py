"""Wake entity: the right action per domain, re-press semantics, missing entities."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.android_tv_pilot.power import WakeError
from custom_components.android_tv_pilot.wake_entity import async_trigger_wake_entity

from .test_init import MP, _fake_transports, _setup, _unload  # noqa: F401 - autouse fixture


def _record(hass: HomeAssistant, domain: str, service: str, calls: list[tuple[str, str]], **kwargs) -> None:
    async def handler(call: ServiceCall) -> None:
        calls.append((domain, service))
        if "sleep" in kwargs:
            await asyncio.sleep(kwargs["sleep"])

    hass.services.async_register(domain, service, handler)


@pytest.mark.parametrize(
    ("entity_id", "state", "expected"),
    [
        ("button.wake_the_tv", "2026-11-23T10:00:00+00:00", [("button", "press")]),
        ("input_button.wake", "unknown", [("input_button", "press")]),
        ("switch.ir_blaster_power", "off", [("switch", "turn_on")]),
        ("switch.ir_blaster_power", "on", [("switch", "turn_off"), ("switch", "turn_on")]),
        ("input_boolean.wake", "on", [("input_boolean", "turn_off"), ("input_boolean", "turn_on")]),
        ("scene.tv_on", "unknown", [("scene", "turn_on")]),
        ("script.wake_on_lan", "off", [("script", "wake_on_lan")]),
    ],
)
async def test_action_per_domain(hass: HomeAssistant, entity_id: str, state: str, expected: list) -> None:
    calls: list[tuple[str, str]] = []
    for domain, service in expected:
        _record(hass, domain, service, calls)
    hass.states.async_set(entity_id, state)
    await async_trigger_wake_entity(hass, entity_id, 8)
    assert calls == expected


async def test_script_wait_is_bounded_by_repress_interval(hass: HomeAssistant) -> None:
    calls: list[tuple[str, str]] = []
    _record(hass, "script", "slow_wake", calls, sleep=5)
    hass.states.async_set("script.slow_wake", "off")
    loop = asyncio.get_running_loop()
    start = loop.time()
    await async_trigger_wake_entity(hass, "script.slow_wake", 0.2)
    assert 0.15 < loop.time() - start < 2
    assert calls == [("script", "slow_wake")]
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_script_errors_propagate(hass: HomeAssistant) -> None:
    async def failing(call: ServiceCall) -> None:
        raise HomeAssistantError("boom")

    hass.services.async_register("script", "broken", failing)
    hass.states.async_set("script.broken", "off")
    with pytest.raises(HomeAssistantError):
        await async_trigger_wake_entity(hass, "script.broken", 1)


@pytest.mark.parametrize("entity_id", ["button.missing", "switch.offline", "light.not_allowed"])
async def test_missing_or_unavailable_entity(hass: HomeAssistant, entity_id: str) -> None:
    hass.states.async_set("switch.offline", "unavailable")
    hass.states.async_set("light.not_allowed", "off")
    with pytest.raises(WakeError) as err:
        await async_trigger_wake_entity(hass, entity_id, 1)
    assert err.value.translation_key == "wake_entity_unavailable"
    assert err.value.placeholders == {"entity_id": entity_id}


async def test_turn_on_with_unavailable_wake_entity(hass: HomeAssistant) -> None:
    entry = await _setup(hass, {"wake_button": "switch.esp32_wake", "wake_timeout": 30})
    hass.states.async_set("switch.esp32_wake", "unavailable")
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call("media_player", "turn_on", {"entity_id": MP}, blocking=True)
    assert err.value.translation_key == "wake_entity_unavailable"
    assert err.value.translation_placeholders == {"entity_id": "switch.esp32_wake"}
    assert "switch.esp32_wake" in str(err.value)
    state = hass.states.get(MP)
    assert state.attributes["wake_state"] == "failed"
    assert state.attributes["has_wake_button"] is True
    await _unload(hass, entry)


async def test_turn_on_with_switch_wake_entity(hass: HomeAssistant) -> None:
    from .fakes import FakeAdb

    calls: list[tuple[str, str]] = []

    async def turn_on(call: ServiceCall) -> None:
        calls.append(("switch", "turn_on"))
        FakeAdb.online = True

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.states.async_set("switch.esp32_wake", "off")
    entry = await _setup(hass, {"wake_button": "switch.esp32_wake"})
    await hass.services.async_call("media_player", "turn_on", {"entity_id": MP}, blocking=True)
    assert calls == [("switch", "turn_on")]
    assert hass.states.get(MP).attributes["wake_state"] == "idle"
    await _unload(hass, entry)
