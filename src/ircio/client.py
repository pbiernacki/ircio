# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

import base64
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from .connection import Connection
from .dispatcher import Dispatcher
from .exceptions import IRCAuthenticationError, IRCConnectionError
from .message import Message

if TYPE_CHECKING:
    import ssl as ssl_module

    from .sasl import SASLMechanism

type AsyncHandler = Callable[[Message], Coroutine[Any, Any, None]]


class Client:
    """
    High-level IRC client.

    Wraps Connection + Dispatcher and handles:
    - Registration (NICK / USER / PASS)
    - PING/PONG keepalive
    - CAP negotiation and SASL authentication
    - Common commands: JOIN, PART, PRIVMSG, NOTICE, QUIT
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        nick: str,
        user: str,
        realname: str,
        password: str | None = None,
        sasl: SASLMechanism | None = None,
        ssl: bool | ssl_module.SSLContext = False,
    ) -> None:
        self.host = host
        self.port = port
        self.nick = nick
        self.user = user
        self.realname = realname
        self.password = password
        self.sasl = sasl

        self._conn = Connection(host, port, ssl=ssl)
        self._dispatcher = Dispatcher()
        self._connected = False

        # Built-in handlers
        self._dispatcher.add_handler("PING", self._on_ping)
        if sasl:
            self._dispatcher.add_handler("AUTHENTICATE", self._on_authenticate)
            self._dispatcher.add_handler("903", self._on_sasl_success)
            self._dispatcher.add_handler("904", self._on_sasl_fail)
            self._dispatcher.add_handler("905", self._on_sasl_fail)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on(self, command: str) -> Callable[[AsyncHandler], AsyncHandler]:
        """Decorator to register a handler for an IRC command."""
        return self._dispatcher.on(command)

    async def connect(self) -> None:
        """Connect and send registration commands."""
        await self._conn.connect()
        await self._register()
        self._connected = True

    async def disconnect(self, message: str = "") -> None:
        """Send QUIT and close the connection."""
        if self._connected:
            params = [message] if message else []
            await self._conn.send(Message("QUIT", params))
        await self._conn.disconnect()
        self._connected = False

    async def join(self, channel: str, key: str = "") -> None:
        params = [channel, key] if key else [channel]
        await self._conn.send(Message("JOIN", params))

    async def part(self, channel: str, message: str = "") -> None:
        params = [channel, message] if message else [channel]
        await self._conn.send(Message("PART", params))

    async def privmsg(self, target: str, text: str) -> None:
        await self._conn.send(Message("PRIVMSG", [target, text]))

    async def notice(self, target: str, text: str) -> None:
        await self._conn.send(Message("NOTICE", [target, text]))

    async def run(self) -> None:
        """
        Main read loop — reads messages and dispatches them until disconnected.

        Typically called as a task:
            asyncio.create_task(client.run())
        """
        while True:
            try:
                message = await self._conn.readline()
            except IRCConnectionError:
                break
            await self._dispatcher.emit(message)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _register(self) -> None:
        if self.sasl:
            await self._conn.send(Message("CAP", ["LS", "302"]))
        if self.password:
            await self._conn.send(Message("PASS", [self.password]))
        await self._conn.send(Message("NICK", [self.nick]))
        await self._conn.send(Message("USER", [self.user, "0", "*", self.realname]))
        if self.sasl:
            await self._conn.send(Message("CAP", ["REQ", "sasl"]))

    async def _on_ping(self, message: Message) -> None:
        token = message.params[0] if message.params else ""
        await self._conn.send(Message("PONG", [token]))

    async def _on_authenticate(self, message: Message) -> None:
        assert self.sasl is not None
        raw = b"" if message.params == ["+"] else base64.b64decode(message.params[0])
        response = self.sasl.step(raw)
        payload = base64.b64encode(response).decode() if response else "+"
        await self._conn.send(Message("AUTHENTICATE", [payload]))

    async def _on_sasl_success(self, message: Message) -> None:
        await self._conn.send(Message("CAP", ["END"]))

    async def _on_sasl_fail(self, message: Message) -> None:
        raise IRCAuthenticationError(
            f"SASL authentication failed ({message.command}): "
            + (message.params[-1] if message.params else "")
        )
