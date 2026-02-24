# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

import asyncio
import ssl as ssl_module

from .exceptions import IRCConnectionError
from .message import Message


class Connection:
    """
    Low-level asyncio TCP/TLS connection to an IRC server.

    Handles raw byte I/O and delegates parsing to Message.

    The ``ssl`` parameter accepts three values:
    - ``True``  (default)       — TLS with the default system CA store
    - ``False``                 — plain TCP (no TLS)
    - ``ssl.SSLContext``        — TLS with a custom context (client certs, custom CA, …)
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        ssl: bool | ssl_module.SSLContext = True,
        encoding: str = "utf-8",
    ) -> None:
        self.host = host
        self.port = port
        self.ssl = ssl
        self.encoding = encoding
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        """Open the TCP (or TLS) connection."""
        match self.ssl:
            case ssl_module.SSLContext():
                ssl_ctx: ssl_module.SSLContext | None = self.ssl
            case True:
                ssl_ctx = ssl_module.create_default_context()
            case _:
                ssl_ctx = None

        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.host, self.port, ssl=ssl_ctx
            )
        except OSError as exc:
            raise IRCConnectionError(
                f"Cannot connect to {self.host}:{self.port}"
            ) from exc

    async def disconnect(self) -> None:
        """Close the connection gracefully."""
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None

    async def send(self, message: Message | str) -> None:
        """Send a message (appends CRLF automatically)."""
        if self._writer is None:
            raise IRCConnectionError("Not connected")
        line = str(message).translate(str.maketrans("", "", "\r\n\0"))
        self._writer.write(f"{line}\r\n".encode(self.encoding))
        await self._writer.drain()

    async def readline(self) -> Message:
        """Read one line from the server and return a parsed Message."""
        if self._reader is None:
            raise IRCConnectionError("Not connected")
        try:
            data = await self._reader.readline()
        except OSError as exc:
            raise IRCConnectionError("Connection lost") from exc
        if not data:
            raise IRCConnectionError("Connection closed by remote host")
        return Message.parse(data.decode(self.encoding, errors="replace"))

    async def __aenter__(self) -> Connection:
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.disconnect()
