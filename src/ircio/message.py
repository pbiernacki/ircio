# SPDX-FileCopyrightText: 2026 Paweł Biernacki
# SPDX-License-Identifier: MIT

from dataclasses import dataclass, field

_STRIP_CTRL = str.maketrans("", "", "\r\n\0")
_STRIP_TAG_KEY = str.maketrans("", "", "\r\n\0; =")
_STRIP_MIDDLE = str.maketrans("", "", "\r\n\0 ")

_TAG_VALUE_ESCAPE = str.maketrans(
    {
        "\\": "\\\\",
        ";": "\\:",
        " ": "\\s",
        "\r": "\\r",
        "\n": "\\n",
        "\0": "",
    }
)

_TAG_UNESCAPE: dict[str, str] = {
    ":": ";",
    "s": " ",
    "\\": "\\",
    "r": "\r",
    "n": "\n",
}


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
                    # unescape IRCv3 tag value
                    out, i = [], 0
                    while i < len(v):
                        if v[i] == "\\" and i + 1 < len(v):
                            out.append(_TAG_UNESCAPE.get(v[i + 1], v[i + 1]))
                            i += 2
                        else:
                            out.append(v[i])
                            i += 1
                    tags[k] = "".join(out)
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
            tag_str = ";".join(
                f"{k.translate(_STRIP_TAG_KEY)}={v.translate(_TAG_VALUE_ESCAPE)}"
                if v
                else k.translate(_STRIP_TAG_KEY)
                for k, v in self.tags.items()
            )
            parts.append(f"@{tag_str}")

        if self.prefix:
            parts.append(f":{self.prefix.translate(_STRIP_CTRL)}")

        parts.append(self.command.translate(_STRIP_CTRL))

        if self.params:
            *middle, last = self.params
            parts.extend(p.translate(_STRIP_MIDDLE) for p in middle)
            last = last.translate(_STRIP_CTRL)
            # Use trailing syntax when the last param contains spaces,
            # starts with ':', or is empty.
            if not last or " " in last or last.startswith(":"):
                parts.append(f":{last}")
            else:
                parts.append(last)

        return " ".join(parts)
