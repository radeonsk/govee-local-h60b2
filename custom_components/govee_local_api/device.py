from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .light_capabilities import GoveeLightCapabilities, ON_OFF_CAPABILITIES
from .message import DevStatusResponse


class GoveeSegment:
    def __init__(
        self,
        is_on: bool,
        color: tuple[int, int, int],
        brightness: int = 100,
        temperature: int = 0,
    ) -> None:
        self.is_on = is_on
        self.color = color if color != (0, 0, 0) else (255, 255, 255)
        self.brightness = brightness
        self.temperature = temperature

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_on": self.is_on,
            "color": self.color,
            "brightness": self.brightness,
            "temperature": self.temperature,
        }

    def __str__(self) -> str:
        return f"<GoveeSegment is_on={self.is_on}, color={self.color}, brightness={self.brightness}, temperature={self.temperature}>"


class GoveeDevice:
    def __init__(
        self,
        controller,
        ip: str,
        fingerprint: str,
        sku: str,
        capabilities: GoveeLightCapabilities = ON_OFF_CAPABILITIES,
    ) -> None:
        self._controller = controller
        self._fingerprint = fingerprint
        self._sku = sku
        self._ip = ip
        self._lastseen: datetime = datetime.now()
        self._capabilities: GoveeLightCapabilities = capabilities

        self._is_on: bool = False
        self._rgb_color = (255, 255, 255)
        self._temperature_color = 0
        self._brightness = 100
        self._update_callbacks: list[Callable[[GoveeDevice], None]] = []
        self.is_manual: bool = False
        self._segments: list[GoveeSegment] = [
            GoveeSegment(False, (255, 255, 255))
            for _ in range(capabilities.segments_count)
        ]
        self._initial_update_done = False

    @property
    def controller(self):
        return self._controller

    @property
    def capabilities(self) -> GoveeLightCapabilities:
        return self._capabilities

    @property
    def segments(self) -> list[GoveeSegment]:
        return self._segments

    @property
    def ip(self) -> str:
        return self._ip

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    @property
    def sku(self) -> str:
        return self._sku

    @property
    def lastseen(self) -> datetime:
        return self._lastseen

    @property
    def on(self) -> bool:
        return self._is_on

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        return self._rgb_color

    @property
    def brightness(self) -> int:
        return self._brightness

    @property
    def temperature_color(self) -> int:
        return self._temperature_color

    def set_update_callback(self, callback: Callable[[GoveeDevice], None]) -> None:
        """Register a callback to be called when the device state is updated."""
        if callback not in self._update_callbacks:
            self._update_callbacks.append(callback)

    def _trigger_update_callbacks(self) -> None:
        """Trigger all registered update callbacks."""
        for callback in self._update_callbacks:
            if callable(callback):
                callback(self)

    async def turn_on(self) -> None:
        await self._controller.turn_on_off(self, True)
        await asyncio.sleep(0.1)
        await self._controller.set_brightness(self, self._brightness)
        await asyncio.sleep(0.1)
        if self._temperature_color > 0:
            await self._controller.set_color(self, temperature=self._temperature_color, rgb=None)
        else:
            await self._controller.set_color(self, rgb=self._rgb_color, temperature=None)
            
        self._is_on = True
        # For Master turn_on, we assume all segments light up
        for segment in self._segments:
            segment.is_on = True
        self._trigger_update_callbacks()

    async def set_segment_rgb_color(
        self,
        segment: int,
        red: int,
        green: int,
        blue: int,
        brightness: int | None = None,
    ) -> None:
        if 0 < segment <= len(self._segments):
            seg = self._segments[segment - 1]
            if brightness is not None:
                seg.brightness = brightness

            is_turning_on = (red, green, blue) != (0, 0, 0)

            # If turning on a segment while device is physically OFF, wake it up first
            if is_turning_on and not self._is_on:
                await self._controller.turn_on_off(self, True)
                await asyncio.sleep(0.1)
                await self._controller.set_brightness(self, self._brightness)
                await asyncio.sleep(0.1)
                self._is_on = True

            if is_turning_on:
                seg.color = (red, green, blue)
                seg.temperature = 0
                seg.is_on = True
            else:
                seg.is_on = False

            s_brightness = seg.brightness
            if seg.is_on:
                # Scaled RGB as fallback
                s_red = int(seg.color[0] * s_brightness / 100)
                s_green = int(seg.color[1] * s_brightness / 100)
                s_blue = int(seg.color[2] * s_brightness / 100)
                if (s_red, s_green, s_blue) == (0, 0, 0) and seg.color != (0, 0, 0):
                    s_red = s_green = s_blue = 1
            else:
                s_red = s_green = s_blue = 0

            rgb: tuple[int, int, int] = (s_red, s_green, s_blue)
            await self._controller.set_segment_rgb_color(self, segment, rgb)
            await asyncio.sleep(0.1)
            await self._controller.set_segment_brightness(self, segment, s_brightness)

            # Ensure Master switch matches activity
            if seg.is_on:
                self._is_on = True

            self._trigger_update_callbacks()

    async def set_segment_temperature(
        self, segment: int, temperature: int, brightness: int | None = None
    ) -> None:
        if 0 < segment <= len(self._segments):
            seg = self._segments[segment - 1]
            seg.temperature = temperature
            seg.color = (255, 255, 255)
            seg.is_on = True
            if brightness is not None:
                seg.brightness = brightness

            # Wake up the device physically if it's currently OFF
            if not self._is_on:
                await self._controller.turn_on_off(self, True)
                await asyncio.sleep(0.1)
                await self._controller.set_brightness(self, self._brightness)
                await asyncio.sleep(0.1)
                self._is_on = True

            await self._controller.set_segment_color_temperature(self, segment, temperature)
            await asyncio.sleep(0.1)
            await self._controller.set_segment_brightness(self, segment, seg.brightness)

            self._is_on = True
            self._trigger_update_callbacks()

    async def turn_segment_on(self, segment_index: int) -> None:
        if 0 < segment_index <= len(self._segments):
            seg = self._segments[segment_index - 1]
            if seg.temperature > 0:
                await self.set_segment_temperature(segment_index, seg.temperature)
            else:
                await self.set_segment_rgb_color(segment_index, *seg.color)

    async def turn_segment_off(self, segment: int) -> None:
        await self.set_segment_rgb_color(segment, 0, 0, 0)

    async def turn_off(self) -> None:
        # Robust OFF: Ensure state is consistent then power off
        await self._controller.set_brightness(self, self._brightness)
        await asyncio.sleep(0.1)
        await self._controller.turn_on_off(self, False)
        
        self._is_on = False
        for segment in self._segments:
            segment.is_on = False
        self._trigger_update_callbacks()

    async def set_brightness(self, value: int) -> None:
        await self._controller.set_brightness(self, value)
        self._brightness = value
        # Master brightness propagates to all segments
        for segment in self._segments:
            segment.brightness = value
        self._trigger_update_callbacks()

    async def set_rgb_color(self, red: int, green: int, blue: int) -> None:
        rgb = (red, green, blue)
        await self._controller.set_color(self, rgb=rgb, temperature=None)
        self._rgb_color = rgb
        self._temperature_color = 0
        # Master color propagates to all segments
        for segment in self._segments:
            segment.color = rgb
            segment.temperature = 0
            segment.is_on = True
        self._trigger_update_callbacks()

    async def set_temperature(self, temperature: int) -> None:
        await self._controller.set_color(self, temperature=temperature, rgb=None)
        self._temperature_color = temperature
        # Master temp propagates to all segments
        for segment in self._segments:
            segment.temperature = temperature
            segment.color = (255, 255, 255)
            segment.is_on = True
        self._trigger_update_callbacks()

    async def set_scene(self, scene: str) -> None:
        await self._controller.set_scene(self, scene)

    async def send_raw_command(self, command: str) -> None:
        await self._controller.send_raw_command(self, command)

    def update(self, message: DevStatusResponse) -> None:
        # Detect global physical changes
        power_changed = self._is_on != message.is_on
        
        self._is_on = message.is_on
        self._brightness = message.brightness
        if message.color != (0, 0, 0):
            self._rgb_color = message.color
        self._temperature_color = message.color_temperature
        
        # Sync segments on initialization OR if a physical power state change was detected
        if not self._initial_update_done or power_changed:
            for segment in self._segments:
                segment.is_on = self._is_on
                segment.brightness = self._brightness
                if self._temperature_color > 0:
                    segment.temperature = self._temperature_color
                    segment.color = (255, 255, 255)
                else:
                    segment.color = self._rgb_color
                    segment.temperature = 0
            self._initial_update_done = True
                
        self.update_lastseen()
        self._trigger_update_callbacks()

    def update_lastseen(self) -> None:
        self._lastseen = datetime.now()

    def update_ip(self, ip: str) -> None:
        self._ip = ip

    def as_dict(self) -> dict[str, Any]:
        return {
            "ip": self._ip,
            "fingerprint": self._fingerprint,
            "sku": self._sku,
            "lastseen": self._lastseen,
            "on": self._is_on,
            "brightness": self._brightness,
            "color": self._rgb_color,
            "colorTemperature": self._temperature_color,
        }

    def __str__(self) -> str:
        result = f"<GoveeDevice ip={self.ip}, fingerprint={self.fingerprint}, sku={self.sku}, lastseen={self._lastseen}, is_on={self._is_on}"
        return result + (
            f", brightness={self._brightness}, color={self._rgb_color}, temperature={self._temperature_color}>"
            if self._is_on
            else ">"
        )
