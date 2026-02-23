# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT


class IRCError(Exception):
    """Base exception for ircio."""


class IRCConnectionError(IRCError):
    """Raised when a connection fails or is lost."""


class IRCParseError(IRCError):
    """Raised when an IRC message cannot be parsed."""


class IRCAuthenticationError(IRCError):
    """Raised when SASL or password authentication fails."""
