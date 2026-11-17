"""A minimal Socket.IO 4 client for one iMHD live board (aiohttp WebSocket only, no Home Assistant imports)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable

import aiohttp

from .const import ORIGIN, SOCKET_URL
from .protocol import (
    CONNECT,
    DISCONNECT,
    PONG,
    Close,
    Connected,
    Disconnected,
    Event,
    Open,
    Ping,
    event,
    parse_frame,
)

_LOGGER = logging.getLogger(__name__)

# Engine.IO defaults until the server sends its own timings.
_DEFAULT_PING_INTERVAL_MS = 25_000
_DEFAULT_PING_TIMEOUT_MS = 20_000

# Set once iMHD refused a handshake without `Origin`; later connections send it right away.
_use_origin = False


class BoardTimeout(Exception):
    """No frame from iMHD within ping interval + ping timeout."""


async def _connect(session: aiohttp.ClientSession, user_agent: str) -> aiohttp.ClientWebSocketResponse:
    global _use_origin
    headers = {"User-Agent": user_agent}
    if _use_origin:
        headers["Origin"] = ORIGIN
    try:
        return await session.ws_connect(SOCKET_URL, headers=headers, heartbeat=None)
    except aiohttp.WSServerHandshakeError as err:
        if _use_origin or err.status not in (400, 403):
            raise
        _LOGGER.debug("iMHD handshake answered HTTP %s, retrying with Origin", err.status)
    ws = await session.ws_connect(SOCKET_URL, headers={**headers, "Origin": ORIGIN}, heartbeat=None)
    _use_origin = True
    return ws


async def run_board(
    session: aiohttp.ClientSession,
    city: str,
    stop_id: int,
    user_agent: str,
    on_ack: Callable[[bool], None],
    on_tabs: Callable[[object], None],
) -> None:
    """Keep one connection for `stop_id` until it ends (returns) or fails (raises)."""
    ws = await _connect(session, user_agent)
    try:
        timeout_s = (_DEFAULT_PING_INTERVAL_MS + _DEFAULT_PING_TIMEOUT_MS) / 1000
        while True:
            try:
                msg = await ws.receive(timeout=timeout_s)
            except TimeoutError as err:
                raise BoardTimeout(f"no frame from iMHD for {timeout_s:.0f} s") from err
            if msg.type is aiohttp.WSMsgType.ERROR:
                raise aiohttp.ClientError(f"iMHD socket error: {ws.exception()}")
            if msg.type is not aiohttp.WSMsgType.TEXT:
                # CLOSE, CLOSING, CLOSED (binary frames are not used by iMHD)
                if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                    return
                continue
            frame = parse_frame(msg.data)
            match frame:
                case Open(ping_interval_ms=interval, ping_timeout_ms=timeout):
                    timeout_s = (interval + timeout) / 1000
                    await ws.send_str(CONNECT)
                case Connected():
                    await ws.send_str(event("tabStart", [stop_id, ["*"], city]))
                case Ping():
                    await ws.send_str(PONG)
                case Event(name="cack", args=args):
                    on_ack(bool(args) and args[0] is True)
                case Event(name="tabs", args=args) if args:
                    on_tabs(args[0])
                case Close() | Disconnected():
                    return
                case _:
                    pass
    except asyncio.CancelledError:
        # Best effort: tell iMHD we leave, then let the cancel through.
        with contextlib.suppress(Exception):
            await ws.send_str(event("dataStop"))
            await ws.send_str(DISCONNECT)
        raise
    finally:
        if not ws.closed:
            with contextlib.suppress(Exception):
                await ws.close()
