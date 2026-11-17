"""The last known departures of one iMHD stop."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from .const import DEPARTED_GRACE_MS, DEPARTURES_PER_STOP, LIVE_MS
from .meta import LineColors, color_for

type Status = Literal["live", "connecting", "unavailable"]

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_TRAM = re.compile(r"^[1-9]$")
_TROLLEYBUS = re.compile(r"^[4-7]\d$")


@dataclass(frozen=True)
class Departure:
    """One departure of a `tabs` push. `cas` = expected (epoch ms), `cas_cp` = timetable, `cas_delta` = delay min."""

    line: str
    cel: str
    cas: float
    cas_cp: float
    cas_delta: float | None
    typ: str
    # The trip's terminus (`konecnaZstr`); `cel` (`cielStr`) can differ per stop for the same trip.
    konecna: str | None = None


@dataclass(frozen=True)
class Platform:
    """One platform (`nastupiste`) of a stop; each push replaces the platforms it carries."""

    timestamp: float
    departures: list[Departure]


type Board = dict[int, Platform]


def _number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _text(value: object) -> bool:
    return isinstance(value, str) and value != ""


def _departure(raw: object) -> Departure | None:
    if not isinstance(raw, dict):
        return None
    delta = raw.get("casDelta")
    # Some cities (e.g. Košice) send no `cielStr`; the terminus `konecnaZstr` is the destination then.
    cel = raw.get("cielStr") if _text(raw.get("cielStr")) else raw.get("konecnaZstr")
    if not (_text(raw.get("linka")) and _text(cel) and _number(raw.get("cas"))):
        return None
    if not (_number(raw.get("casCP")) and isinstance(raw.get("typ"), str)):
        return None
    if delta is not None and not _number(delta):
        return None
    return Departure(
        line=raw["linka"],
        cel=str(cel),
        cas=raw["cas"],
        cas_cp=raw["casCP"],
        cas_delta=delta,
        typ=raw["typ"],
        konecna=raw["konecnaZstr"] if _text(raw.get("konecnaZstr")) else None,
    )


def apply_tabs(board: Board, push: object) -> bool:
    """Apply one `tabs` push; unreadable departures are skipped. False when the push is not a platform array."""
    if not isinstance(push, list):
        return False
    applied = False
    for raw in push:
        if not isinstance(raw, dict):
            continue
        nastupiste, timestamp, tab = raw.get("nastupiste"), raw.get("timestamp"), raw.get("tab")
        if not (_number(raw.get("zastavka")) and _number(nastupiste) and _number(timestamp)):
            continue
        if not isinstance(tab, list):
            continue
        departures = [d for d in (_departure(item) for item in tab) if d is not None]
        board[int(nastupiste)] = Platform(timestamp=timestamp, departures=departures)
        applied = True
    return applied


def line_mode(city: str, line: str) -> str | None:
    """Bratislava: trams 1–9, trolleybuses 40–79, everything else a bus. Other cities: unknown (None)."""
    if city != "ba":
        return None
    if _TRAM.match(line):
        return "tram"
    if _TROLLEYBUS.match(line):
        return "trolleybus"
    return "bus"


def iso_ms(epoch_ms: float) -> str:
    """Epoch ms as ISO 8601 UTC with `Z` (like JavaScript `toISOString`)."""
    moment = _EPOCH + timedelta(milliseconds=epoch_ms)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def board_departures(
    board: Board | None,
    lines: list[str],
    now_ms: float,
    city: str,
    platform_labels: dict[int, str] | None = None,
    line_colors: LineColors | None = None,
) -> list[dict[str, Any]]:
    """All platforms merged (each row keeps its `platform`), filtered by `lines` (empty = all), departed dropped, sorted by expected time, max 10.

    `platform_label` = the letter iMHD shows for the platform, `color` / `text_color` = the iMHD line colors (None = unknown),
    `terminus` = the trip's terminus (`konecnaZstr`, else the destination).
    """
    if not board:
        return []
    wanted = {line.upper() for line in lines}
    seen: set[str] = set()
    merged: list[tuple[int, Departure]] = []
    for nastupiste, platform in board.items():
        for d in platform.departures:
            if wanted and d.line.upper() not in wanted:
                continue
            if d.cas < now_ms - DEPARTED_GRACE_MS:
                continue
            # iMHD may list one trip twice on a platform; keep it once.
            key = f"{d.line}|{d.cel}|{d.cas_cp}"
            if key in seen:
                continue
            seen.add(key)
            merged.append((nastupiste, d))
    merged.sort(key=lambda item: item[1].cas)
    result: list[dict[str, Any]] = []
    for nastupiste, d in merged[:DEPARTURES_PER_STOP]:
        realtime = d.typ == "online"
        color = color_for(line_colors, d.line)
        result.append(
            {
                "line": d.line,
                "mode": line_mode(city, d.line),
                "destination": d.cel,
                "terminus": d.konecna or d.cel,
                "departs_at": iso_ms(d.cas),
                "scheduled_at": iso_ms(d.cas_cp),
                "realtime": realtime,
                "delay_min": (d.cas_delta if d.cas_delta is not None else 0) if realtime else 0,
                "platform": nastupiste,
                "platform_label": (platform_labels or {}).get(nastupiste),
                "color": color.background if color is not None else None,
                "text_color": color.text if color is not None else None,
            }
        )
    return result


def board_status(received_at_ms: float | None, failing: bool, now_ms: float) -> Status:
    """`live` = a push younger than 2 min; else `unavailable` while failing, `connecting` otherwise."""
    if received_at_ms is not None and now_ms - received_at_ms < LIVE_MS:
        return "live"
    return "unavailable" if failing else "connecting"
