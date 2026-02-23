# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

import pytest

from ircio.message import Message


@pytest.fixture
def privmsg() -> Message:
    return Message.parse(":nick!user@host PRIVMSG #channel :Hello world")
