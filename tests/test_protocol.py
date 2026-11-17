"""Engine.IO / Socket.IO text frames."""

from __future__ import annotations

from custom_components.imhd.protocol import (
    CONNECT,
    DISCONNECT,
    PONG,
    Close,
    Connected,
    Disconnected,
    Event,
    Open,
    Ping,
    Unknown,
    event,
    parse_frame,
)


def test_open() -> None:
    frame = parse_frame('0{"sid":"abc","upgrades":[],"pingInterval":25000,"pingTimeout":20000,"maxPayload":1000000}')
    assert frame == Open(25_000, 20_000)
    assert parse_frame("0{}") == Open(25_000, 20_000)
    assert parse_frame("0nope") == Unknown("0nope")


def test_control_frames() -> None:
    assert parse_frame("1") == Close()
    assert parse_frame("2") == Ping()
    assert parse_frame('40{"sid":"x"}') == Connected()
    assert parse_frame("40") == Connected()
    assert parse_frame("41") == Disconnected()


def test_events() -> None:
    assert parse_frame('42["cack",true]') == Event("cack", [True])
    assert parse_frame('42["tabs",[{"a":1}]]') == Event("tabs", [[{"a": 1}]])
    # an event with an ack id
    assert parse_frame('4217["cack",false]') == Event("cack", [False])
    assert parse_frame("42[]") == Unknown("42[]")
    assert parse_frame("42{bad") == Unknown("42{bad")
    assert parse_frame("6") == Unknown("6")


def test_outgoing() -> None:
    assert (PONG, CONNECT, DISCONNECT) == ("3", "40", "41")
    assert event("tabStart", [101, ["*"], "ba"]) == '42["tabStart",[101,["*"],"ba"]]'
    assert event("dataStop") == '42["dataStop"]'
