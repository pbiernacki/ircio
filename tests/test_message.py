# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

from ircio.message import Message


class TestMessageParse:
    def test_simple_command(self):
        msg = Message.parse("PING :server.example.com")
        assert msg.command == "PING"
        assert msg.params == ["server.example.com"]
        assert msg.prefix is None
        assert msg.tags == {}

    def test_with_prefix(self):
        msg = Message.parse(":nick!user@host PRIVMSG #channel :Hello world")
        assert msg.command == "PRIVMSG"
        assert msg.prefix == "nick!user@host"
        assert msg.params == ["#channel", "Hello world"]

    def test_numeric_command(self):
        msg = Message.parse(":server 001 nick :Welcome to the network!")
        assert msg.command == "001"
        assert msg.params == ["nick", "Welcome to the network!"]

    def test_ircv3_tags(self):
        msg = Message.parse(
            "@time=2024-01-01T00:00:00Z;msgid=abc123 :nick!u@h PRIVMSG #ch :Hi"
        )
        assert msg.tags == {"time": "2024-01-01T00:00:00Z", "msgid": "abc123"}
        assert msg.command == "PRIVMSG"
        assert msg.prefix == "nick!u@h"

    def test_tag_without_value(self):
        msg = Message.parse("@server-time :nick!u@h PRIVMSG #ch :Hi")
        assert msg.tags == {"server-time": ""}

    def test_trailing_empty(self):
        msg = Message.parse("PRIVMSG #ch :")
        assert msg.params == ["#ch", ""]

    def test_crlf_stripped(self):
        msg = Message.parse("PING :srv\r\n")
        assert msg.command == "PING"
        assert msg.params == ["srv"]

    def test_multiple_middle_params(self):
        msg = Message.parse("MODE #channel +o someuser")
        assert msg.params == ["#channel", "+o", "someuser"]

    def test_command_uppercased(self):
        msg = Message.parse("privmsg #ch :hi")
        assert msg.command == "PRIVMSG"

    def test_no_params(self):
        msg = Message.parse(":server MOTD")
        assert msg.command == "MOTD"
        assert msg.params == []


class TestMessageStr:
    def test_round_trip_simple(self):
        # Trailing ':' is optional for single-word last params; parse → serialize
        # produces semantically identical output (no spaces, no leading ':').
        msg = Message.parse("PING :server.example.com")
        reparsed = Message.parse(str(msg))
        assert reparsed.command == msg.command
        assert reparsed.params == msg.params

    def test_round_trip_with_prefix(self):
        raw = ":nick!user@host PRIVMSG #channel :Hello world"
        assert str(Message.parse(raw)) == raw

    def test_round_trip_tags(self):
        # Same as test_round_trip_simple: single-word trailing without ':'  is valid.
        msg = Message.parse("@msgid=abc :nick!u@h PRIVMSG #ch :Hi")
        reparsed = Message.parse(str(msg))
        assert reparsed.tags == msg.tags
        assert reparsed.prefix == msg.prefix
        assert reparsed.command == msg.command
        assert reparsed.params == msg.params

    def test_build_privmsg_with_spaces(self):
        msg = Message("PRIVMSG", ["#channel", "hello world"])
        assert str(msg) == "PRIVMSG #channel :hello world"

    def test_build_simple_no_trailing(self):
        msg = Message("JOIN", ["#channel"])
        assert str(msg) == "JOIN #channel"

    def test_trailing_empty_param(self):
        msg = Message("QUIT", [""])
        assert str(msg) == "QUIT :"

    def test_trailing_colon_prefix(self):
        # Params that start with ':' must use trailing syntax
        msg = Message("TEST", [":starts-with-colon"])
        assert str(msg) == "TEST ::starts-with-colon"
