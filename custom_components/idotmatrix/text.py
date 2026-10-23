"""Shows text on the display."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
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
    """Set up the text entity of a display."""
    async_add_entities([IDotMatrixText(entry.runtime_data)])


class IDotMatrixText(IDotMatrixEntity, TextEntity):
    """Setting the value shows it as scrolling text. Use the `show_text` action for colors, fonts and modes."""

    _attr_translation_key = "message"
    _attr_native_max = 255

    def __init__(self, device: IDotMatrixDevice) -> None:
        super().__init__(device, "message")
        self._value: str | None = None

    @property
    def native_value(self) -> str | None:
        return self._value

    def _restore(self, last_state: State) -> None:
        if last_state.state not in ("unknown", "unavailable"):
            self._value = last_state.state

    async def async_set_value(self, value: str) -> None:
        await self._device.call(self._device.client.text.show_text(value))
        self._value = value
        self._device.async_content_changed()
