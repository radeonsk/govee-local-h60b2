"""The Govee Local API integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .controller import GoveeController

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee Local API from a config entry."""

    controller = GoveeController(
        loop=hass.loop,
        logger=_LOGGER,
        discovery_enabled=True,
        update_enabled=True,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller

    await controller.start()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        controller: GoveeController = hass.data[DOMAIN].pop(entry.entry_id)
        controller.cleanup()

    return unload_ok
