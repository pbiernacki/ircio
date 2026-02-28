# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

from .message import Message

type AsyncHandler = Callable[[Message], Coroutine[Any, Any, None]]


class Dispatcher:
    """
    Maps IRC commands to async handler functions.

    Use ``"*"`` as the command to receive every message.
    """

    def __init__(self) -> None:
        self._handlers: defaultdict[str, list[AsyncHandler]] = defaultdict(list)

    def on(self, command: str) -> Callable[[AsyncHandler], None]:
        """Decorator that registers a handler for the given command."""

        def decorator(func: AsyncHandler) -> None:
            self._handlers[command.upper()].append(func)

        return decorator

    def add_handler(self, command: str, handler: AsyncHandler) -> None:
        """Register a handler imperatively (no decorator)."""
        self._handlers[command.upper()].append(handler)

    async def emit(self, message: Message) -> None:
        """Call all handlers registered for this message's command (and wildcard)."""
        handlers = self._handlers.get(message.command, []) + self._handlers.get("*", [])
        if not handlers:
            return
        async with asyncio.TaskGroup() as tg:
            for handler in handlers:
                tg.create_task(handler(message))
