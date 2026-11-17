"""One live iMHD connection per configured stop, with reconnect backoff."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .board import Board, apply_tabs
from .client import run_board
from .const import BOARD_PAGE_URL_FORMAT, LINE_CSS_URL, META_REFRESH_S, REJECTED_S, RETRY_MAX_S, RETRY_MIN_S
from .meta import LineColors, MetaError, fetch_text, parse_line_css, parse_platform_labels

_LOGGER = logging.getLogger(__name__)


class _Refused(Exception):
    """iMHD answered `cack` with something else than `true`."""

    def __init__(self, ack: bool) -> None:
        super().__init__(f"cack {ack}")


class StopConnection:
    """The live board of one iMHD stop: owns the board and the background connection task."""

    def __init__(self, entry: ConfigEntry, city: str, stop_id: int, user_agent: str) -> None:
        self.entry = entry
        self.city = city
        self.stop_id = stop_id
        self.user_agent = user_agent
        self.board: Board = {}
        # Epoch ms of the last push; None = none yet.
        self.received_at_ms: float | None = None
        # The last connection attempt failed or iMHD refused the stop.
        self.failing = False
        self.listeners: list[Callable[[], None]] = []
        self._task: asyncio.Task[None] | None = None
        self._failures = 0
        self._warned_rejected = False

    @callback
    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call `listener` on every change; returns the remover."""
        self.listeners.append(listener)

        def remove() -> None:
            if listener in self.listeners:
                self.listeners.remove(listener)

        return remove

    @callback
    def notify(self) -> None:
        """Call every listener."""
        for listener in list(self.listeners):
            listener()

    @callback
    def async_start(self, hass: HomeAssistant, session: aiohttp.ClientSession) -> None:
        """Start the connection loop in the background."""
        self._task = self.entry.async_create_background_task(
            hass, self._run(session), f"imhd board {self.city} {self.stop_id}"
        )

    async def async_stop(self) -> None:
        """Cancel the connection loop (sends `dataStop` best effort)."""
        task, self._task = self._task, None
        if task is None or task.done():
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    @callback
    def _on_ack(self, ok: bool) -> None:
        if not ok:
            raise _Refused(ok)
        self._failures = 0
        self._warned_rejected = False
        if self.failing:
            self.failing = False
            self.notify()

    @callback
    def _on_tabs(self, push: object) -> None:
        if not apply_tabs(self.board, push):
            return
        self.received_at_ms = time.time() * 1000
        self.failing = False
        self.notify()

    async def _run(self, session: aiohttp.ClientSession) -> None:
        while True:
            try:
                await run_board(session, self.city, self.stop_id, self.user_agent, self._on_ack, self._on_tabs)
            except _Refused:
                if not self._warned_rejected:
                    self._warned_rejected = True
                    _LOGGER.warning(
                        "iMHD refused stop %s in %s; retrying in %d min", self.stop_id, self.city, REJECTED_S // 60
                    )
                self.failing = True
                self.notify()
                await asyncio.sleep(REJECTED_S)
                continue
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - any network problem means reconnect
                _LOGGER.debug("iMHD stop %s connection failed: %s", self.stop_id, err)
            else:
                _LOGGER.debug("iMHD stop %s connection closed", self.stop_id)
            delay = min(RETRY_MAX_S, RETRY_MIN_S * 2**self._failures)
            self._failures += 1
            self.failing = True
            self.notify()
            await asyncio.sleep(delay)


@dataclass
class ImhdRuntime:
    """`entry.runtime_data`: the city, one connection per stop id and the website metadata."""

    city: str
    connections: dict[int, StopConnection] = field(default_factory=dict)
    # Stop id -> platform id -> letter as iMHD shows it ("A").
    platform_labels: dict[int, dict[int, str]] = field(default_factory=dict)
    line_colors: LineColors | None = None


class StopMeta:
    """Loads the line colors and every stop's platform letters on start and then once a day."""

    def __init__(self, entry: ConfigEntry, runtime: ImhdRuntime, user_agent: str) -> None:
        self.entry = entry
        self.runtime = runtime
        self.user_agent = user_agent

    @callback
    def async_start(self, hass: HomeAssistant, session: aiohttp.ClientSession) -> None:
        """Start the refresh loop in the background (cancelled with the entry)."""
        self.entry.async_create_background_task(hass, self._run(session), f"imhd meta {self.runtime.city}")

    async def _run(self, session: aiohttp.ClientSession) -> None:
        while True:
            await self.async_refresh(session)
            await asyncio.sleep(META_REFRESH_S)

    async def async_refresh(self, session: aiohttp.ClientSession) -> None:
        """Fetch linky.css once and every stop's board page; on error keep the previous values."""
        runtime = self.runtime
        changed = False
        try:
            colors = parse_line_css(await fetch_text(session, LINE_CSS_URL, self.user_agent), runtime.city)
        except (aiohttp.ClientError, TimeoutError, MetaError) as err:
            _LOGGER.debug("iMHD line colors failed: %s", err)
        else:
            if colors.exact or colors.prefixes:
                runtime.line_colors = colors
                changed = True
        for stop_id in runtime.connections:
            url = BOARD_PAGE_URL_FORMAT.format(city=runtime.city, stop_id=stop_id)
            try:
                labels = parse_platform_labels(await fetch_text(session, url, self.user_agent))
            except (aiohttp.ClientError, TimeoutError, MetaError) as err:
                _LOGGER.debug("iMHD platform labels of stop %s failed: %s", stop_id, err)
                continue
            if labels:
                runtime.platform_labels[stop_id] = labels
                changed = True
        if changed:
            for connection in runtime.connections.values():
                connection.notify()
