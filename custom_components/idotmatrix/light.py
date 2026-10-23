"""The display as a light: screen on and off, brightness, fullscreen color and effects."""

from __future__ import annotations

from typing import Any

from idotmatrix.modules.effect import EffectStyle

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IDotMatrixConfigEntry
from .const import MAX_BRIGHTNESS_PERCENT, MIN_BRIGHTNESS_PERCENT
from .device import DEFAULT_PALETTE, IDotMatrixDevice
from .entity import IDotMatrixEntity
from .services import async_setup_services

EFFECT_CLOCK = "Clock"
EFFECTS = {
    "Rainbow (horizontal)": EffectStyle.GRADIENT_HORIZONTAL_RAINBOW,
    "Random colored pixels on black": EffectStyle.RANDOM_COLORED_PIXELS_ON_BLACK,
    "Random white pixels": EffectStyle.RANDOM_WHITE_PIXELS_ON_CHANGING_BACKGROUND,
    "Rainbow (vertical)": EffectStyle.VERTICAL_RAINBOW,
    "Rainbow (diagonal right)": EffectStyle.DIAGONAL_RIGHT_RAINBOW,
    "Rainbow (diagonal left)": EffectStyle.DIAGONAL_LEFT_RAINBOW_ON_BLACK,
    "Random colored pixels": EffectStyle.RANDOM_COLORED_PIXELS,
}


def brightness_to_percent(brightness: int) -> int:
    """Home Assistant uses 1-255, the display 5-100 %."""
    percent = round(brightness / 255 * 100)
    return max(MIN_BRIGHTNESS_PERCENT, min(MAX_BRIGHTNESS_PERCENT, percent))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IDotMatrixConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the light of a display."""
    async_add_entities([IDotMatrixLight(entry.runtime_data)])
    async_setup_services()


class IDotMatrixLight(IDotMatrixEntity, LightEntity):
    """The whole display as one light."""

    _attr_name = None
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = [*EFFECTS, EFFECT_CLOCK]

    def __init__(self, device: IDotMatrixDevice) -> None:
        super().__init__(device, "light")

    @property
    def is_on(self) -> bool:
        return self._device.state.is_on

    @property
    def brightness(self) -> int:
        return self._device.state.brightness

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return self._device.state.rgb_color

    @property
    def effect(self) -> str | None:
        return self._device.state.effect

    def _restore(self, last_state: State) -> None:
        state = self._device.state
        state.is_on = last_state.state == STATE_ON
        attributes = last_state.attributes
        if (brightness := attributes.get(ATTR_BRIGHTNESS)) is not None:
            state.brightness = brightness
        if (rgb_color := attributes.get(ATTR_RGB_COLOR)) is not None:
            state.rgb_color = tuple(rgb_color)
        state.effect = attributes.get(ATTR_EFFECT)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the screen on, and show a color or an effect if asked to."""
        client = self._device.client
        state = self._device.state

        if not state.is_on or not kwargs:
            await self._device.call(client.common.turn_on())
            state.is_on = True

        if ATTR_BRIGHTNESS in kwargs:
            await self._device.call(client.common.set_brightness(brightness_to_percent(kwargs[ATTR_BRIGHTNESS])))
            state.brightness = kwargs[ATTR_BRIGHTNESS]

        if (effect := kwargs.get(ATTR_EFFECT)) is not None:
            await self._async_show_effect(effect)
        elif ATTR_RGB_COLOR in kwargs:
            color = tuple(kwargs[ATTR_RGB_COLOR])
            await self._device.call(client.color.show_color(color))
            state.rgb_color = color
            state.effect = None

        self._device.async_state_changed()

    async def _async_show_effect(self, effect: str) -> None:
        client = self._device.client
        state = self._device.state
        if effect == EFFECT_CLOCK:
            await self._device.call(client.clock.show())
        else:
            await self._device.call(client.effect.show(EFFECTS[effect], DEFAULT_PALETTE))
        state.effect = effect

    @callback
    def async_content_changed(self, effect: str | None = None) -> None:
        """Something was shown with an action, so the color or effect that was assumed is not shown anymore."""
        self._device.state.is_on = True
        self._device.state.rgb_color = None
        self._device.state.effect = effect
        self._device.async_state_changed()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the screen off."""
        await self._device.call(self._device.client.common.turn_off())
        self._device.state.is_on = False
        self._device.async_state_changed()
