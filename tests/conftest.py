"""Test configuration.

Pure modules (adb, keys, power, apps) have no Home Assistant imports. When Home
Assistant is not installed, the package is registered as a namespace stub so these
modules import without running the package ``__init__`` (which needs Home Assistant).
Home Assistant tests skip themselves in that case.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "custom_components" / "android_tv_pilot"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HAS_HA = importlib.util.find_spec("homeassistant") is not None
HAS_HA_TEST = importlib.util.find_spec("pytest_homeassistant_custom_component") is not None

if not HAS_HA:
    for name, path in (
        ("custom_components", ROOT / "custom_components"),
        ("custom_components.android_tv_pilot", PKG_DIR),
    ):
        module = types.ModuleType(name)
        module.__path__ = [str(path)]  # type: ignore[attr-defined]
        sys.modules[name] = module


if HAS_HA_TEST and sys.platform == "win32":
    # Windows only: asyncio's self-pipe is an AF_INET socketpair, which the Home
    # Assistant test plugin's socket guard blocks. Tests never touch the network
    # (transports are mocked), so the guard is turned into a no-op. Home Assistant
    # itself does not support Windows; on Linux the guard stays active.
    import pytest_socket

    pytest_socket.disable_socket = lambda *args, **kwargs: None
    pytest_socket.socket_allow_hosts = lambda *args, **kwargs: None


if HAS_HA_TEST:
    from unittest.mock import patch

    @pytest.fixture(autouse=True)
    def auto_enable_custom_integrations(request: pytest.FixtureRequest):
        """Enable custom integrations for Home Assistant tests only.

        The ``frontend`` dependency needs the large ``home-assistant-frontend``
        package; its setup is replaced with a no-op in tests.
        """
        if "hass" not in request.fixturenames:
            yield
            return
        request.getfixturevalue("enable_custom_integrations")
        with patch("homeassistant.components.frontend.async_setup", return_value=True):
            yield
