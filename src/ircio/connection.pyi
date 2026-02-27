# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

import ssl as ssl_module

from .message import Message

class Connection:
    host: str
    port: int
    ssl: bool | ssl_module.SSLContext
    encoding: str
    timeout: float | None

    def __init__(
        self,
        host: str,
        port: int,
        *,
        ssl: bool | ssl_module.SSLContext = ...,
        encoding: str = ...,
        timeout: float | None = ...,
    ) -> None: ...
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def send(self, message: Message | str) -> None: ...
    async def readline(self) -> Message: ...
    async def __aenter__(self) -> Connection: ...
    async def __aexit__(self, *_: object) -> None: ...
