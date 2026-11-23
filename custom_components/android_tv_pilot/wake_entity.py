"""Trigger the entity that wakes the TV from deep standby.

Any of these domains can be selected; each gets the action that fits it:

- ``button`` / ``input_button``: ``press``
- ``switch`` / ``input_boolean``: ``turn_on``; when it is already on, ``turn_off`` then
  ``turn_on`` so every re-press is a real edge
- ``script``: the script is run and awaited (``script.<name>``; ``script.turn_on`` would
  return immediately), but the wait is bounded by the re-press interval; a longer script
  keeps running in the background
- ``scene``: ``turn_on``
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, split_entity_id

from .power import WakeError

_LOGGER = logging.getLogger(__name__)

WAKE_ENTITY_DOMAINS: tuple[str, ...] = (
    "button",
    "input_button",
    "switch",
    "input_boolean",
    "script",
    "scene",
)


async def async_trigger_wake_entity(hass: HomeAssistant, entity_id: str, max_wait: float) -> None:
    """Trigger ``entity_id``; raise ``WakeError("wake_entity_unavailable")`` if it cannot be used."""
    domain, object_id = split_entity_id(entity_id)
    state = hass.states.get(entity_id)
    if domain not in WAKE_ENTITY_DOMAINS or state is None or state.state == STATE_UNAVAILABLE:
        raise WakeError("wake_entity_unavailable", entity_id=entity_id)
    target = {"entity_id": entity_id}

    if domain in ("button", "input_button"):
        await hass.services.async_call(domain, "press", target, blocking=True)
    elif domain in ("switch", "input_boolean"):
        if state.state == STATE_ON:
            await hass.services.async_call(domain, "turn_off", target, blocking=True)
        await hass.services.async_call(domain, "turn_on", target, blocking=True)
    elif domain == "scene":
        await hass.services.async_call(domain, "turn_on", target, blocking=True)
    else:  # script: run it as its own service so the call waits for it to finish
        task = hass.async_create_task(
            hass.services.async_call("script", object_id, {}, blocking=True),
            f"android_tv_pilot wake script {entity_id}",
        )
        done, _ = await asyncio.wait({task}, timeout=max(max_wait, 0.1))
        if task in done:
            task.result()  # re-raise script errors
        else:
            _LOGGER.debug("Wake script %s still running after %.1f s; continuing", entity_id, max_wait)

            def _consume(t: asyncio.Task) -> None:
                with contextlib.suppress(BaseException):
                    t.result()

            task.add_done_callback(_consume)
