"""Board link parsing."""

from __future__ import annotations

import pytest

from custom_components.imhd.link import BoardLink, LinkError, parse_board_link


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://imhd.sk/ba/online-zastavkova-tabula?st=101;102", BoardLink("ba", (101, 102))),
        ("https://imhd.sk/ke/online-zastavkova-tabula?st=1201", BoardLink("ke", (1201,))),
        ("https://imhd.sk/ba/online-zastavkova-tabula?st=101%3B102%3b103", BoardLink("ba", (101, 102, 103))),
        ("https://www.imhd.sk/ba/online-zastavkova-tabula?st=g101;G102", BoardLink("ba", (101, 102))),
        ("https://m.imhd.sk/za/online-zastavkova-tabula?st=12,13", BoardLink("za", (12, 13))),
        ("  imhd.sk/ba/online-zastavkova-tabula?st=101  ", BoardLink("ba", (101,))),
        ("https://imhd.sk/BA/online-zastavkova-tabula?st=;101;;x;0;-3", BoardLink("ba", (101,))),
        ("https://imhd.sk/ba/online-zastavkova-tabula?st=102;101;102;g101", BoardLink("ba", (102, 101))),
        ("https://imhd.sk/tatry/online-zastavkova-tabula?st=9", BoardLink("tatry", (9,))),
    ],
)
def test_parses_valid_links(text: str, expected: BoardLink) -> None:
    assert parse_board_link(text) == expected


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("", "invalid_link"),
        ("https://example.com/ba/online-zastavkova-tabula?st=101", "invalid_link"),
        ("https://imhd.sk/", "invalid_link"),
        ("https://imhd.sk.evil.com/ba/?st=101", "invalid_link"),
        ("https://imhd.sk/xx/online-zastavkova-tabula?st=101", "unknown_city"),
        ("https://imhd.sk/ba/online-zastavkova-tabula", "no_stops"),
        ("https://imhd.sk/ba/online-zastavkova-tabula?st=", "no_stops"),
        ("https://imhd.sk/ba/online-zastavkova-tabula?st=abc;0", "no_stops"),
    ],
)
def test_rejects_bad_links(text: str, code: str) -> None:
    with pytest.raises(LinkError) as err:
        parse_board_link(text)
    assert err.value.code == code
