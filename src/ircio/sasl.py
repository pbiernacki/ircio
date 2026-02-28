# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from .exceptions import IRCAuthenticationError

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey

_CRYPTOGRAPHY_MISSING = (
    "The 'cryptography' package is required for ECDSA-NIST256P-CHALLENGE. "
    "Install it with: pip install 'ircio[ecdsa]'"
)


class SASLMechanism(ABC):
    """Abstract base for SASL authentication mechanisms."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Mechanism name as sent in the ``AUTHENTICATE`` CAP negotiation."""

    @abstractmethod
    def step(self, challenge: bytes) -> bytes:
        """
        Process one step of SASL authentication.

        Args:
            challenge: Raw (already base64-decoded) bytes from the server's
                       ``AUTHENTICATE`` message. ``b""`` when the server sent ``+``.

        Returns:
            Raw bytes for the client response (base64-encoding is done by the
            caller). Return ``b""`` to send ``+``.
        """

    def reset(self) -> None:  # noqa: B027
        """Reset authentication state (called automatically before each connect).

        Stateless mechanisms (PLAIN, EXTERNAL) do not need to override this.
        """


class SASLPlain(SASLMechanism):
    """
    SASL PLAIN mechanism (RFC 4616).

    Single-step: ``step(b"")`` → ``authzid NUL authcid NUL passwd``
    """

    @property
    def name(self) -> str:
        return "PLAIN"

    def __init__(self, username: str, password: str, authzid: str = "") -> None:
        self.username = username
        self.password = password
        self.authzid = authzid

    def step(self, challenge: bytes) -> bytes:
        payload = f"{self.authzid}\0{self.username}\0{self.password}"
        return payload.encode()


class SASLExternal(SASLMechanism):
    """
    SASL EXTERNAL mechanism — delegates identity to the TLS certificate.

    Single-step: ``step(b"")`` → ``b""`` (sends ``+``)
    """

    @property
    def name(self) -> str:
        return "EXTERNAL"

    def step(self, challenge: bytes) -> bytes:
        return b""


class SASLEcdsaNist256pChallenge(SASLMechanism):
    """
    SASL ECDSA-NIST256P-CHALLENGE mechanism (used by Libera.Chat et al.).

    Two-step flow:

    1. Server sends ``+``; client responds with the NickServ account name.
    2. Server sends a random challenge; client signs it with the ECDSA private
       key (NIST P-256 curve, SHA-256) and replies with the DER signature.

    Requires the ``cryptography`` package::

        pip install "ircio[ecdsa]"

    Usage::

        sasl = SASLEcdsaNist256pChallenge.from_pem_file("yournick", "~/.irc/key.pem")
        client = Client("irc.libera.chat", 6697, nick="yournick", ssl=True, sasl=sasl)
    """

    @property
    def name(self) -> str:
        return "ECDSA-NIST256P-CHALLENGE"

    def __init__(self, username: str, private_key: EllipticCurvePrivateKey) -> None:
        self.username = username
        self._private_key = private_key
        self._step = 0

    @classmethod
    def from_pem_file(
        cls,
        username: str,
        path: str | Path,
        password: bytes | None = None,
    ) -> SASLEcdsaNist256pChallenge:
        """Load the ECDSA private key from a PEM file."""
        try:
            from cryptography.hazmat.primitives.asymmetric.ec import (
                EllipticCurvePrivateKey,
            )
            from cryptography.hazmat.primitives.serialization import (
                load_pem_private_key,
            )
        except ImportError as exc:
            raise ImportError(_CRYPTOGRAPHY_MISSING) from exc

        key = load_pem_private_key(Path(path).read_bytes(), password=password)
        if not isinstance(key, EllipticCurvePrivateKey):
            raise ValueError("PEM file does not contain an EC private key")
        return cls(username, key)

    def reset(self) -> None:
        """Reset authentication state (called automatically before each connect)."""
        self._step = 0

    def step(self, challenge: bytes) -> bytes:
        if self._step == 0:
            self._step += 1
            return self.username.encode()

        if self._step == 1:
            self._step += 1
            # Sign the server challenge (DER-encoded ECDSA signature, SHA-256).
            try:
                from cryptography.hazmat.primitives import hashes
                from cryptography.hazmat.primitives.asymmetric import ec
            except ImportError as exc:
                raise ImportError(_CRYPTOGRAPHY_MISSING) from exc

            return self._private_key.sign(challenge, ec.ECDSA(hashes.SHA256()))

        raise IRCAuthenticationError(
            "Unexpected AUTHENTICATE message after ECDSA exchange completed"
        )
