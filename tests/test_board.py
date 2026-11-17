"""Board merge, line mode and status."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from custom_components.imhd.board import Board, apply_tabs, board_departures, board_status, iso_ms, line_mode
from custom_components.imhd.const import LIVE_MS
from custom_components.imhd.meta import LineColor, LineColors

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "tabs-83.json").read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(FIXTURE["receivedAt"]).timestamp() * 1000


def real_board() -> Board:
    """The real first burst of pushes for stop 83 (Hodžovo nám.), applied in order."""
    board: Board = {}
    for push in FIXTURE["pushes"]:
        assert apply_tabs(board, push) is True
    return board


def test_maps_the_real_payload_merged_and_sorted() -> None:
    board = real_board()
    # Three pushes with four platforms; 214, 215 and 216 were pushed twice, the second push replaced the first.
    assert sorted(board) == [213, 214, 215, 216]
    departures = board_departures(board, [], NOW, "ba")
    assert len(departures) == 10
    times = [d["departs_at"] for d in departures]
    assert sorted(times) == times
    first = departures[0]
    assert first["line"] == "84"
    assert first["mode"] == "bus"
    assert first["destination"] == "Ovsište"
    assert first["scheduled_at"] == "2026-11-17T19:27:45.000Z"
    assert first["realtime"] is True
    assert first["delay_min"] == 1
    assert first["platform"] == 216
    assert {d["platform"] for d in departures} <= set(board)
    # The second push of platform 215 moved the live line 83 row; the newer time is kept.
    line_83 = [d for d in board_departures(board, ["83"], NOW, "ba") if d["platform"] == 215]
    assert line_83[0]["departs_at"] == "2026-11-17T19:41:30.592Z"
    # An empty platform is kept on the board without departures.
    assert apply_tabs(board, [{"zastavka": 100, "nastupiste": 217, "timestamp": NOW, "tab": []}]) is True
    assert board[217].departures == []
    assert len(board_departures(board, [], NOW, "ba")) == 10
    # One trip listed twice by iMHD stays once.
    twice: Board = {}
    row = {"linka": "93", "cielStr": "Centrum", "cas": NOW + 60_000, "casCP": NOW + 60_000, "typ": "online"}
    apply_tabs(twice, [{"zastavka": 100, "nastupiste": 1, "timestamp": NOW, "tab": [row, dict(row)]}])
    assert len(board_departures(twice, [], NOW, "ba")) == 1


def test_marks_timetable_only_departures_and_keeps_the_delay() -> None:
    departures = board_departures(real_board(), ["47"], NOW, "ba")
    assert [(d["destination"], d["realtime"], d["delay_min"]) for d in departures] == [
        ("Hrad ► Červený most", True, 1),
        ("Zimný štadión", True, 0),
        ("Hrad ► Červený most", True, 0),
        ("Zimný štadión", False, 0),
        ("Depo Hroboňova", True, 0),
    ]
    board: Board = {}
    # line 30, tracked, 63 s late, casDelta 1
    apply_tabs(
        board,
        [
            {
                "zastavka": 100,
                "nastupiste": 1,
                "timestamp": NOW,
                "tab": [
                    {
                        "linka": "30",
                        "cielStr": "Centrum",
                        "cas": NOW + 123_000,
                        "casCP": NOW + 60_000,
                        "casDelta": 1,
                        "typ": "online",
                        "odjazd": "2 min",
                    }
                ],
            }
        ],
    )
    first = board_departures(board, [], NOW, "ba")[0]
    assert first["realtime"] is True
    assert first["delay_min"] == 1
    assert first["departs_at"] == iso_ms(NOW + 123_000)
    assert first["scheduled_at"] == iso_ms(NOW + 60_000)


def test_filters_lines_and_drops_departed_and_unreadable_rows() -> None:
    lines = {d["line"] for d in board_departures(real_board(), ["42", "93"], NOW, "ba")}
    assert lines == {"42", "93"}
    board: Board = {}
    apply_tabs(
        board,
        [
            {
                "zastavka": 1,
                "nastupiste": 1,
                "timestamp": NOW,
                "tab": [
                    {"linka": "N33", "cielStr": "A", "cas": NOW - 120_000, "casCP": NOW - 120_000, "typ": "cp"},
                    {"linka": "n33", "cielStr": "B", "cas": NOW + 60_000, "casCP": NOW + 60_000, "typ": "cp"},
                    {"linka": "X", "cas": "soon"},
                ],
            }
        ],
    )
    assert [d["destination"] for d in board_departures(board, ["N33"], NOW, "ba")] == ["B"]
    assert apply_tabs(board, {"not": "an array"}) is False


def test_derives_the_mode_from_the_line_number() -> None:
    assert [line_mode("ba", x) for x in ["1", "4", "9"]] == ["tram"] * 3
    assert [line_mode("ba", x) for x in ["40", "47", "71", "79"]] == ["trolleybus"] * 4
    assert all(line_mode("ba", x) == "bus" for x in ["10", "30", "39", "80", "92", "N33", "X13", "201", "23"])
    # The rule is Bratislava-only.
    assert [line_mode("ke", x) for x in ["4", "40", "N33"]] == [None, None, None]
    assert {d["mode"] for d in board_departures(real_board(), [], NOW, "ke")} == {None}


def test_reports_live_connecting_and_unavailable() -> None:
    assert board_status(NOW, False, NOW + LIVE_MS - 1) == "live"
    assert board_status(NOW, False, NOW + LIVE_MS) == "connecting"
    assert board_status(NOW, True, NOW + LIVE_MS) == "unavailable"
    assert board_status(None, False, NOW) == "connecting"
    assert board_status(None, True, NOW) == "unavailable"


def test_uses_the_terminus_when_cielstr_is_missing() -> None:
    # Košice pushes have `konecnaZstr` but no `cielStr` (live smoke test, 2026-11-15).
    board: Board = {}
    row = {"linka": "R1", "konecnaZstr": "Staničné nám.", "cas": NOW + 60_000, "casCP": NOW + 60_000, "typ": "cp"}
    apply_tabs(board, [{"zastavka": 1130, "nastupiste": 1, "timestamp": NOW, "tab": [row, {"linka": "R2"}]}])
    assert [(d["line"], d["destination"], d["mode"]) for d in board_departures(board, [], NOW, "ke")] == [
        ("R1", "Staničné nám.", None)
    ]


def test_terminus_comes_from_konecnazstr_with_the_destination_as_fallback() -> None:
    board: Board = {}
    row = {"linka": "N21", "cas": NOW + 60_000, "casCP": NOW + 60_000, "typ": "cp"}
    apply_tabs(
        board,
        [
            {
                "zastavka": 100,
                "nastupiste": 1,
                "timestamp": NOW,
                "tab": [
                    {**row, "cielStr": "Hlavná stanica ► Centrum", "konecnaZstr": "Hlavná stanica"},
                    {**row, "linka": "30", "cielStr": "Centrum", "cas": NOW + 90_000},
                ],
            }
        ],
    )
    assert [(d["destination"], d["terminus"]) for d in board_departures(board, [], NOW, "ba")] == [
        ("Hlavná stanica ► Centrum", "Hlavná stanica"),
        ("Centrum", "Centrum"),
    ]


def test_empty_board_has_no_departures() -> None:
    assert board_departures(None, [], NOW, "ba") == []
    assert board_departures({}, [], NOW, "ba") == []


def test_merged_platforms_keep_their_own_numbers() -> None:
    board: Board = {}
    row = {"cielStr": "A", "typ": "cp"}
    apply_tabs(
        board,
        [
            {"zastavka": 100, "nastupiste": 1310, "timestamp": NOW, "tab": [
                {**row, "linka": "20", "cas": NOW + 120_000, "casCP": NOW + 120_000},
                {**row, "linka": "21", "cas": NOW + 60_000, "casCP": NOW + 60_000},
            ]},
            {"zastavka": 100, "nastupiste": 11585, "timestamp": NOW, "tab": [
                {**row, "linka": "30", "cas": NOW + 90_000, "casCP": NOW + 90_000},
                # The same trip on a second platform: the first platform wins.
                {**row, "linka": "21", "cas": NOW + 60_000, "casCP": NOW + 60_000},
            ]},
        ],
    )
    assert [(d["line"], d["platform"]) for d in board_departures(board, [], NOW, "ba")] == [
        ("21", 1310),
        ("30", 11585),
        ("20", 1310),
    ]


def test_adds_platform_letters_and_line_colors() -> None:
    labels = {213: "A", 214: "B", 215: "C", 216: "D"}
    colors = LineColors(
        exact={"93": LineColor("rgb(51,134,50)", "rgb(255,255,255)")},
        prefixes=[("", LineColor("rgb(128,128,128)", None))],
    )
    departures = board_departures(real_board(), [], NOW, "ba", labels, colors)
    first = departures[0]
    assert (first["line"], first["platform"], first["platform_label"]) == ("84", 216, "D")
    assert (first["color"], first["text_color"]) == ("rgb(128,128,128)", None)
    assert first["mode"] == "bus"
    line_93 = next(d for d in departures if d["line"] == "93")
    assert (line_93["color"], line_93["text_color"]) == ("rgb(51,134,50)", "rgb(255,255,255)")
    assert all(d["platform_label"] == labels[d["platform"]] for d in departures)
    # Without metadata the fields are there but empty.
    plain = board_departures(real_board(), [], NOW, "ba")[0]
    assert (plain["platform_label"], plain["color"], plain["text_color"]) == (None, None, None)
