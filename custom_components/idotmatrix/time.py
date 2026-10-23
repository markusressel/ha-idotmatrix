"""The times between which the night mode dims the display."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
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
    """Set up the night mode times of a display."""
    async_add_entities(
        [
            IDotMatrixNightModeTime(entry.runtime_data, "night_mode_start", "night_start"),
            IDotMatrixNightModeTime(entry.runtime_data, "night_mode_end", "night_end"),
        ]
    )


class IDotMatrixNightModeTime(IDotMatrixEntity, TimeEntity):
    """When the night mode starts or ends. Setting it sends the night mode settings to the display."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device: IDotMatrixDevice, key: str, attribute: str) -> None:
        super().__init__(device, key)
        self._attr_translation_key = key
        self._attribute = attribute

    @property
    def native_value(self) -> time:
        return getattr(self._device.state, self._attribute)

    def _restore(self, last_state: State) -> None:
        try:
            setattr(self._device.state, self._attribute, time.fromisoformat(last_state.state))
        except ValueError:
            pass

    async def async_set_value(self, value: time) -> None:
        previous = getattr(self._device.state, self._attribute)
        setattr(self._device.state, self._attribute, value.replace(second=0, microsecond=0))
        try:
            await self._device.async_apply_night_mode()
        except Exception:
            setattr(self._device.state, self._attribute, previous)
            raise
