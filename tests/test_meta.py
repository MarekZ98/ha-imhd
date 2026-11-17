"""Platform letters and line colors from the iMHD website."""

from __future__ import annotations

from pathlib import Path

from custom_components.imhd.meta import LineColor, color_for, escape_line, parse_line_css, parse_platform_labels

CSS = (Path(__file__).parent / "fixtures" / "linky-sample.css").read_text(encoding="utf-8")
WHITE = "rgb(255,255,255)"

# Inline script of https://imhd.sk/ba/online-zastavkova-tabula?st=83 (2026-11-17).
PAGE_83 = (
    '<script>window.board = {"stopId":83,"platformsLabels":{"213":"A","214":"B","215":"C","216":"D"},'
    '"other":{"x":1}};</script>'
)


def test_parses_the_platform_letters() -> None:
    assert parse_platform_labels(PAGE_83) == {213: "A", 214: "B", 215: "C", 216: "D"}


def test_missing_or_broken_platform_letters_are_empty() -> None:
    assert parse_platform_labels("<html><body>no board</body></html>") == {}
    assert parse_platform_labels('{"platformsLabels":{"1310":"A",}}') == {}
    assert parse_platform_labels('{"platformsLabels":{"abc":"A"}}') == {}


def test_exact_line_rule_wins() -> None:
    colors = parse_line_css(CSS, "ba")
    assert color_for(colors, "21") == LineColor("rgb(51,134,50)", WHITE)
    # One selector list naming several lines.
    assert color_for(colors, "N1") == LineColor("#0064b4", "#fff")
    assert color_for(colors, "N2") == LineColor("#0064b4", "#fff")


def test_falls_back_to_the_longest_city_prefix() -> None:
    colors = parse_line_css(CSS, "ba")
    assert color_for(colors, "20") == LineColor("rgb(128,128,128)", WHITE)
    assert color_for(colors, "N21") == LineColor("rgb(43,42,41)", WHITE)
    # A rule without a background is skipped; the prefix applies.
    assert color_for(colors, "99") == LineColor("rgb(128,128,128)", WHITE)


def test_escaped_lines_and_background_shorthand() -> None:
    assert escape_line("►") == "_9658_"
    assert escape_line("X13") == "X13"
    assert color_for(parse_line_css(CSS, "ba"), "►") == LineColor("#ffcc00", "black")


def test_other_cities_and_media_blocks() -> None:
    assert color_for(parse_line_css(CSS, "ke"), "21") == LineColor("rgb(255,221,0)", "rgb(0,0,0)")
    assert color_for(parse_line_css(CSS, "ke"), "20") is None
    assert color_for(parse_line_css(CSS, "zz"), "21") is None
    assert color_for(None, "21") is None
    # The @media override of l21 is ignored.
    assert parse_line_css(CSS, "ba").exact["21"].background == "rgb(51,134,50)"
