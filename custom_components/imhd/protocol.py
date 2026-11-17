"""Engine.IO 4 / Socket.IO 4 text packets (only what the iMHD board needs)."""

from __future__ import annotations

import json
from dataclasses import dataclass

PONG = "3"
CONNECT = "40"
DISCONNECT = "41"


@dataclass(frozen=True)
class Open:
    """Engine.IO handshake (`0{...}`)."""

    ping_interval_ms: int
    ping_timeout_ms: int


@dataclass(frozen=True)
class Ping:
    """Server ping (`2`); answer with PONG."""


@dataclass(frozen=True)
class Close:
    """Engine.IO close (`1`)."""


@dataclass(frozen=True)
class Connected:
    """Socket.IO namespace connected (`40...`)."""


@dataclass(frozen=True)
class Disconnected:
    """Socket.IO namespace disconnected (`41`)."""


@dataclass(frozen=True)
class Event:
    """Socket.IO event (`42[name, ...args]`, also `42<ackid>[...]`)."""

    name: str
    args: list[object]


@dataclass(frozen=True)
class Unknown:
    """Anything else."""

    text: str


type Frame = Open | Ping | Close | Connected | Disconnected | Event | Unknown


def _int(value: object, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def parse_frame(text: str) -> Frame:
    """Read one text frame."""
    if text.startswith("0"):
        try:
            data = json.loads(text[1:])
        except ValueError:
            return Unknown(text)
        if not isinstance(data, dict):
            return Unknown(text)
        return Open(_int(data.get("pingInterval"), 25_000), _int(data.get("pingTimeout"), 20_000))
    if text == "1":
        return Close()
    if text == "2":
        return Ping()
    if text.startswith("40"):
        return Connected()
    if text.startswith("41"):
        return Disconnected()
    if text.startswith("42"):
        body = text[2:].lstrip("0123456789")
        try:
            data = json.loads(body)
        except ValueError:
            return Unknown(text)
        if isinstance(data, list) and data and isinstance(data[0], str):
            return Event(data[0], list(data[1:]))
        return Unknown(text)
    return Unknown(text)


def event(name: str, *args: object) -> str:
    """A Socket.IO event packet."""
    return "42" + json.dumps([name, *args], separators=(",", ":"), ensure_ascii=False)
