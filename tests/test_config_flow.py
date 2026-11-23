"""Config, options and reauth flows."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.android_tv_pilot.adb import AdbAuthTimeout, AdbUnreachable, DeviceInfoResult
from custom_components.android_tv_pilot.const import DOMAIN
from custom_components.android_tv_pilot.remote_client import RemoteAuthError, RemoteUnreachable

INFO = DeviceInfoResult(
    serial="SERIAL123", manufacturer="Xiaomi", model="MiTV-MSSP1", release="9", mac="aa:bb:cc:dd:ee:ff"
)
USER_INPUT = {"host": "192.0.2.10", "name": "Living room TV", "adb_port": 5555}


@pytest.fixture
def identify() -> Generator[AsyncMock]:
    with patch(
        "custom_components.android_tv_pilot.config_flow._async_adb_identify", return_value=INFO
    ) as mock:
        yield mock


@pytest.fixture
def pairing() -> Generator[MagicMock]:
    instance = MagicMock()
    instance.async_start = AsyncMock()
    instance.async_finish = AsyncMock()
    with (
        patch("custom_components.android_tv_pilot.config_flow.RemotePairing", return_value=instance),
        patch("custom_components.android_tv_pilot.config_flow.ensure_remote_cert"),
    ):
        yield instance


@pytest.fixture(autouse=True)
def no_setup() -> Generator[None]:
    with patch("custom_components.android_tv_pilot.async_setup_entry", return_value=True):
        yield


async def test_full_flow_with_pairing(hass: HomeAssistant, identify: AsyncMock, pairing: MagicMock) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    pairing.async_start.assert_awaited_once()

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"pin": "ab12cd"})
    pairing.async_finish.assert_awaited_once_with("AB12CD")
    assert result["step_id"] == "wake"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"wake_button": "button.wake_the_tv", "wake_timeout": 45, "repress_interval": 6},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room TV"
    assert result["result"].unique_id == "SERIAL123"
    assert result["data"]["use_remote"] is True
    assert result["data"]["host"] == "192.0.2.10"
    assert result["data"]["model"] == "MiTV-MSSP1"
    assert result["options"]["wake_button"] == "button.wake_the_tv"
    assert result["options"]["wake_timeout"] == 45
    assert result["options"]["repress_interval"] == 6
    assert result["options"]["exclude_system_apps"] is True


async def test_adb_auth_timeout_then_retry(
    hass: HomeAssistant, identify: AsyncMock, pairing: MagicMock
) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    identify.side_effect = AdbAuthTimeout("no answer")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "adb_auth_timeout"}
    identify.side_effect = AdbUnreachable("no route")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "cannot_connect"}
    identify.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["step_id"] == "pair"


async def test_remote_unreachable_skip(hass: HomeAssistant, identify: AsyncMock, pairing: MagicMock) -> None:
    pairing.async_start.side_effect = RemoteUnreachable("closed port")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "remote_unreachable"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"skip_remote": True})
    assert result["step_id"] == "wake"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"wake_timeout": 40, "repress_interval": 8}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["use_remote"] is False
    assert "wake_button" not in result["options"]


async def test_wrong_pin_restarts_pairing(
    hass: HomeAssistant, identify: AsyncMock, pairing: MagicMock
) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    pairing.async_finish.side_effect = RemoteAuthError("bad pin")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"pin": "000000"})
    assert result["errors"] == {"pin": "invalid_pin"}
    assert pairing.async_start.await_count == 2


async def test_already_configured(hass: HomeAssistant, identify: AsyncMock, pairing: MagicMock) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id="SERIAL123", data={"host": "192.0.2.99"}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_settings(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SERIAL123",
        data={"host": "192.0.2.10"},
        options={"wake_button": "button.old", "wake_timeout": 40, "repress_interval": 8},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "settings"}
    )
    assert result["step_id"] == "settings"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "volume_entity": "media_player.soundbar",
            "wake_timeout": 60,
            "repress_interval": 10,
            "poll_interval": 3,
            "exclude_system_apps": False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        "volume_entity": "media_player.soundbar",
        "wake_timeout": 60,
        "repress_interval": 10,
        "poll_interval": 3,
        "exclude_system_apps": False,
    }


async def test_options_app_override(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="SERIAL123", data={"host": "192.0.2.10"}, options={})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "app_override"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"package": "com.netflix.ninja"}
    )
    assert result["step_id"] == "app_override_edit"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"label": "Кіно", "hidden": "hide"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["app_overrides"] == {
        "com.netflix.ninja": {"label": "Кіно", "icon_url": None, "hidden": True}
    }


async def test_reauth_adb_only(hass: HomeAssistant, identify: AsyncMock) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="SERIAL123", data={"host": "192.0.2.10", "use_remote": False}
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_with_remote_pairing(
    hass: HomeAssistant, identify: AsyncMock, pairing: MagicMock
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="SERIAL123", data={"host": "192.0.2.10", "use_remote": True}
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "reauth_pair"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"pin": "abcdef"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_wake_step_links_and_any_wake_domain(
    hass: HomeAssistant, identify: AsyncMock, pairing: MagicMock
) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"skip_remote": True})
    assert result["step_id"] == "wake"
    placeholders = result["description_placeholders"]
    assert placeholders["guide_url"].startswith("https://community.home-assistant.io/t/wake-a-xiaomi-tv-box")
    assert placeholders["firmware_url"] == "https://github.com/dckiller51/esphome-xiaomi-ble-wake"
    selector = result["data_schema"].schema["wake_button"]
    assert set(selector.config["domain"]) == {
        "button",
        "input_button",
        "switch",
        "input_boolean",
        "script",
        "scene",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"wake_button": "script.wake_on_lan", "wake_timeout": 40, "repress_interval": 8}
    )
    assert result["options"]["wake_button"] == "script.wake_on_lan"


async def test_options_settings_has_links(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="SERIAL123", data={"host": "192.0.2.10"}, options={})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "settings"}
    )
    assert result["description_placeholders"]["firmware_url"].startswith("https://github.com/dckiller51/")
