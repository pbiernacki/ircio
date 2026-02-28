# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

from collections.abc import Callable, Coroutine
from typing import Any

from .message import Message

type AsyncHandler = Callable[[Message], Coroutine[Any, Any, None]]

class Dispatcher:
    def __init__(self) -> None: ...
    def on(self, command: str) -> Callable[[AsyncHandler], None]: ...
    def add_handler(self, command: str, handler: AsyncHandler) -> None: ...
    async def emit(self, message: Message) -> None: ...
