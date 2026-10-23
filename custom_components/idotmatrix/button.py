"""Buttons of the display."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IDotMatrixConfigEntry
from .device import IDotMatrixDevice
from .entity import IDotMatrixEntity


@dataclass(frozen=True, kw_only=True)
class IDotMatrixButtonDescription(ButtonEntityDescription):
    """Describes a button, and what it does."""

    press_fn: Callable[[IDotMatrixDevice], Awaitable[object]]


BUTTONS = (
    IDotMatrixButtonDescription(
        key="sync_time",
        translation_key="sync_time",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda device: device.async_sync_time(),
    ),
    IDotMatrixButtonDescription(
        key="show_clock",
        translation_key="show_clock",
        press_fn=lambda device: device.async_show_clock(),
    ),
    IDotMatrixButtonDescription(
        key="reset",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda device: device.call(device.client.common.reset()),
    ),
    IDotMatrixButtonDescription(
        key="freeze",
        translation_key="freeze",
        press_fn=lambda device: device.call(device.client.common.freeze_screen()),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IDotMatrixConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons of a display."""
    async_add_entities(IDotMatrixButton(entry.runtime_data, description) for description in BUTTONS)


class IDotMatrixButton(IDotMatrixEntity, ButtonEntity):
    """A button that sends one command."""

    entity_description: IDotMatrixButtonDescription
    _attr_assumed_state = False

    def __init__(self, device: IDotMatrixDevice, description: IDotMatrixButtonDescription) -> None:
        super().__init__(device, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self._device)
