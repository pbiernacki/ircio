# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

import ssl
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ircio.client import Client
from ircio.message import Message
from ircio.sasl import SASLPlain


@pytest.fixture
def mock_conn() -> MagicMock:
    conn = MagicMock()
    conn.connect = AsyncMock()
    conn.disconnect = AsyncMock()
    conn.send = AsyncMock()
    return conn


@pytest.fixture
def client(mock_conn: MagicMock) -> Client:
    c = Client(
        "irc.example.com",
        6667,
        nick="testnick",
        user="testuser",
        realname="Test User",
    )
    c._conn = mock_conn
    return c


def sent_commands(mock_conn: MagicMock) -> list[str]:
    return [call.args[0].command for call in mock_conn.send.call_args_list]


async def test_connect_sends_nick_and_user(client: Client, mock_conn: MagicMock):
    await client.connect()
    commands = sent_commands(mock_conn)
    assert "NICK" in commands
    assert "USER" in commands


async def test_connect_no_pass_by_default(client: Client, mock_conn: MagicMock):
    await client.connect()
    assert "PASS" not in sent_commands(mock_conn)


async def test_connect_sends_pass_when_set(mock_conn: MagicMock):
    c = Client("h", 6667, nick="n", user="u", realname="r", password="secret")
    c._conn = mock_conn
    await c.connect()
    assert "PASS" in sent_commands(mock_conn)


async def test_connect_sasl_sends_cap(mock_conn: MagicMock):
    c = Client("h", 6667, nick="n", user="u", realname="r", sasl=SASLPlain("u", "p"))
    c._conn = mock_conn
    await c.connect()
    commands = sent_commands(mock_conn)
    assert "CAP" in commands


async def test_join(client: Client, mock_conn: MagicMock):
    await client.join("#test")
    msg: Message = mock_conn.send.call_args.args[0]
    assert msg.command == "JOIN"
    assert msg.params[0] == "#test"


async def test_join_with_key(client: Client, mock_conn: MagicMock):
    await client.join("#test", "secret")
    msg: Message = mock_conn.send.call_args.args[0]
    assert msg.params == ["#test", "secret"]


async def test_part(client: Client, mock_conn: MagicMock):
    await client.part("#test", "Goodbye")
    msg: Message = mock_conn.send.call_args.args[0]
    assert msg.command == "PART"
    assert msg.params == ["#test", "Goodbye"]


async def test_privmsg(client: Client, mock_conn: MagicMock):
    await client.privmsg("#test", "Hello!")
    msg: Message = mock_conn.send.call_args.args[0]
    assert msg.command == "PRIVMSG"
    assert msg.params == ["#test", "Hello!"]


async def test_notice(client: Client, mock_conn: MagicMock):
    await client.notice("someone", "hey")
    msg: Message = mock_conn.send.call_args.args[0]
    assert msg.command == "NOTICE"
    assert msg.params == ["someone", "hey"]


async def test_ping_pong(client: Client, mock_conn: MagicMock):
    ping = Message.parse("PING :server.example.com")
    await client._on_ping(ping)
    msg: Message = mock_conn.send.call_args.args[0]
    assert msg.command == "PONG"
    assert msg.params == ["server.example.com"]


async def test_ping_pong_no_params(client: Client, mock_conn: MagicMock):
    ping = Message.parse("PING")
    await client._on_ping(ping)
    msg: Message = mock_conn.send.call_args.args[0]
    assert msg.command == "PONG"
    assert msg.params == [""]


async def test_disconnect_sends_quit(client: Client, mock_conn: MagicMock):
    client._connected = True
    await client.disconnect("Bye")
    commands = sent_commands(mock_conn)
    assert "QUIT" in commands
    mock_conn.disconnect.assert_called_once()


async def test_disconnect_not_connected(client: Client, mock_conn: MagicMock):
    client._connected = False
    await client.disconnect()
    # Should not send QUIT but still close
    assert "QUIT" not in sent_commands(mock_conn)
    mock_conn.disconnect.assert_called_once()


async def test_ssl_false_no_context(mock_conn: MagicMock) -> None:
    with patch("ircio.connection.asyncio.open_connection", new_callable=AsyncMock) as m:
        m.return_value = (MagicMock(), MagicMock())
        conn = __import__("ircio.connection", fromlist=["Connection"]).Connection(
            "h", 1, ssl=False
        )
        await conn.connect()
        _, kwargs = m.call_args
        assert kwargs["ssl"] is None


async def test_ssl_true_default_context(mock_conn: MagicMock) -> None:
    with patch("ircio.connection.asyncio.open_connection", new_callable=AsyncMock) as m:
        m.return_value = (MagicMock(), MagicMock())
        conn = __import__("ircio.connection", fromlist=["Connection"]).Connection(
            "h", 1, ssl=True
        )
        await conn.connect()
        _, kwargs = m.call_args
        assert isinstance(kwargs["ssl"], ssl.SSLContext)


async def test_ssl_custom_context(mock_conn: MagicMock) -> None:
    ctx = ssl.create_default_context()
    with patch("ircio.connection.asyncio.open_connection", new_callable=AsyncMock) as m:
        m.return_value = (MagicMock(), MagicMock())
        conn = __import__("ircio.connection", fromlist=["Connection"]).Connection(
            "h", 1, ssl=ctx
        )
        await conn.connect()
        _, kwargs = m.call_args
        assert kwargs["ssl"] is ctx


async def test_on_decorator(client: Client):
    received: list[Message] = []

    @client.on("PRIVMSG")
    async def handler(msg: Message) -> None:
        received.append(msg)

    msg = Message.parse(":n!u@h PRIVMSG #ch :hello")
    await client._dispatcher.emit(msg)
    assert len(received) == 1
