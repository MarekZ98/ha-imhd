"""Stop metadata from the iMHD website: platform letters of a stop and the official line colors."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import aiohttp

from .const import META_TIMEOUT_S

_PLATFORMS_LABELS = re.compile(r'"platformsLabels"\s*:\s*(\{.*?\})', re.DOTALL)
_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_COLOR_TOKEN = re.compile(r"(?:rgba?|hsla?)\([^)]*\)|#[0-9A-Fa-f]{3,8}\b|\b[A-Za-z]+\b")
# Words of a `background` shorthand that are not colors.
_NOT_COLORS = frozenset(
    {
        "none",
        "inherit",
        "initial",
        "unset",
        "revert",
        "url",
        "repeat",
        "no",
        "x",
        "y",
        "space",
        "round",
        "scroll",
        "fixed",
        "local",
        "center",
        "top",
        "bottom",
        "left",
        "right",
        "auto",
        "cover",
        "contain",
        "border",
        "padding",
        "content",
        "box",
        "important",
    }
)


class MetaError(Exception):
    """The iMHD website answered with an error."""


@dataclass(frozen=True)
class LineColor:
    """The badge colors of one line; `text` None = the website sets none."""

    background: str
    text: str | None


@dataclass
class LineColors:
    """The line color rules of ONE city: exact `l<escaped line>` classes and `l<prefix>` fallbacks."""

    exact: dict[str, LineColor] = field(default_factory=dict)
    prefixes: list[tuple[str, LineColor]] = field(default_factory=list)


def parse_platform_labels(html: str) -> dict[int, str]:
    """`platformsLabels` of the board page (platform id -> letter); anything unreadable -> {}."""
    match = _PLATFORMS_LABELS.search(html)
    if match is None:
        return {}
    try:
        raw = json.loads(match.group(1))
        if not isinstance(raw, dict):
            return {}
        return {int(key): str(value) for key, value in raw.items() if isinstance(value, str | int)}
    except ValueError:
        return {}


def escape_line(line: str) -> str:
    """The iMHD CSS class part of a line: every char outside [A-Za-z0-9] becomes `_<code point>_`."""
    return "".join(c if c.isascii() and c.isalnum() else f"_{ord(c)}_" for c in line)


def _blocks(css: str) -> list[tuple[str, str]]:
    """Top-level `selectors { body }` blocks; at-rule blocks (`@media` …) are skipped whole."""
    css = _COMMENT.sub("", css)
    blocks: list[tuple[str, str]] = []
    i, n = 0, len(css)
    while i < n:
        start = css.find("{", i)
        if start < 0:
            break
        selector = css[i:start].strip()
        if selector.startswith("@"):
            depth, j = 1, start + 1
            while j < n and depth:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            i = j
            continue
        end = css.find("}", start)
        if end < 0:
            break
        blocks.append((selector, css[start + 1 : end]))
        i = end + 1
    return blocks


def _declarations(body: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in body.split(";"):
        name, sep, value = part.partition(":")
        if sep:
            result[name.strip().lower()] = value.replace("!important", "").strip()
    return result


def _shorthand_color(value: str) -> str | None:
    """The color token of a `background` shorthand."""
    value = re.sub(r"url\([^)]*\)", " ", value)
    for token in _COLOR_TOKEN.findall(value):
        if token.lower() not in _NOT_COLORS:
            return token
    return None


def parse_line_css(css: str, city: str) -> LineColors:
    """The line color rules of `city` from `linky.css`; blocks without a background are skipped."""
    exact = re.compile(rf"^\.Linka\.{re.escape(city)}\.l([^\s:]+)$")
    # The real file quotes the attribute value with ' (the docs show ").
    prefix = re.compile(rf"""^\[class\*=(["']) Linka {re.escape(city)} l([^"']*)\1\]$""")
    colors = LineColors()
    prefixes: dict[str, LineColor] = {}
    for selectors, body in _blocks(css):
        declarations = _declarations(body)
        background = declarations.get("background-color") or None
        if background is None and "background" in declarations:
            background = _shorthand_color(declarations["background"])
        if not background:
            continue
        color = LineColor(background=background, text=declarations.get("color") or None)
        for selector in selectors.split(","):
            selector = selector.strip()
            if (match := exact.match(selector)) is not None:
                colors.exact[match.group(1)] = color
            elif (match := prefix.match(selector)) is not None:
                prefixes[match.group(2)] = color
    colors.prefixes = list(prefixes.items())
    return colors


def color_for(colors: LineColors | None, line: str) -> LineColor | None:
    """Like CSS specificity: the exact line class wins, else the longest matching prefix, else None."""
    if colors is None:
        return None
    escaped = escape_line(line)
    if escaped in colors.exact:
        return colors.exact[escaped]
    best: tuple[str, LineColor] | None = None
    for prefix, color in colors.prefixes:
        if escaped.startswith(prefix) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, color)
    return best[1] if best is not None else None


async def fetch_text(session: aiohttp.ClientSession, url: str, user_agent: str) -> str:
    """GET `url` as text; HTTP != 200 raises `MetaError`."""
    async with session.get(
        url, headers={"user-agent": user_agent}, timeout=aiohttp.ClientTimeout(total=META_TIMEOUT_S)
    ) as response:
        if response.status != 200:
            raise MetaError(f"{url} answered HTTP {response.status}")
        return await response.text()
