"""iMHD stop search (the website endpoint `GET /<city>/api/sk/vyhladavanie?q=`)."""

from __future__ import annotations

import re
from dataclasses import dataclass

import aiohttp

from .const import QUERY_MAX, QUERY_MIN, SEARCH_TIMEOUT_S, SEARCH_URL_FORMAT

_STOP_VALUE = re.compile(r"^g(\d+)$")


class SearchError(Exception):
    """iMHD answered with an error or an unexpected body."""


@dataclass(frozen=True)
class StopHit:
    """One stop found by the search."""

    stop_id: int
    name: str


def clean_query(query: str) -> str:
    """Trim, collapse whitespace and cut to the max length."""
    return " ".join(query.split())[:QUERY_MAX]


def parse_search(raw: object) -> list[StopHit]:
    """Keep only `class: stop` entries with `value` `g<id>`, distinct by id, in iMHD order."""
    if not isinstance(raw, dict) or not isinstance(raw.get("results"), list):
        raise SearchError("iMHD search: unexpected response")
    seen: set[int] = set()
    hits: list[StopHit] = []
    for entry in raw["results"]:
        # iMHD mixes stops with streets and documents that have no `value`.
        if not isinstance(entry, dict) or entry.get("class") != "stop":
            continue
        name, value = entry.get("name"), entry.get("value")
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        match = _STOP_VALUE.match(value)
        if match is None or not name.strip():
            continue
        stop_id = int(match.group(1))
        if stop_id <= 0 or stop_id in seen:
            continue
        seen.add(stop_id)
        hits.append(StopHit(stop_id=stop_id, name=name.strip()))
    return hits


async def search_stops(session: aiohttp.ClientSession, city: str, query: str, user_agent: str) -> list[StopHit]:
    """Stops of `city` matching `query`; text shorter than 2 characters = []."""
    text = clean_query(query)
    if len(text) < QUERY_MIN:
        return []
    headers = {"accept": "application/json", "x-requested-with": "XMLHttpRequest", "user-agent": user_agent}
    async with session.get(
        SEARCH_URL_FORMAT.format(city=city),
        params={"q": text},
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=SEARCH_TIMEOUT_S),
    ) as response:
        if response.status != 200:
            raise SearchError(f"iMHD search answered HTTP {response.status}")
        try:
            body: object = await response.json(content_type=None)
        except ValueError as err:
            raise SearchError("iMHD search: unexpected response") from err
    return parse_search(body)
