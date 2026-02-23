# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

from dataclasses import dataclass, field


@dataclass
class Message:
    """
    Represents a single IRC message (RFC 1459 + IRCv3 message tags).

    Wire format:
        [@tags] [:prefix] <command> [params] [:trailing]
    """

    command: str
    params: list[str] = field(default_factory=list)
    prefix: str | None = None
    tags: dict[str, str] = field(default_factory=dict)

    @classmethod
    def parse(cls, raw: str) -> Message:
        """Parse a raw IRC line into a Message. Strips trailing CR/LF."""
        raw = raw.rstrip("\r\n")
        tags: dict[str, str] = {}
        prefix: str | None = None

        # IRCv3 tags: @key=value;key2
        if raw.startswith("@"):
            tag_str, _, raw = raw[1:].partition(" ")
            for tag in tag_str.split(";"):
                if not tag:
                    continue
                if "=" in tag:
                    k, _, v = tag.partition("=")
                    tags[k] = v
                else:
                    tags[tag] = ""

        # Prefix
        if raw.startswith(":"):
            prefix, _, raw = raw[1:].partition(" ")

        # Command + params
        params: list[str] = []
        if " " in raw:
            command, _, rest = raw.partition(" ")
            while rest:
                if rest.startswith(":"):
                    params.append(rest[1:])
                    break
                if " " in rest:
                    param, _, rest = rest.partition(" ")
                    params.append(param)
                else:
                    params.append(rest)
                    break
        else:
            command = raw

        return cls(command=command.upper(), params=params, prefix=prefix, tags=tags)

    def __str__(self) -> str:
        """Serialize back to wire format (without trailing CRLF)."""
        parts: list[str] = []

        if self.tags:
            tag_str = ";".join(f"{k}={v}" if v else k for k, v in self.tags.items())
            parts.append(f"@{tag_str}")

        if self.prefix:
            parts.append(f":{self.prefix}")

        parts.append(self.command)

        if self.params:
            *middle, last = self.params
            parts.extend(middle)
            # Use trailing syntax when the last param contains spaces,
            # starts with ':', or is empty.
            if not last or " " in last or last.startswith(":"):
                parts.append(f":{last}")
            else:
                parts.append(last)

        return " ".join(parts)
