"""iMHD live departures for several stops, plus the bundled Lovelace card."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import CARD_FILE, CARD_URL_BASE, CONF_CITY, CONF_STOPS, DOMAIN, STOP_ID, USER_AGENT_FORMAT
from .hub import ImhdRuntime, StopConnection, StopMeta

PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type ImhdConfigEntry = ConfigEntry[ImhdRuntime]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the card and load it on every dashboard."""
    version = (await async_get_integration(hass, DOMAIN)).version
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_BASE, str(Path(__file__).parent / "frontend"), cache_headers=False)]
    )
    add_extra_js_url(hass, f"{CARD_URL_BASE}/{CARD_FILE}?v={version}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ImhdConfigEntry) -> bool:
    """Connect every configured stop of one city."""
    version = (await async_get_integration(hass, DOMAIN)).version
    user_agent = USER_AGENT_FORMAT.format(version=version)
    city: str = entry.data[CONF_CITY]
    stop_ids = [int(stop[STOP_ID]) for stop in entry.options.get(CONF_STOPS, [])]
    connections = {stop_id: StopConnection(entry, city, stop_id, user_agent) for stop_id in stop_ids}
    entry.runtime_data = ImhdRuntime(city, connections)

    session = async_get_clientsession(hass)
    for connection in connections.values():
        connection.async_start(hass, session)
    StopMeta(entry, entry.runtime_data, user_agent).async_start(hass, session)

    # Drop devices of stops that were removed in the options.
    device_registry = dr.async_get(hass)
    wanted = {(DOMAIN, f"{city}_{stop_id}") for stop_id in stop_ids}
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not device.identifiers & wanted:
            device_registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ImhdConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ImhdConfigEntry) -> bool:
    """Stop the sensors and close every connection."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    for connection in entry.runtime_data.connections.values():
        await connection.async_stop()
    return unloaded
