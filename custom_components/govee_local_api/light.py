"""Support for Govee Lights over Local API."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controller import GoveeController
from .device import GoveeDevice
from .light_capabilities import GoveeLightFeatures

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Govee light from a config entry."""
    controller: GoveeController = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_discover_device(device: GoveeDevice, is_new: bool) -> bool:
        """Handle discovery of a new Govee device."""
        if is_new:
            async_add_entities([GoveeLightEntity(device)])
        return True

    # Register callback for new devices
    controller.set_device_discovered_callback(async_discover_device)

    # Add existing devices
    if controller.devices:
        async_add_entities(
            [GoveeLightEntity(device) for device in controller.devices]
        )


class GoveeLightEntity(LightEntity):
    """Representation of a Govee Light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device: GoveeDevice) -> None:
        """Initialize the light."""
        self._device = device
        self._attr_unique_id = device.fingerprint
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.fingerprint)},
            manufacturer="Govee",
            model=device.sku,
            name=device.sku,
        )

        # Set supported color modes
        self._attr_supported_color_modes = set()
        if device.capabilities.features & GoveeLightFeatures.COLOR_RGB:
            self._attr_supported_color_modes.add(ColorMode.RGB)
        if device.capabilities.features & GoveeLightFeatures.COLOR_KELVIN_TEMPERATURE:
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
        
        if not self._attr_supported_color_modes:
            if device.capabilities.features & GoveeLightFeatures.BRIGHTNESS:
                self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
            else:
                self._attr_supported_color_modes.add(ColorMode.ONOFF)

        if device.capabilities.features & GoveeLightFeatures.SCENES:
            self._attr_supported_features |= LightEntityFeature.EFFECT
            self._attr_effect_list = device.capabilities.available_scenes

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._device.on

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int(self._device.brightness * 255 / 100)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        return self._device.rgb_color

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        return self._device.temperature_color

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode of the light."""
        if self._device.temperature_color > 0:
            return ColorMode.COLOR_TEMP
        if self._device.rgb_color and self._device.rgb_color != (0, 0, 0):
            return ColorMode.RGB
        if self._device.capabilities.features & GoveeLightFeatures.BRIGHTNESS:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            await self._device.set_brightness(brightness)
        
        if ATTR_RGB_COLOR in kwargs:
            red, green, blue = kwargs[ATTR_RGB_COLOR]
            await self._device.set_rgb_color(red, green, blue)
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            await self._device.set_temperature(kwargs[ATTR_COLOR_TEMP_KELVIN])
        elif ATTR_EFFECT in kwargs:
            await self._device.set_scene(kwargs[ATTR_EFFECT])
        
        if not kwargs:
            await self._device.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._device.turn_off()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self._device.set_update_callback(self._update_callback)

    @callback
    def _update_callback(self, device: GoveeDevice) -> None:
        """Handle updated data from the device."""
        self.async_write_ha_state()
