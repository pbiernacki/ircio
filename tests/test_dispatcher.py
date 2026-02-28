# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

import pytest

from ircio.dispatcher import Dispatcher
from ircio.exceptions import IRCHandlerError
from ircio.message import Message


@pytest.fixture
def dispatcher() -> Dispatcher:
    return Dispatcher()


async def test_handler_called(dispatcher: Dispatcher):
    results: list[str] = []

    @dispatcher.on("PING")
    async def on_ping(msg: Message) -> None:
        results.append(msg.command)

    await dispatcher.emit(Message.parse("PING :srv"))
    assert results == ["PING"]


async def test_wildcard_handler(dispatcher: Dispatcher):
    results: list[str] = []

    @dispatcher.on("*")
    async def catch_all(msg: Message) -> None:
        results.append(msg.command)

    await dispatcher.emit(Message.parse("PING :srv"))
    await dispatcher.emit(Message.parse(":s 001 n :Welcome"))
    assert results == ["PING", "001"]


async def test_wildcard_combined_with_specific(dispatcher: Dispatcher):
    specific: list[str] = []
    wildcard: list[str] = []

    @dispatcher.on("PRIVMSG")
    async def on_privmsg(msg: Message) -> None:
        specific.append("specific")

    @dispatcher.on("*")
    async def catch_all(msg: Message) -> None:
        wildcard.append("wildcard")

    await dispatcher.emit(Message.parse(":n!u@h PRIVMSG #ch :hi"))
    assert specific == ["specific"]
    assert wildcard == ["wildcard"]


async def test_multiple_handlers_same_command(dispatcher: Dispatcher):
    calls: list[int] = []

    @dispatcher.on("PRIVMSG")
    async def h1(msg: Message) -> None:
        calls.append(1)

    @dispatcher.on("PRIVMSG")
    async def h2(msg: Message) -> None:
        calls.append(2)

    await dispatcher.emit(Message.parse(":n!u@h PRIVMSG #c :hi"))
    assert sorted(calls) == [1, 2]


async def test_no_handler_no_error(dispatcher: Dispatcher):
    # Should not raise when no handler is registered
    await dispatcher.emit(Message.parse("UNKNOWN_CMD"))


async def test_add_handler_method(dispatcher: Dispatcher):
    results: list[str] = []

    async def handler(msg: Message) -> None:
        results.append(msg.command)

    dispatcher.add_handler("NOTICE", handler)
    await dispatcher.emit(Message.parse(":s NOTICE #ch :test"))
    assert results == ["NOTICE"]


async def test_handler_receives_message(dispatcher: Dispatcher):
    received: list[Message] = []

    @dispatcher.on("PRIVMSG")
    async def on_privmsg(msg: Message) -> None:
        received.append(msg)

    msg = Message.parse(":nick!u@h PRIVMSG #ch :hello")
    await dispatcher.emit(msg)
    assert len(received) == 1
    assert received[0].params == ["#ch", "hello"]


async def test_emit_single_handler_error(dispatcher: Dispatcher):
    async def bad(msg: Message) -> None:
        raise ValueError("oops")

    dispatcher.add_handler("PRIVMSG", bad)
    with pytest.raises(ValueError, match="oops"):
        await dispatcher.emit(Message("PRIVMSG", ["#c", "hi"]))


async def test_emit_multi_handler_one_error(dispatcher: Dispatcher):
    called: list[int] = []

    async def ok(msg: Message) -> None:
        called.append(1)

    async def bad(msg: Message) -> None:
        raise RuntimeError("boom")

    dispatcher.add_handler("PRIVMSG", ok)
    dispatcher.add_handler("PRIVMSG", bad)
    with pytest.raises(RuntimeError, match="boom"):
        await dispatcher.emit(Message("PRIVMSG", ["#c", "hi"]))
    assert called == [1]


async def test_emit_multi_handler_all_errors(dispatcher: Dispatcher):
    async def bad1(msg: Message) -> None:
        raise ValueError("v")

    async def bad2(msg: Message) -> None:
        raise RuntimeError("r")

    dispatcher.add_handler("PRIVMSG", bad1)
    dispatcher.add_handler("PRIVMSG", bad2)
    with pytest.raises(IRCHandlerError) as exc_info:
        await dispatcher.emit(Message("PRIVMSG", ["#c", "hi"]))
    assert len(exc_info.value.errors) == 2
