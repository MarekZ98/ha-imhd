"""Live smoke test: search a stop, connect to its board and print what iMHD sends.

Usage: python scripts/smoke.py <city> "<stop name>"
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import types
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
# The package `__init__.py` imports Home Assistant; register empty packages and load only pure modules.
for name, path in (
    ("custom_components", ROOT / "custom_components"),
    ("custom_components.imhd", ROOT / "custom_components" / "imhd"),
):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
sys.path.insert(0, str(ROOT))

from custom_components.imhd.board import Board, apply_tabs, board_departures
from custom_components.imhd.client import run_board
from custom_components.imhd.const import BOARD_PAGE_URL_FORMAT, LINE_CSS_URL, USER_AGENT_FORMAT
from custom_components.imhd.meta import (
    LineColors,
    color_for,
    fetch_text,
    parse_line_css,
    parse_platform_labels,
)
from custom_components.imhd.search import search_stops

TIMEOUT_S = 25


async def main(city: str, query: str) -> int:
    version = json.loads((ROOT / "custom_components" / "imhd" / "manifest.json").read_text(encoding="utf-8"))["version"]
    user_agent = USER_AGENT_FORMAT.format(version=version)
    async with aiohttp.ClientSession() as session:
        hits = await search_stops(session, city, query, user_agent)
        print(f"search {city} {query!r}: {len(hits)} hits", ", ".join(f"{h.name} ({h.stop_id})" for h in hits[:5]))
        if not hits:
            return 1
        stop = hits[0]
        labels: dict[int, str] = {}
        colors: LineColors | None = None
        try:
            labels = parse_platform_labels(
                await fetch_text(session, BOARD_PAGE_URL_FORMAT.format(city=city, stop_id=stop.stop_id), user_agent)
            )
            colors = parse_line_css(await fetch_text(session, LINE_CSS_URL, user_agent), city)
        except Exception as err:  # noqa: BLE001 - the smoke test only reports
            print(f"meta failed: {err!r}")
        print(f"platform labels of {stop.stop_id}:", labels)
        if colors is not None:
            print(f"line colors: {len(colors.exact)} exact, prefixes {[p for p, _ in colors.prefixes]}")
        board: Board = {}
        done = asyncio.Event()

        def on_ack(ok: bool) -> None:
            print(f"cack: {ok}")
            if not ok:
                done.set()

        def on_tabs(push: object) -> None:
            if done.is_set() or not apply_tabs(board, push):
                return
            departures = board_departures(board, [], time.time() * 1000, city, labels, colors)
            print(f"tabs: {len(departures)} departures")
            for platform in push:  # type: ignore[union-attr]
                if isinstance(platform, dict):
                    tab = platform.get("tab")
                    count = len(tab) if isinstance(tab, list) else 0
                    print(f"  nastupiste {platform.get('nastupiste')} zastavka {platform.get('zastavka')}: {count} departures")
            raw = next((d for p in push if isinstance(p, dict) for d in p.get("tab", [])), None)  # type: ignore[union-attr]
            print("raw keys:", sorted(raw) if isinstance(raw, dict) else None)
            if departures:
                print("first:", departures[0])
            lines = list(dict.fromkeys(d["line"] for d in departures))[:5]
            for line in lines:
                print(f"  color {line}: {color_for(colors, line)}")
            done.set()

        task = asyncio.create_task(run_board(session, city, stop.stop_id, user_agent, on_ack, on_tabs))
        waiter = asyncio.create_task(done.wait())
        finished, _ = await asyncio.wait({task, waiter}, timeout=TIMEOUT_S, return_when=asyncio.FIRST_COMPLETED)
        if not finished:
            print(f"timeout after {TIMEOUT_S} s")
        if task in finished and task.exception() is not None:
            print(f"connection failed: {task.exception()!r}")
        for pending in (task, waiter):
            pending.cancel()
        await asyncio.gather(task, waiter, return_exceptions=True)
        return 0 if done.is_set() else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2])))
