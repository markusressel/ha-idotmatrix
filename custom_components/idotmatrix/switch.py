"""Switches of the display."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory, STATE_ON
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
    """Set up the switches of a display."""
    async_add_entities([IDotMatrixFlipSwitch(entry.runtime_data)])


class IDotMatrixFlipSwitch(IDotMatrixEntity, SwitchEntity):
    """Rotates the picture by 180 degrees."""

    _attr_translation_key = "flip"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device: IDotMatrixDevice) -> None:
        super().__init__(device, "flip")

    @property
    def is_on(self) -> bool:
        return self._device.state.flipped

    def _restore(self, last_state: State) -> None:
        self._device.state.flipped = last_state.state == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.call(self._device.client.common.set_screen_flipped(True))
        self._device.state.flipped = True
        self._device.async_state_changed()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.call(self._device.client.common.set_screen_flipped(False))
        self._device.state.flipped = False
        self._device.async_state_changed()
