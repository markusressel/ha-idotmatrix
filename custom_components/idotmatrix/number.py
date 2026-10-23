"""The brightness of the night mode."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IDotMatrixConfigEntry
from .device import IDotMatrixDevice
from .entity import IDotMatrixEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IDotMatrixConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the numbers of a display."""
    async_add_entities([IDotMatrixNightModeBrightness(entry.runtime_data)])


class IDotMatrixNightModeBrightness(IDotMatrixEntity, NumberEntity):
    """How bright the display is while the night mode dims it. Setting it sends the night mode settings."""

    _attr_translation_key = "night_mode_brightness"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, device: IDotMatrixDevice) -> None:
        super().__init__(device, "night_mode_brightness")

    @property
    def native_value(self) -> float:
        return self._device.state.night_brightness

    def _restore(self, last_state: State) -> None:
        try:
            self._device.state.night_brightness = max(1, min(100, int(float(last_state.state))))
        except ValueError:
            pass

    async def async_set_native_value(self, value: float) -> None:
        previous = self._device.state.night_brightness
        self._device.state.night_brightness = int(value)
        try:
            await self._device.async_apply_night_mode()
        except Exception:
            self._device.state.night_brightness = previous
            raise
