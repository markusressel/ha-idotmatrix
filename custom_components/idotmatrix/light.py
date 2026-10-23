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
from .const import MAX_BRIGHTNESS_PERCENT, MIN_BRIGHTNESS_PERCENT, MODE_CLOCK, MODE_EFFECT, MODE_LIGHT
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
    """Set up the lights of a display."""
    async_add_entities([IDotMatrixLight(entry.runtime_data), IDotMatrixClockLight(entry.runtime_data)])
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
        state = self._device.state
        if state.mode == MODE_CLOCK:
            return EFFECT_CLOCK
        return state.effect if state.mode == MODE_EFFECT else None

    def _restore(self, last_state: State) -> None:
        state = self._device.state
        state.is_on = last_state.state == STATE_ON
        attributes = last_state.attributes
        if (brightness := attributes.get(ATTR_BRIGHTNESS)) is not None:
            state.brightness = brightness
        if (rgb_color := attributes.get(ATTR_RGB_COLOR)) is not None:
            state.rgb_color = tuple(rgb_color)
        if (effect := attributes.get(ATTR_EFFECT)) == EFFECT_CLOCK:
            state.mode = MODE_CLOCK
        elif effect is not None:
            state.mode = MODE_EFFECT
            state.effect = effect
        elif state.rgb_color is not None:
            state.mode = MODE_LIGHT

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
            state.mode = MODE_LIGHT

        self._device.async_state_changed()

    async def _async_show_effect(self, effect: str) -> None:
        if effect == EFFECT_CLOCK:
            await self._device.async_show_clock()
            return
        await self._device.call(self._device.client.effect.show(EFFECTS[effect], DEFAULT_PALETTE))
        self._device.state.effect = effect
        self._device.state.mode = MODE_EFFECT

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the screen off."""
        await self._device.call(self._device.client.common.turn_off())
        self._device.state.is_on = False
        self._device.async_state_changed()


class IDotMatrixClockLight(IDotMatrixEntity, LightEntity):
    """
    The clock. Turning it on shows the clock, also when it is shown already, and its color is the color of the
    clock (which the clock style "color" shows). It is on while the clock is shown. Turning it off turns the
    screen off, like the main light does, because the display has no state "no clock".
    """

    _attr_translation_key = "clock"
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(self, device: IDotMatrixDevice) -> None:
        super().__init__(device, "clock_light")

    @property
    def is_on(self) -> bool:
        state = self._device.state
        return state.is_on and state.mode == MODE_CLOCK

    @property
    def brightness(self) -> int:
        return self._device.state.brightness

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        return self._device.state.clock_color

    def _restore(self, last_state: State) -> None:
        if (rgb_color := last_state.attributes.get(ATTR_RGB_COLOR)) is not None:
            self._device.state.clock_color = tuple(rgb_color)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Show the clock, in the given color."""
        state = self._device.state
        if ATTR_BRIGHTNESS in kwargs:
            await self._device.call(
                self._device.client.common.set_brightness(brightness_to_percent(kwargs[ATTR_BRIGHTNESS]))
            )
            state.brightness = kwargs[ATTR_BRIGHTNESS]
        if ATTR_RGB_COLOR in kwargs:
            state.clock_color = tuple(kwargs[ATTR_RGB_COLOR])
        await self._device.async_show_clock()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the screen off."""
        await self._device.call(self._device.client.common.turn_off())
        self._device.state.is_on = False
        self._device.async_state_changed()
