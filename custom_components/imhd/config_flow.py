"""Config flow: paste a board link or search a stop; options add, edit and remove stops."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowHandler
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.loader import async_get_integration

from .const import (
    CITIES,
    CONF_CITY,
    CONF_STOPS,
    DOMAIN,
    MAX_STOPS,
    STOP_ID,
    STOP_LABEL,
    STOP_LINES,
    STOP_WALK_MIN,
    USER_AGENT_FORMAT,
)
from .link import LinkError, parse_board_link
from .search import SearchError, StopHit, search_stops

_LOGGER = logging.getLogger(__name__)

CONF_URL = "url"
CONF_QUERY = "query"
CONF_STOP = "stop"
CONF_LABEL = "label"
CONF_WALK_MIN = "walk_min"
CONF_LINES = "lines"
CONF_REMOVE = "remove"


def new_stop(stop_id: int, label: str) -> dict[str, Any]:
    """A configured stop with default walk time and all lines."""
    return {STOP_ID: stop_id, STOP_LABEL: label, STOP_WALK_MIN: 0, STOP_LINES: []}


def merge_stops(current: list[dict[str, Any]], added: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Append stops whose id is new; None when the result would exceed MAX_STOPS."""
    merged = list(current)
    known = {int(stop[STOP_ID]) for stop in current}
    for stop in added:
        if int(stop[STOP_ID]) not in known:
            known.add(int(stop[STOP_ID]))
            merged.append(stop)
    return None if len(merged) > MAX_STOPS else merged


def parse_lines(text: str) -> list[str]:
    """`"30, n33"` -> `["30", "N33"]`; empty = all lines."""
    lines: list[str] = []
    for part in text.split(","):
        line = part.strip().upper()
        if line and line not in lines:
            lines.append(line)
    return lines


def _stop_options(stops: list[dict[str, Any]]) -> list[SelectOptionDict]:
    return [SelectOptionDict(value=str(s[STOP_ID]), label=f"{s[STOP_LABEL]} ({s[STOP_ID]})") for s in stops]


class _StopSteps(FlowHandler):
    """Steps shared by the config flow and the options flow: `link`, `labels`, `search`, `pick`."""

    # Options flow: the entry's city (links of other cities are refused, search has no city field).
    _fixed_city: str | None = None

    def _init_steps(self) -> None:
        self._city = ""
        self._pending: list[int] = []
        self._hits: list[StopHit] = []

    async def _async_finish(self, stops: list[dict[str, Any]]) -> ConfigFlowResult:
        raise NotImplementedError

    async def async_step_link(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Paste an imhd.sk board link."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                link = parse_board_link(user_input[CONF_URL])
            except LinkError as err:
                errors["base"] = err.code
            else:
                if self._fixed_city is not None and link.city != self._fixed_city:
                    errors["base"] = "other_city"
                else:
                    self._city = link.city
                    self._pending = list(link.stop_ids)
                    return await self.async_step_labels()
        return self.async_show_form(
            step_id="link", data_schema=vol.Schema({vol.Required(CONF_URL): str}), errors=errors
        )

    async def async_step_labels(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Name every stop of the link."""
        if user_input is not None:
            stops = [new_stop(i, str(user_input.get(f"label_{i}", "")).strip() or str(i)) for i in self._pending]
            return await self._async_finish(stops)
        schema = vol.Schema({vol.Required(f"label_{i}"): str for i in self._pending})
        return self.async_show_form(
            step_id="labels",
            data_schema=schema,
            description_placeholders={"ids": ", ".join(str(i) for i in self._pending)},
        )

    async def async_step_search(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Search a stop by name."""
        errors: dict[str, str] = {}
        if user_input is not None:
            city = self._fixed_city or user_input[CONF_CITY]
            version = (await async_get_integration(self.hass, DOMAIN)).version
            try:
                hits = await search_stops(
                    async_get_clientsession(self.hass),
                    city,
                    user_input[CONF_QUERY],
                    USER_AGENT_FORMAT.format(version=version),
                )
            except (SearchError, aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.debug("iMHD search failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if hits:
                    self._city = city
                    self._hits = hits
                    return await self.async_step_pick()
                errors["base"] = "no_stops_found"
        fields: dict[Any, Any] = {}
        if self._fixed_city is None:
            cities = [SelectOptionDict(value=code, label=name) for code, name in CITIES.items()]
            fields[vol.Required(CONF_CITY, default="ba")] = SelectSelector(
                SelectSelectorConfig(options=cities, mode=SelectSelectorMode.DROPDOWN)
            )
        fields[vol.Required(CONF_QUERY)] = str
        return self.async_show_form(step_id="search", data_schema=vol.Schema(fields), errors=errors)

    async def async_step_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose one of the hits and optionally name it."""
        if user_input is not None:
            stop_id = int(user_input[CONF_STOP])
            hit = next((h for h in self._hits if h.stop_id == stop_id), None)
            name = hit.name if hit is not None else str(stop_id)
            label = str(user_input.get(CONF_LABEL) or "").strip() or name
            return await self._async_finish([new_stop(stop_id, label)])
        options = [SelectOptionDict(value=str(h.stop_id), label=f"{h.name} ({h.stop_id})") for h in self._hits]
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP, default=options[0]["value"]): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                    ),
                    vol.Optional(CONF_LABEL): str,
                }
            ),
        )


class ImhdConfigFlow(_StopSteps, ConfigFlow, domain=DOMAIN):
    """One entry per city; adding stops of a configured city extends that entry."""

    VERSION = 1

    def __init__(self) -> None:
        self._init_steps()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ImhdOptionsFlow:
        """Add, edit and remove stops."""
        return ImhdOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Paste a link or search a stop."""
        return self.async_show_menu(step_id="user", menu_options=["link", "search"])

    async def _async_finish(self, stops: list[dict[str, Any]]) -> ConfigFlowResult:
        city = self._city
        await self.async_set_unique_id(city)
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, city)
        if entry is not None:
            merged = merge_stops(list(entry.options.get(CONF_STOPS, [])), stops)
            if merged is None:
                return self.async_abort(reason="too_many_stops")
            self.hass.config_entries.async_update_entry(entry, options={**entry.options, CONF_STOPS: merged})
            return self.async_abort(reason="stops_added")
        merged = merge_stops([], stops)
        if merged is None:
            return self.async_abort(reason="too_many_stops")
        return self.async_create_entry(
            title=f"iMHD {CITIES[city]}", data={CONF_CITY: city}, options={CONF_STOPS: merged}
        )


class ImhdOptionsFlow(_StopSteps, OptionsFlow):
    """Menu: add by link, add by search, edit one stop, remove stops."""

    def __init__(self) -> None:
        self._init_steps()
        self._edit_id: int | None = None

    @property
    def _stops(self) -> list[dict[str, Any]]:
        return list(self.config_entry.options.get(CONF_STOPS, []))

    def _save(self, stops: list[dict[str, Any]]) -> ConfigFlowResult:
        return self.async_create_entry(data={**self.config_entry.options, CONF_STOPS: stops})

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """The options menu."""
        self._fixed_city = self.config_entry.data[CONF_CITY]
        menu = ["add_link", "add_search"]
        if self._stops:
            menu += ["edit", "remove"]
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_add_link(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Add stops from a board link."""
        return await self.async_step_link()

    async def async_step_add_search(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Add a stop found by name."""
        return await self.async_step_search()

    async def _async_finish(self, stops: list[dict[str, Any]]) -> ConfigFlowResult:
        merged = merge_stops(self._stops, stops)
        if merged is None:
            return self.async_abort(reason="too_many_stops")
        return self._save(merged)

    async def async_step_edit(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the stop to edit."""
        if user_input is not None:
            self._edit_id = int(user_input[CONF_STOP])
            return await self.async_step_edit_stop()
        options = _stop_options(self._stops)
        return self.async_show_form(
            step_id="edit",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP, default=options[0]["value"]): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                    )
                }
            ),
        )

    async def async_step_edit_stop(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Label, walk time and line filter of one stop."""
        stops = self._stops
        index = next(i for i, s in enumerate(stops) if int(s[STOP_ID]) == self._edit_id)
        stop = stops[index]
        if user_input is not None:
            stops[index] = {
                STOP_ID: stop[STOP_ID],
                STOP_LABEL: str(user_input[CONF_LABEL]).strip() or str(stop[STOP_ID]),
                STOP_WALK_MIN: int(user_input.get(CONF_WALK_MIN, 0)),
                STOP_LINES: parse_lines(str(user_input.get(CONF_LINES, ""))),
            }
            return self._save(stops)
        return self.async_show_form(
            step_id="edit_stop",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LABEL, default=stop[STOP_LABEL]): str,
                    vol.Required(CONF_WALK_MIN, default=stop.get(STOP_WALK_MIN, 0)): NumberSelector(
                        NumberSelectorConfig(min=0, max=30, step=1, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Optional(
                        CONF_LINES, description={"suggested_value": ", ".join(stop.get(STOP_LINES, []))}
                    ): str,
                }
            ),
            description_placeholders={"stop": f"{stop[STOP_LABEL]} ({stop[STOP_ID]})"},
        )

    async def async_step_remove(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Remove one or more stops."""
        if user_input is not None:
            removed = {int(v) for v in user_input.get(CONF_REMOVE, [])}
            return self._save([s for s in self._stops if int(s[STOP_ID]) not in removed])
        return self.async_show_form(
            step_id="remove",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REMOVE, default=[]): SelectSelector(
                        SelectSelectorConfig(
                            options=_stop_options(self._stops), multiple=True, mode=SelectSelectorMode.LIST
                        )
                    )
                }
            ),
        )
