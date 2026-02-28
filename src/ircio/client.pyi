# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

import ssl as ssl_module
from collections.abc import Callable, Coroutine
from typing import Any

from .message import Message
from .sasl import SASLMechanism

type AsyncHandler = Callable[[Message], Coroutine[Any, Any, None]]

class Client:
    host: str
    port: int
    nick: str
    user: str
    realname: str
    password: str | None
    sasl: SASLMechanism | None
    def __init__(
        self,
        host: str,
        port: int,
        *,
        nick: str,
        user: str,
        realname: str,
        password: str | None = ...,
        sasl: SASLMechanism | None = ...,
        ssl: bool | ssl_module.SSLContext = ...,
        timeout: float | None = ...,
    ) -> None: ...
    def on(self, command: str) -> Callable[[AsyncHandler], None]: ...
    def add_handler(self, command: str, handler: AsyncHandler) -> None: ...
    @property
    def is_connected(self) -> bool: ...
    async def connect(self) -> None: ...
    async def disconnect(self, message: str = ...) -> None: ...
    async def join(self, channel: str, key: str = ...) -> None: ...
    async def part(self, channel: str, message: str = ...) -> None: ...
    async def privmsg(self, target: str, text: str) -> None: ...
    async def notice(self, target: str, text: str) -> None: ...
    async def set_nick(self, nick: str) -> None: ...
    async def send(self, message: Message) -> None: ...
    async def run(self) -> None: ...
