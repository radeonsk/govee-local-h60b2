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
            entities: list[LightEntity] = [GoveeLightEntity(device)]
            if device.capabilities.segments_count > 0:
                entities.extend(
                    [
                        GoveeSegmentLightEntity(device, i + 1)
                        for i in range(device.capabilities.segments_count)
                    ]
                )
            async_add_entities(entities)
        return True

    # Register callback for new devices
    controller.set_device_discovered_callback(async_discover_device)

    # Add existing devices
    if controller.devices:
        entities: list[LightEntity] = []
        for device in controller.devices:
            entities.append(GoveeLightEntity(device))
            if device.capabilities.segments_count > 0:
                entities.extend(
                    [
                        GoveeSegmentLightEntity(device, i + 1)
                        for i in range(device.capabilities.segments_count)
                    ]
                )
        async_add_entities(entities)


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
        if self.color_mode == ColorMode.COLOR_TEMP:
            return None
        color = self._device.rgb_color
        if color == (0, 0, 0):
            return (255, 255, 255)
        return color

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        return self._device.temperature_color

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode of the light."""
        if self._device.temperature_color > 0:
            return ColorMode.COLOR_TEMP
        if ColorMode.RGB in self.supported_color_modes:
            return ColorMode.RGB
        if ColorMode.COLOR_TEMP in self.supported_color_modes:
            return ColorMode.COLOR_TEMP
        if ColorMode.BRIGHTNESS in self.supported_color_modes:
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


class GoveeSegmentLightEntity(LightEntity):
    """Representation of a Govee Light Segment."""

    _attr_has_entity_name = True

    def __init__(self, device: GoveeDevice, segment_index: int) -> None:
        """Initialize the light segment."""
        self._device = device
        self._segment_index = segment_index
        self._attr_unique_id = f"{device.fingerprint}_segment_{segment_index}"
        self._attr_name = f"Segment {segment_index}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.fingerprint)},
        )

        self._attr_supported_color_modes = {ColorMode.RGB}
        if device.capabilities.features & GoveeLightFeatures.COLOR_KELVIN_TEMPERATURE:
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)

    @property
    def is_on(self) -> bool:
        """Return true if segment is on."""
        return self._device.segments[self._segment_index - 1].is_on

    @property
    def brightness(self) -> int:
        """Return the brightness of this segment."""
        return int(self._device.segments[self._segment_index - 1].brightness * 255 / 100)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        if self.color_mode == ColorMode.COLOR_TEMP:
            return None
        seg_color = self._device.segments[self._segment_index - 1].color
        if seg_color == (0, 0, 0):
            return (255, 255, 255)
        return seg_color

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        return self._device.segments[self._segment_index - 1].temperature

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode of the segment."""
        if self._device.segments[self._segment_index - 1].temperature > 0:
            return ColorMode.COLOR_TEMP
        return ColorMode.RGB

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the segment on."""
        if not kwargs:
            await self._device.turn_segment_on(self._segment_index)
            return

        segment = self._device.segments[self._segment_index - 1]
        
        brightness = segment.brightness
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS] * 100 / 255)

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            await self._device.set_segment_temperature(
                self._segment_index, kwargs[ATTR_COLOR_TEMP_KELVIN], brightness=brightness
            )
        elif ATTR_RGB_COLOR in kwargs:
            red, green, blue = kwargs[ATTR_RGB_COLOR]
            await self._device.set_segment_rgb_color(
                self._segment_index, red, green, blue, brightness=brightness
            )
        else:
            if segment.temperature > 0:
                await self._device.set_segment_temperature(
                    self._segment_index, segment.temperature, brightness=brightness
                )
            else:
                await self._device.set_segment_rgb_color(
                    self._segment_index, *segment.color, brightness=brightness
                )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the segment off."""
        await self._device.turn_segment_off(self._segment_index)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self._device.set_update_callback(self._update_callback)

    @callback
    def _update_callback(self, device: GoveeDevice) -> None:
        """Handle updated data from the device."""
        self.async_write_ha_state()
