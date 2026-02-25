# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

import asyncio
import ssl
import warnings
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ircio.client import Client
from ircio.exceptions import IRCConnectionError
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


@pytest.fixture
def sasl_client(mock_conn: MagicMock) -> Client:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        c = Client(
            "irc.example.com",
            6667,
            nick="testnick",
            user="testuser",
            realname="Test User",
            sasl=SASLPlain("testuser", "secret"),
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
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        c = Client("h", 6667, nick="n", user="u", realname="r", password="secret")
    c._conn = mock_conn
    await c.connect()
    assert "PASS" in sent_commands(mock_conn)


async def test_connect_sasl_sends_cap(mock_conn: MagicMock):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        c = Client(
            "h", 6667, nick="n", user="u", realname="r", sasl=SASLPlain("u", "p")
        )
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


# ---------------------------------------------------------------------------
# CAP / SASL negotiation
# ---------------------------------------------------------------------------


def sent_messages(mock_conn: MagicMock) -> list[Message]:
    return [call.args[0] for call in mock_conn.send.call_args_list]


async def test_register_with_sasl_sends_cap_ls(
    sasl_client: Client, mock_conn: MagicMock
):
    await sasl_client.connect()
    cmds = sent_commands(mock_conn)
    assert cmds[0] == "CAP"
    cap_msg = sent_messages(mock_conn)[0]
    assert cap_msg.params == ["LS", "302"]


async def test_cap_ls_sasl_supported(sasl_client: Client, mock_conn: MagicMock):
    msg = Message.parse(":srv CAP testnick LS :sasl multi-prefix")
    await sasl_client._on_cap(msg)
    last = mock_conn.send.call_args.args[0]
    assert last.command == "CAP"
    assert last.params == ["REQ", "sasl"]


async def test_cap_ls_sasl_not_supported(sasl_client: Client, mock_conn: MagicMock):
    msg = Message.parse(":srv CAP testnick LS :multi-prefix away-notify")
    await sasl_client._on_cap(msg)
    last = mock_conn.send.call_args.args[0]
    assert last.command == "CAP"
    assert last.params == ["END"]


async def test_cap_ls_sasl_with_value(sasl_client: Client, mock_conn: MagicMock):
    # CAP 302: sasl cap may carry a value like sasl=PLAIN,EXTERNAL
    msg = Message.parse(":srv CAP testnick LS :sasl=PLAIN,EXTERNAL multi-prefix")
    await sasl_client._on_cap(msg)
    last = mock_conn.send.call_args.args[0]
    assert last.command == "CAP"
    assert last.params == ["REQ", "sasl"]


async def test_cap_ls_multiline_sasl_in_second_batch(
    sasl_client: Client, mock_conn: MagicMock
):
    # First LS line — marked with * (more coming), no sasl yet
    first = Message.parse(":srv CAP testnick LS * :multi-prefix away-notify")
    await sasl_client._on_cap(first)
    # No REQ/END sent yet
    mock_conn.send.assert_not_called()

    # Final LS line — sasl present
    final = Message.parse(":srv CAP testnick LS :sasl tls")
    await sasl_client._on_cap(final)
    last = mock_conn.send.call_args.args[0]
    assert last.command == "CAP"
    assert last.params == ["REQ", "sasl"]


async def test_cap_ls_multiline_sasl_in_first_batch(
    sasl_client: Client, mock_conn: MagicMock
):
    # sasl in the first (non-final) line — should not send REQ until final arrives
    first = Message.parse(":srv CAP testnick LS * :sasl multi-prefix")
    await sasl_client._on_cap(first)
    mock_conn.send.assert_not_called()

    # Final LS line — empty (no more caps)
    final = Message.parse(":srv CAP testnick LS :")
    await sasl_client._on_cap(final)
    last = mock_conn.send.call_args.args[0]
    assert last.command == "CAP"
    assert last.params == ["REQ", "sasl"]


async def test_cap_ls_multiline_sasl_absent(sasl_client: Client, mock_conn: MagicMock):
    first = Message.parse(":srv CAP testnick LS * :multi-prefix")
    await sasl_client._on_cap(first)
    final = Message.parse(":srv CAP testnick LS :away-notify")
    await sasl_client._on_cap(final)
    last = mock_conn.send.call_args.args[0]
    assert last.params == ["END"]


async def test_cap_ack_sasl_sends_authenticate(
    sasl_client: Client, mock_conn: MagicMock
):
    msg = Message.parse(":srv CAP testnick ACK :sasl")
    await sasl_client._on_cap(msg)
    last = mock_conn.send.call_args.args[0]
    assert last.command == "AUTHENTICATE"
    assert last.params == ["PLAIN"]


async def test_cap_nak_sends_cap_end(sasl_client: Client, mock_conn: MagicMock):
    msg = Message.parse(":srv CAP testnick NAK :sasl")
    await sasl_client._on_cap(msg)
    last = mock_conn.send.call_args.args[0]
    assert last.command == "CAP"
    assert last.params == ["END"]


async def test_sasl_success_sends_cap_end(sasl_client: Client, mock_conn: MagicMock):
    msg = Message.parse(":srv 903 testnick :SASL authentication successful")
    await sasl_client._on_sasl_success(msg)
    last = mock_conn.send.call_args.args[0]
    assert last.command == "CAP"
    assert last.params == ["END"]


async def test_sasl_fail_stores_error(sasl_client: Client, mock_conn: MagicMock):
    from ircio.exceptions import IRCAuthenticationError

    msg = Message.parse(":srv 904 testnick :SASL authentication failed")
    await sasl_client._on_sasl_fail(msg)
    assert isinstance(sasl_client._sasl_error, IRCAuthenticationError)


async def test_sasl_fail_raised_from_run(mock_conn: MagicMock):
    """run() raises IRCAuthenticationError directly, not wrapped in ExceptionGroup."""
    import warnings

    from ircio.exceptions import IRCAuthenticationError

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        c = Client(
            "h",
            6667,
            nick="n",
            user="u",
            realname="r",
            sasl=SASLPlain("u", "p"),
            ssl=False,
        )
    c._conn = mock_conn
    # Server sends 904 (SASL fail), then closes connection
    mock_conn.readline = AsyncMock(
        side_effect=[
            Message.parse(":srv 904 n :SASL authentication failed"),
        ]
    )
    with pytest.raises(IRCAuthenticationError):
        await c.run()


async def test_send_strips_crlf() -> None:
    """Connection.send() must not let embedded CRLF reach the wire."""
    from unittest.mock import AsyncMock, MagicMock

    from ircio.connection import Connection
    from ircio.message import Message

    conn = Connection("h", 1)
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    conn._writer = writer

    msg = Message("PRIVMSG", ["#ch", "hello\r\nJOIN #evil"])
    await conn.send(msg)

    written: bytes = writer.write.call_args.args[0]
    assert b"\r\n" not in written[:-2], "embedded CRLF must be stripped before write"


# ---------------------------------------------------------------------------
# Plaintext credential warnings
# ---------------------------------------------------------------------------


def test_warn_password_without_ssl():
    with pytest.warns(match="plaintext"):
        Client(
            "h",
            6667,
            nick="n",
            user="u",
            realname="r",
            password="secret",
            ssl=False,
        )


def test_warn_sasl_without_ssl():
    with pytest.warns(match="plaintext"):
        Client(
            "h",
            6667,
            nick="n",
            user="u",
            realname="r",
            sasl=SASLPlain("u", "p"),
            ssl=False,
        )


def test_no_warn_password_with_ssl():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        Client("h", 6697, nick="n", user="u", realname="r", password="s", ssl=True)


def test_no_warn_no_credentials():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        Client("h", 6667, nick="n", user="u", realname="r")


# ---------------------------------------------------------------------------
# SASL reset on connect + b64decode validation
# ---------------------------------------------------------------------------


async def test_register_calls_sasl_reset(mock_conn: MagicMock):
    """Client._register() must call sasl.reset() before each connection attempt."""
    from unittest.mock import MagicMock

    sasl = MagicMock()
    sasl.name = "PLAIN"
    c = Client("h", 6697, nick="n", user="u", realname="r", sasl=sasl)
    c._conn = mock_conn
    await c._register()
    sasl.reset.assert_called_once()


async def test_authenticate_rejects_invalid_b64(
    sasl_client: Client, mock_conn: MagicMock
):
    """_on_authenticate must raise IRCAuthenticationError on malformed base64."""
    from ircio.exceptions import IRCAuthenticationError

    msg = Message("AUTHENTICATE", ["not!!valid==base64"])
    with pytest.raises(IRCAuthenticationError, match="base64"):
        await sasl_client._on_authenticate(msg)


# ---------------------------------------------------------------------------
# Resilience: LimitOverrunError, timeout, CAP LS limit
# ---------------------------------------------------------------------------


async def test_readline_limit_overrun_raises_connection_error():
    """LimitOverrunError from asyncio must be wrapped as IRCConnectionError."""
    from ircio.connection import Connection

    conn = Connection("h", 1)
    reader = MagicMock()
    reader.readline = AsyncMock(side_effect=asyncio.LimitOverrunError("too long", 0))
    conn._reader = reader

    with pytest.raises(IRCConnectionError):
        await conn.readline()


async def test_connect_timeout_raises_connection_error():
    """A TimeoutError during connect must be wrapped as IRCConnectionError."""
    from ircio.connection import Connection

    with patch("ircio.connection.asyncio.open_connection", new_callable=AsyncMock) as m:
        m.side_effect = TimeoutError
        conn = Connection("h", 1, ssl=False, timeout=0.001)
        with pytest.raises(IRCConnectionError, match="timed out"):
            await conn.connect()


async def test_readline_timeout_raises_connection_error():
    """A TimeoutError during readline must be wrapped as IRCConnectionError."""
    from ircio.connection import Connection

    conn = Connection("h", 1, timeout=0.001)
    reader = MagicMock()
    reader.readline = AsyncMock(side_effect=TimeoutError)
    conn._reader = reader

    with pytest.raises(IRCConnectionError, match="timed out"):
        await conn.readline()


async def test_cap_ls_limit(sasl_client: Client, mock_conn: MagicMock):
    """_cap_ls_caps must not grow beyond _CAP_LS_MAX entries."""
    from ircio.client import _CAP_LS_MAX

    # Flood with continuation lines
    caps = " ".join(f"cap{i}" for i in range(50))
    for _ in range(_CAP_LS_MAX):
        msg = Message.parse(f":srv CAP testnick LS * :{caps}")
        await sasl_client._on_cap(msg)

    assert len(sasl_client._cap_ls_caps) <= _CAP_LS_MAX
