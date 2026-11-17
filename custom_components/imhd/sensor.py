"""One "next departure" sensor per configured stop."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from . import ImhdConfigEntry
from .board import Status, board_departures, board_status, iso_ms
from .const import (
    CITIES,
    CONF_STOPS,
    DOMAIN,
    STOP_ID,
    STOP_LABEL,
    STOP_LINES,
    STOP_WALK_MIN,
    TICK_S,
    WRITE_THROTTLE_S,
)
from .hub import ImhdRuntime, StopConnection


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImhdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add one sensor per configured stop."""
    runtime = entry.runtime_data
    registry = er.async_get(hass)
    entities: list[ImhdDepartureSensor] = []
    for stop in entry.options.get(CONF_STOPS, []):
        stop_id = int(stop[STOP_ID])
        sensor = ImhdDepartureSensor(runtime, stop, runtime.connections[stop_id])
        # Pick a readable entity id only the first time; later the registry keeps it.
        if registry.async_get_entity_id("sensor", DOMAIN, sensor.unique_id or "") is None:
            sensor.entity_id = async_generate_entity_id("sensor.imhd_{}", slugify(stop[STOP_LABEL]), hass=hass)
        entities.append(sensor)
    async_add_entities(entities)


class ImhdDepartureSensor(SensorEntity):
    """State = the next departure time; attribute `departures` = the board."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_departure"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:bus-clock"
    _attr_should_poll = False
    _unrecorded_attributes = frozenset({"departures", "last_live", "status"})

    def __init__(self, runtime: ImhdRuntime, stop: dict[str, Any], connection: StopConnection) -> None:
        city = runtime.city
        self._runtime = runtime
        self._city = city
        self._connection = connection
        self._stop_id = int(stop[STOP_ID])
        self._stop_name: str = stop[STOP_LABEL]
        self._walk_min = int(stop.get(STOP_WALK_MIN, 0))
        self._lines: list[str] = list(stop.get(STOP_LINES, []))
        self._status: Status | None = None
        self._last_write = 0.0
        self._pending: Callable[[], None] | None = None
        self._attr_unique_id = f"{city}_{self._stop_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{city}_{self._stop_id}")},
            name=stop[STOP_LABEL],
            manufacturer="iMHD",
            model=CITIES.get(city, city),
            entry_type=DeviceEntryType.SERVICE,
        )
        self._refresh()

    async def async_added_to_hass(self) -> None:
        """Follow the hub and tick every 30 s."""
        self.async_on_remove(self._connection.add_listener(self._on_hub))
        self.async_on_remove(async_track_time_interval(self.hass, self._on_tick, timedelta(seconds=TICK_S)))
        self.async_on_remove(self._cancel_pending)

    @callback
    def _cancel_pending(self) -> None:
        if self._pending is not None:
            self._pending()
            self._pending = None

    def _refresh(self) -> Status:
        """Recompute state and attributes from the board."""
        connection = self._connection
        now_ms = time.time() * 1000
        status = board_status(connection.received_at_ms, connection.failing, now_ms)
        # Stale boards show no departures (a vehicle "in 2 min" from 10 min ago misleads).
        runtime = self._runtime
        departures = (
            board_departures(
                connection.board,
                self._lines,
                now_ms,
                self._city,
                runtime.platform_labels.get(self._stop_id),
                runtime.line_colors,
            )
            if status == "live"
            else []
        )
        value: datetime | None = dt_util.parse_datetime(departures[0]["departs_at"]) if departures else None
        self._attr_native_value = value
        self._attr_extra_state_attributes = {
            "departures": departures,
            "status": status,
            "last_live": iso_ms(connection.received_at_ms) if connection.received_at_ms is not None else None,
            "stop_id": self._stop_id,
            "stop_name": self._stop_name,
            "city": self._city,
            "walk_min": self._walk_min,
            "lines": self._lines,
        }
        return status

    @callback
    def _write(self, *_: Any) -> None:
        self._cancel_pending()
        self._status = self._refresh()
        self._last_write = time.monotonic()
        self.async_write_ha_state()

    @callback
    def _on_hub(self) -> None:
        """Write at most once per 10 s, but a status change right away."""
        connection = self._connection
        status = board_status(connection.received_at_ms, connection.failing, time.time() * 1000)
        if status != self._status:
            self._write()
            return
        wait = WRITE_THROTTLE_S - (time.monotonic() - self._last_write)
        if wait <= 0:
            self._write()
        elif self._pending is None:
            self._pending = async_call_later(self.hass, wait, self._write)

    @callback
    def _on_tick(self, _now: datetime) -> None:
        # Drops departed vehicles and flips live -> stale without a push.
        self._write()
