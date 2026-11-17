"""Stop search parsing."""

from __future__ import annotations

import pytest

from custom_components.imhd.search import SearchError, StopHit, clean_query, parse_search

RESPONSE = {
    "results": [
        {
            "name": "Zochova",
            "html": "Zochova",
            "url": "/ba/zastavka/Zochova/0a1b2c3d4e5f6a7b8c9d0e",
            "class": "stop",
            "value": "g201",
            "sort": "20.000000",
        },
        {"name": "Zochova", "class": "street", "value": "s12", "url": "/x"},
        {"name": "Zochova", "class": "stop", "value": "g201", "url": "/y"},
        {"name": "Kamenné námestie", "class": "stop", "value": "g202", "url": "/z"},
        {"name": "Broken", "class": "stop", "value": "line-4", "url": "/w"},
        {"name": "   ", "class": "stop", "value": "g9", "url": "/v"},
        # live iMHD answers always end with this entry: a document without `value`
        {
            "name": " › Podrobnejšie vyhľadávanie ›",
            "html": " › Podrobnejšie vyhľadávanie ›",
            "url": "/ba/vyhladavanie?q=Zochova",
            "class": "document",
            "sort": 999,
        },
    ]
}


def test_keeps_distinct_stop_hits_with_the_number_after_g() -> None:
    assert parse_search(RESPONSE) == [StopHit(201, "Zochova"), StopHit(202, "Kamenné námestie")]


def test_only_the_document_entry_is_no_error() -> None:
    assert parse_search({"results": [{"name": " › Podrobnejšie vyhľadávanie ›", "class": "document"}]}) == []


@pytest.mark.parametrize("body", [{"nope": True}, [], None, {"results": "x"}])
def test_fails_on_a_bad_envelope(body: object) -> None:
    with pytest.raises(SearchError, match="unexpected response"):
        parse_search(body)


def test_cleans_the_query() -> None:
    assert clean_query("  Nám.   SNP ") == "Nám. SNP"
    assert len(clean_query("a" * 300)) == 100
