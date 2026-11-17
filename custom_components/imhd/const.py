"""Constants of the iMHD integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "imhd"

# iMHD cities: path code -> Slovak name.
CITIES: Final[dict[str, str]] = {
    "ba": "Bratislava",
    "bb": "Banská Bystrica",
    "hc": "Hlohovec",
    "ke": "Košice",
    "lm": "Liptovský Mikuláš",
    "mt": "Martin",
    "nr": "Nitra",
    "nz": "Nové Zámky",
    "pn": "Piešťany",
    "tatry": "Poprad-Tatry",
    "pb": "Považská Bystrica",
    "po": "Prešov",
    "pd": "Prievidza",
    "rk": "Ružomberok",
    "se": "Senica",
    "si": "Skalica",
    "sn": "Spišská Nová Ves",
    "tn": "Trenčín",
    "tt": "Trnava",
    "zv": "Zvolen",
    "za": "Žilina",
}

SEARCH_URL_FORMAT: Final = "https://imhd.sk/{city}/api/sk/vyhladavanie"
BOARD_PAGE_URL_FORMAT: Final = "https://imhd.sk/{city}/online-zastavkova-tabula?st={stop_id}"
LINE_CSS_URL: Final = "https://imhd.sk/data/css/linky.css"
SOCKET_URL: Final = "wss://imhd.sk/rt/sio2/?EIO=4&transport=websocket"
ORIGIN: Final = "https://imhd.sk"
USER_AGENT_FORMAT: Final = "ha-imhd/{version} (+https://github.com/MarekZ98/ha-imhd)"

CONF_CITY: Final = "city"
CONF_STOPS: Final = "stops"

# Keys of one configured stop in `entry.options[CONF_STOPS]`.
STOP_ID: Final = "id"
STOP_LABEL: Final = "label"
STOP_WALK_MIN: Final = "walk_min"
STOP_LINES: Final = "lines"

MAX_STOPS: Final = 8
DEPARTURES_PER_STOP: Final = 10
LIVE_MS: Final = 120_000
DEPARTED_GRACE_MS: Final = 30_000
RETRY_MIN_S: Final = 5
RETRY_MAX_S: Final = 60
REJECTED_S: Final = 600
SEARCH_TIMEOUT_S: Final = 8
META_REFRESH_S: Final = 86_400
META_TIMEOUT_S: Final = 10
WRITE_THROTTLE_S: Final = 10
TICK_S: Final = 30

QUERY_MIN: Final = 2
QUERY_MAX: Final = 100

CARD_URL_BASE: Final = "/imhd_static"
CARD_FILE: Final = "imhd-departures-card.js"
