"""A minimal ADB-over-TCP server speaking the real wire protocol, for client tests."""

from __future__ import annotations

import asyncio
import contextlib

from adb_shell import constants
from adb_shell.adb_message import AdbMessage, unpack

WIRE_TO_ID = {v: k for k, v in constants.ID_TO_WIRE.items()}
HEADER = 24


class FakeAdbServer:
    """Serves ``shell:`` and ``exec:`` with a configurable delay before answering.

    ``require_auth``: answer CNXN with an AUTH token and never accept the key, like a
    TV whose "Allow USB debugging?" prompt nobody accepts.
    """

    def __init__(self, *, delay: float = 0.0, output: bytes = b"ok\n", require_auth: bool = False) -> None:
        self.delay = delay
        self.output = output
        self.require_auth = require_auth
        self.port = 0
        self.public_key_received = False
        self._server: asyncio.base_events.Server | None = None
        self._tasks: set[asyncio.Task] = set()

    async def __aenter__(self) -> FakeAdbServer:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc: object) -> None:
        assert self._server is not None
        self._server.close()
        for task in list(self._tasks):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        with contextlib.suppress(Exception):
            await self._server.wait_closed()

    async def _read(self, reader: asyncio.StreamReader) -> tuple[bytes, int, int, bytes]:
        header = await reader.readexactly(HEADER)
        cmd, arg0, arg1, length, _ = unpack(header)
        data = await reader.readexactly(length) if length else b""
        return WIRE_TO_ID[cmd], arg0, arg1, data

    @staticmethod
    def _send(writer: asyncio.StreamWriter, cmd: bytes, arg0: int, arg1: int, data: bytes = b"") -> None:
        msg = AdbMessage(cmd, arg0, arg1, data)
        writer.write(msg.pack() + data)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        self._tasks.add(task)
        try:
            cmd, *_ = await self._read(reader)
            assert cmd == constants.CNXN
            if self.require_auth:
                self._send(writer, constants.AUTH, constants.AUTH_TOKEN, 0, b"\x01" * 20)
                while True:
                    cmd, arg0, _, _ = await self._read(reader)
                    if cmd == constants.AUTH and arg0 == constants.AUTH_SIGNATURE:
                        self._send(writer, constants.AUTH, constants.AUTH_TOKEN, 0, b"\x02" * 20)
                    elif cmd == constants.AUTH and arg0 == constants.AUTH_RSAPUBLICKEY:
                        self.public_key_received = True
                        await asyncio.sleep(3600)  # the prompt is never accepted
            self._send(writer, constants.CNXN, constants.VERSION, constants.MAX_ADB_DATA, b"device::\x00")
            remote_id = 100
            while True:
                cmd, local_id, _, _ = await self._read(reader)
                if cmd != constants.OPEN:
                    continue
                remote_id += 1
                self._send(writer, constants.OKAY, remote_id, local_id)
                await asyncio.sleep(self.delay)  # silent while the "command" runs
                self._send(writer, constants.WRTE, remote_id, local_id, self.output)
                cmd, *_ = await self._read(reader)  # client OKAY
                self._send(writer, constants.CLSE, remote_id, local_id)
                cmd, *_ = await self._read(reader)  # client CLSE
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            self._tasks.discard(task)
            writer.close()
