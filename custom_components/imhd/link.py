"""Parse an imhd.sk live board link (`https://imhd.sk/<city>/online-zastavkova-tabula?st=83;270`)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlsplit

from .const import CITIES

HOSTS = frozenset({"imhd.sk", "www.imhd.sk", "m.imhd.sk"})
_ID = re.compile(r"^g?(\d+)$", re.IGNORECASE)


class LinkError(ValueError):
    """The link cannot be used; `code` is the config flow error key."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class BoardLink:
    """City code and stop ids of one board link."""

    city: str
    stop_ids: tuple[int, ...]


def parse_board_link(text: str) -> BoardLink:
    """Read the city (first path segment) and the stop ids (`st`) of a board link."""
    raw = text.strip()
    if not raw:
        raise LinkError("invalid_link")
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        parts = urlsplit(raw)
    except ValueError as err:
        raise LinkError("invalid_link") from err
    if (parts.hostname or "").lower() not in HOSTS:
        raise LinkError("invalid_link")
    segments = [s for s in parts.path.split("/") if s]
    if not segments:
        raise LinkError("invalid_link")
    city = unquote(segments[0]).lower()
    if city not in CITIES:
        raise LinkError("unknown_city")

    ids: list[int] = []
    # parse_qs decodes %3B; `;` and `,` both separate ids.
    for value in parse_qs(parts.query, keep_blank_values=True).get("st", []):
        for part in re.split(r"[;,]", value):
            match = _ID.match(part.strip())
            if match is None:
                continue
            stop_id = int(match.group(1))
            if stop_id > 0 and stop_id not in ids:
                ids.append(stop_id)
    if not ids:
        raise LinkError("no_stops")
    return BoardLink(city=city, stop_ids=tuple(ids))
