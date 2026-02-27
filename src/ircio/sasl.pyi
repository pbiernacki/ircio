# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

from abc import ABC, abstractmethod
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey

class SASLMechanism(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...
    @abstractmethod
    def step(self, challenge: bytes) -> bytes: ...
    def reset(self) -> None: ...

class SASLPlain(SASLMechanism):
    username: str
    password: str
    authzid: str
    def __init__(self, username: str, password: str, authzid: str = ...) -> None: ...
    def step(self, challenge: bytes) -> bytes: ...

class SASLExternal(SASLMechanism):
    def step(self, challenge: bytes) -> bytes: ...

class SASLEcdsaNist256pChallenge(SASLMechanism):
    username: str
    def __init__(self, username: str, private_key: EllipticCurvePrivateKey) -> None: ...
    @classmethod
    def from_pem_file(
        cls,
        username: str,
        path: str | Path,
        password: bytes | None = ...,
    ) -> SASLEcdsaNist256pChallenge: ...
    def reset(self) -> None: ...
    def step(self, challenge: bytes) -> bytes: ...
