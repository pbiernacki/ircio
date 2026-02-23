# ircio

An asynchronous IRC client library for Python 3.14+, built on top of `asyncio`.

## Features

- **Fully async** — all I/O is non-blocking via `asyncio.StreamReader`/`StreamWriter`
- **IRCv3 message tags** — parsed and serialised transparently
- **TLS** — plain `ssl=True` for system CA verification, or pass a custom `ssl.SSLContext` for client certificates and private networks
- **SASL authentication**
  - `PLAIN` — username and password (RFC 4616)
  - `EXTERNAL` — identity delegated to the TLS certificate
  - `ECDSA-NIST256P-CHALLENGE` — challenge–response using an ECDSA key on the NIST P-256 curve (used by Libera.Chat and other networks)
- **Event dispatcher** — register async handlers per command, with wildcard (`"*"`) support
- **Structured concurrency** — handlers are dispatched via `asyncio.TaskGroup`

## Requirements

- Python ≥ 3.14
- [uv](https://docs.astral.sh/uv/) (recommended) or any PEP 517-compatible build tool

Optional, for ECDSA-NIST256P-CHALLENGE:

```
pip install "ircio[ecdsa]"
```

## Quick start

```python
import asyncio
from ircio import Client

client = Client(
    "irc.libera.chat",
    6697,
    nick="mybot",
    user="mybot",
    realname="My Bot",
    ssl=True,
)

@client.on("PRIVMSG")
async def on_privmsg(msg):
    target = msg.params[0]
    text   = msg.params[1]
    print(f"[{target}] {msg.prefix}: {text}")

async def main():
    await client.connect()
    await client.join("#python")
    await client.run()

asyncio.run(main())
```

## SASL authentication

### PLAIN

```python
from ircio import Client, SASLPlain

client = Client(
    "irc.libera.chat", 6697,
    nick="mybot", user="mybot", realname="My Bot",
    ssl=True,
    sasl=SASLPlain("mybot", "s3cr3t"),
)
```

### ECDSA-NIST256P-CHALLENGE

Register your public key with NickServ, then authenticate using the corresponding private key:

```python
from ircio import Client, SASLEcdsaNist256pChallenge

sasl = SASLEcdsaNist256pChallenge.from_pem_file("mybot", "~/.irc/key.pem")

client = Client(
    "irc.libera.chat", 6697,
    nick="mybot", user="mybot", realname="My Bot",
    ssl=True,
    sasl=sasl,
)
```

Generate a key with OpenSSL:

```bash
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out ~/.irc/key.pem
openssl pkey -in ~/.irc/key.pem -pubout
```

Provide the public key to NickServ: `/msg NickServ SET PUBKEY <base64-pubkey>`.

### EXTERNAL (client certificate)

```python
import ssl
from ircio import Client, SASLExternal

ctx = ssl.create_default_context()
ctx.load_cert_chain("cert.pem", "key.pem")

client = Client(
    "irc.libera.chat", 6697,
    nick="mybot", user="mybot", realname="My Bot",
    ssl=ctx,
    sasl=SASLExternal(),
)
```

## Low-level API

`Connection` and `Dispatcher` are exposed for use cases that require finer control:

```python
from ircio import Connection, Dispatcher, Message

async def main():
    async with Connection("irc.libera.chat", 6697, ssl=True) as conn:
        await conn.send(Message("NICK", ["mybot"]))
        await conn.send(Message("USER", ["mybot", "0", "*", "My Bot"]))
        while True:
            msg = await conn.readline()
            print(msg)
```

## Development

```bash
uv sync
uv run pytest
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

Pre-commit hooks (ruff linter + formatter) are installed automatically on first commit after:

```bash
uv run pre-commit install
```

## Licence

MIT — see [LICENSE](LICENSE).
