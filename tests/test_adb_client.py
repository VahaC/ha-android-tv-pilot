"""AdbClient against a fake ADB server speaking the real wire protocol (adb-shell 0.4.4)."""

from __future__ import annotations

import importlib.util

import pytest

pytest.importorskip("adb_shell")

from custom_components.android_tv_pilot.adb import AdbAuthTimeout, AdbClient, AdbUnreachable

from .fake_adb_server import FakeAdbServer


@pytest.fixture(autouse=True)
def _allow_local_sockets(request: pytest.FixtureRequest) -> None:
    """These tests talk to a real local TCP server.

    Under the Home Assistant test harness (pytest-socket) sockets are blocked in
    ``pytest_runtest_setup``; the ``socket_enabled`` fixture runs after that and
    re-enables them (connections stay limited to 127.0.0.1 by the harness).
    """
    if importlib.util.find_spec("pytest_socket") is not None:
        request.getfixturevalue("socket_enabled")


class FakeSigner:
    def Sign(self, data: bytes) -> bytes:
        return b"\x00" * 256

    def GetPublicKey(self) -> str:
        return "QAAAAFAKE= test@pilot"


async def test_command_silent_longer_than_connect_timeout() -> None:
    """Regression: commands used the connect timeout per packet and died after ~2-3 s."""
    async with FakeAdbServer(delay=0.6, output=b"package:com.netflix.ninja\n") as server:
        client = AdbClient("127.0.0.1", server.port, FakeSigner(), connect_timeout=0.2)
        await client.async_connect()
        assert client.connected
        assert (
            await client.async_shell("cmd package query-activities", timeout=5)
            == "package:com.netflix.ninja\n"
        )
        assert await client.async_exec_out("screencap -p", timeout=5) == b"package:com.netflix.ninja\n"
        assert client.connected
        await client.async_close()


async def test_command_timeout_still_applies() -> None:
    async with FakeAdbServer(delay=2.0) as server:
        client = AdbClient("127.0.0.1", server.port, FakeSigner(), connect_timeout=0.2)
        await client.async_connect()
        with pytest.raises(AdbUnreachable):
            await client.async_shell("sleep 10", timeout=0.3)
        assert not client.connected


async def test_unaccepted_key_is_auth_timeout() -> None:
    """adb-shell sends the public key and waits; nobody accepts -> AdbAuthTimeout."""
    async with FakeAdbServer(require_auth=True) as server:
        client = AdbClient("127.0.0.1", server.port, FakeSigner(), connect_timeout=1.0)
        with pytest.raises(AdbAuthTimeout):
            await client.async_connect(auth_timeout=0.3)
        assert server.public_key_received
        assert client.auth_prompted
        assert not client.connected


async def test_closed_port_is_unreachable() -> None:
    async with FakeAdbServer() as server:
        port = server.port
    client = AdbClient("127.0.0.1", port, FakeSigner(), connect_timeout=0.5)
    with pytest.raises(AdbUnreachable):
        await client.async_connect()
