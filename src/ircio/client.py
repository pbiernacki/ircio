# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

import base64
import binascii
import warnings
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

_CAP_LS_MAX = 500  # maximum capabilities accumulated across CAP LS continuation lines


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
        ssl: bool | ssl_module.SSLContext = True,
        timeout: float | None = None,
    ) -> None:
        if (password or sasl) and ssl is False:
            warnings.warn(
                "Credentials (password/SASL) are being sent over a plaintext "
                "connection. Set ssl=True or pass an ssl.SSLContext to encrypt "
                "the connection.",
                stacklevel=2,
            )

        self.host = host
        self.port = port
        self.nick = nick
        self.user = user
        self.realname = realname
        self.password = password
        self.sasl = sasl

        self._conn = Connection(host, port, ssl=ssl, timeout=timeout)
        self._dispatcher = Dispatcher()
        self._connected = False
        self._cap_ls_caps: list[str] = []
        self._sasl_error: IRCAuthenticationError | None = None

        # Built-in handlers
        self._dispatcher.add_handler("PING", self._on_ping)
        if sasl:
            self._dispatcher.add_handler("AUTHENTICATE", self._on_authenticate)
            self._dispatcher.add_handler("CAP", self._on_cap)
            self._dispatcher.add_handler("903", self._on_sasl_success)
            self._dispatcher.add_handler("904", self._on_sasl_fail)
            self._dispatcher.add_handler("905", self._on_sasl_fail)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on(self, command: str) -> Callable[[AsyncHandler], None]:
        """Decorator to register a handler for an IRC command."""
        return self._dispatcher.on(command)

    def add_handler(self, command: str, handler: AsyncHandler) -> None:
        """Register a handler function for an IRC command."""
        self._dispatcher.add_handler(command, handler)

    @property
    def is_connected(self) -> bool:
        """Return True if the client is currently connected."""
        return self._connected

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

    async def set_nick(self, nick: str) -> None:
        """Send NICK and update the stored nickname."""
        self.nick = nick
        await self._conn.send(Message("NICK", [nick]))

    async def send(self, message: Message) -> None:
        """Send a raw IRC message."""
        await self._conn.send(message)

    async def run(self) -> None:
        """
        Main read loop — reads messages and dispatches them until disconnected.

        Typically called as a task:
            asyncio.create_task(client.run())
        """
        try:
            while True:
                try:
                    message = await self._conn.readline()
                except IRCConnectionError:
                    break
                await self._dispatcher.emit(message)
                if self._sasl_error is not None:
                    raise self._sasl_error
        finally:
            self._connected = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _register(self) -> None:
        if self.sasl:
            self.sasl.reset()
            self._cap_ls_caps = []
            self._sasl_error = None
            await self._conn.send(Message("CAP", ["LS", "302"]))
        if self.password:
            await self._conn.send(Message("PASS", [self.password]))
        await self._conn.send(Message("NICK", [self.nick]))
        await self._conn.send(Message("USER", [self.user, "0", "*", self.realname]))

    async def _on_cap(self, message: Message) -> None:
        if not self.sasl:
            return

        subcmd = message.params[1] if len(message.params) > 1 else ""

        if subcmd == "LS":
            # CAP LS 302 allows multiline responses: params[2] == "*" means more coming,
            # actual caps are then in params[3]; otherwise params[2] holds the caps.
            if len(message.params) > 2 and message.params[2] == "*":
                caps_str = message.params[3] if len(message.params) > 3 else ""
                if len(self._cap_ls_caps) < _CAP_LS_MAX:
                    self._cap_ls_caps.extend(caps_str.split())
            else:
                caps_str = message.params[2] if len(message.params) > 2 else ""
                if len(self._cap_ls_caps) < _CAP_LS_MAX:
                    self._cap_ls_caps.extend(caps_str.split())
                if any(c == "sasl" or c.startswith("sasl=") for c in self._cap_ls_caps):
                    await self._conn.send(Message("CAP", ["REQ", "sasl"]))
                else:
                    await self._conn.send(Message("CAP", ["END"]))
        elif subcmd == "ACK":
            caps_str = message.params[2] if len(message.params) > 2 else ""
            if any(c == "sasl" or c.startswith("sasl=") for c in caps_str.split()):
                await self._conn.send(Message("AUTHENTICATE", [self.sasl.name]))
        elif subcmd == "NAK":
            await self._conn.send(Message("CAP", ["END"]))

    async def _on_ping(self, message: Message) -> None:
        token = message.params[0] if message.params else ""
        await self._conn.send(Message("PONG", [token]))

    async def _on_authenticate(self, message: Message) -> None:
        if self.sasl is None:
            return
        if message.params == ["+"]:
            raw = b""
        else:
            try:
                raw = base64.b64decode(message.params[0], validate=True)
            except binascii.Error:
                self._sasl_error = IRCAuthenticationError(
                    "Invalid base64 in AUTHENTICATE message"
                )
                return
        response = self.sasl.step(raw)
        payload = base64.b64encode(response).decode() if response else "+"
        await self._conn.send(Message("AUTHENTICATE", [payload]))

    async def _on_sasl_success(self, message: Message) -> None:
        await self._conn.send(Message("CAP", ["END"]))

    async def _on_sasl_fail(self, message: Message) -> None:
        self._sasl_error = IRCAuthenticationError(
            f"SASL authentication failed ({message.command}): "
            + (message.params[-1] if message.params else "")
        )
