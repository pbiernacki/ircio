# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

import asyncio
import ssl
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ircio.connection import Connection
from ircio.exceptions import IRCConnectionError
from ircio.message import Message

# ---------------------------------------------------------------------------
# SSL context selection
# ---------------------------------------------------------------------------


async def test_ssl_false_no_context() -> None:
    with patch("ircio.connection.asyncio.open_connection", new_callable=AsyncMock) as m:
        m.return_value = (MagicMock(), MagicMock())
        conn = Connection("h", 1, ssl=False)
        await conn.connect()
        _, kwargs = m.call_args
        assert kwargs["ssl"] is None


async def test_ssl_true_default_context() -> None:
    with patch("ircio.connection.asyncio.open_connection", new_callable=AsyncMock) as m:
        m.return_value = (MagicMock(), MagicMock())
        conn = Connection("h", 1, ssl=True)
        await conn.connect()
        _, kwargs = m.call_args
        assert isinstance(kwargs["ssl"], ssl.SSLContext)


async def test_ssl_custom_context() -> None:
    ctx = ssl.create_default_context()
    with patch("ircio.connection.asyncio.open_connection", new_callable=AsyncMock) as m:
        m.return_value = (MagicMock(), MagicMock())
        conn = Connection("h", 1, ssl=ctx)
        await conn.connect()
        _, kwargs = m.call_args
        assert kwargs["ssl"] is ctx


# ---------------------------------------------------------------------------
# send / readline
# ---------------------------------------------------------------------------


async def test_send_strips_crlf() -> None:
    """Connection.send() must not let embedded CRLF reach the wire."""
    conn = Connection("h", 1)
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    conn._writer = writer

    msg = Message("PRIVMSG", ["#ch", "hello\r\nJOIN #evil"])
    await conn.send(msg)

    written: bytes = writer.write.call_args.args[0]
    assert b"\r\n" not in written[:-2], "embedded CRLF must be stripped before write"


async def test_readline_limit_overrun_raises_connection_error():
    """LimitOverrunError from asyncio must be wrapped as IRCConnectionError."""
    conn = Connection("h", 1)
    reader = MagicMock()
    reader.readline = AsyncMock(side_effect=asyncio.LimitOverrunError("too long", 0))
    conn._reader = reader

    with pytest.raises(IRCConnectionError):
        await conn.readline()


async def test_connect_timeout_raises_connection_error():
    """A TimeoutError during connect must be wrapped as IRCConnectionError."""
    with patch("ircio.connection.asyncio.open_connection", new_callable=AsyncMock) as m:
        m.side_effect = TimeoutError
        conn = Connection("h", 1, ssl=False, timeout=0.001)
        with pytest.raises(IRCConnectionError, match="timed out"):
            await conn.connect()


async def test_readline_timeout_raises_connection_error():
    """A TimeoutError during readline must be wrapped as IRCConnectionError."""
    conn = Connection("h", 1, timeout=0.001)
    reader = MagicMock()
    reader.readline = AsyncMock(side_effect=TimeoutError)
    conn._reader = reader

    with pytest.raises(IRCConnectionError, match="timed out"):
        await conn.readline()
