# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

import inspect
from unittest.mock import MagicMock

import pytest

from ircio.sasl import (
    SASLEcdsaNist256pChallenge,
    SASLExternal,
    SASLMechanism,
    SASLPlain,
)

# ---------------------------------------------------------------------------
# SASLMechanism ABC
# ---------------------------------------------------------------------------


def test_sasl_is_abstract():
    assert inspect.isabstract(SASLMechanism)


# ---------------------------------------------------------------------------
# SASLPlain
# ---------------------------------------------------------------------------


def test_sasl_plain_step_no_authzid():
    sasl = SASLPlain("user", "secret")
    assert sasl.step(b"").decode() == "\0user\0secret"


def test_sasl_plain_step_with_authzid():
    sasl = SASLPlain("user", "pass", authzid="authz")
    assert sasl.step(b"").decode() == "authz\0user\0pass"


# ---------------------------------------------------------------------------
# SASLExternal
# ---------------------------------------------------------------------------


def test_sasl_external_step_returns_empty():
    assert SASLExternal().step(b"") == b""


# ---------------------------------------------------------------------------
# SASLEcdsaNist256pChallenge
# ---------------------------------------------------------------------------


def test_sasl_ecdsa_step0_returns_username():
    sasl = SASLEcdsaNist256pChallenge("testnick", MagicMock())
    assert sasl.step(b"") == b"testnick"


def test_sasl_ecdsa_step1_signs_challenge():
    key = MagicMock()
    key.sign.return_value = b"der_signature"
    sasl = SASLEcdsaNist256pChallenge("nick", key)

    sasl.step(b"")  # step 0: username
    challenge = b"\x42" * 32
    result = sasl.step(challenge)

    assert result == b"der_signature"
    assert key.sign.call_count == 1
    # First positional arg must be the raw challenge bytes
    assert key.sign.call_args.args[0] == challenge


def test_sasl_ecdsa_reset():
    key = MagicMock()
    key.sign.return_value = b"sig"
    sasl = SASLEcdsaNist256pChallenge("nick", key)

    sasl.step(b"")  # step 0
    sasl.step(b"\x00" * 32)  # step 1
    sasl.reset()

    assert sasl._step == 0
    # After reset, step 0 should return the username again
    assert sasl.step(b"") == b"nick"


def test_sasl_ecdsa_step2_raises():
    from ircio.exceptions import IRCAuthenticationError

    key = MagicMock()
    key.sign.return_value = b"sig"
    sasl = SASLEcdsaNist256pChallenge("nick", key)

    sasl.step(b"")  # step 0
    sasl.step(b"\x00" * 32)  # step 1
    with pytest.raises(IRCAuthenticationError):
        sasl.step(b"\xff" * 32)  # step 2 — must be rejected
    assert key.sign.call_count == 1  # signed only once


def test_sasl_ecdsa_real_signature(tmp_path):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    key_file = tmp_path / "key.pem"
    key_file.write_bytes(pem)

    sasl = SASLEcdsaNist256pChallenge.from_pem_file("nick", key_file)
    sasl.step(b"")  # step 0

    challenge = b"\xab" * 32
    signature = sasl.step(challenge)

    # Verify the signature is a valid ECDSA-P256-SHA256 signature
    key.public_key().verify(signature, challenge, ec.ECDSA(hashes.SHA256()))
