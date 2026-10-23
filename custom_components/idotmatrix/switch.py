"""Switches of the display."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory, STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IDotMatrixConfigEntry
from .device import IDotMatrixDevice
from .entity import IDotMatrixEntity


@dataclass(frozen=True, kw_only=True)
class IDotMatrixSwitchDescription(SwitchEntityDescription):
    """Describes a switch, which is a setting that is stored in the assumed state."""

    get_fn: Callable[[IDotMatrixDevice], bool]
    set_fn: Callable[[IDotMatrixDevice, bool], None]
    apply_fn: Callable[[IDotMatrixDevice], Awaitable[object]]


async def _apply_flip(device: IDotMatrixDevice) -> None:
    await device.call(device.client.common.set_screen_flipped(device.state.flipped))
    device.async_state_changed()


async def _apply_night_mode(device: IDotMatrixDevice) -> None:
    await device.async_apply_night_mode()


SWITCHES = (
    IDotMatrixSwitchDescription(
        key="flip",
        translation_key="flip",
        entity_category=EntityCategory.CONFIG,
        get_fn=lambda device: device.state.flipped,
        set_fn=lambda device, value: setattr(device.state, "flipped", value),
        apply_fn=_apply_flip,
    ),
    IDotMatrixSwitchDescription(
        key="clock_show_date",
        translation_key="clock_show_date",
        entity_category=EntityCategory.CONFIG,
        get_fn=lambda device: device.state.clock_show_date,
        set_fn=lambda device, value: setattr(device.state, "clock_show_date", value),
        apply_fn=lambda device: device.async_update_clock(),
    ),
    IDotMatrixSwitchDescription(
        key="clock_hour24",
        translation_key="clock_hour24",
        entity_category=EntityCategory.CONFIG,
        get_fn=lambda device: device.state.clock_hour24,
        set_fn=lambda device, value: setattr(device.state, "clock_hour24", value),
        apply_fn=lambda device: device.async_update_clock(),
    ),
    IDotMatrixSwitchDescription(
        key="night_mode",
        translation_key="night_mode",
        entity_category=EntityCategory.CONFIG,
        get_fn=lambda device: device.state.night_enabled,
        set_fn=lambda device, value: setattr(device.state, "night_enabled", value),
        apply_fn=_apply_night_mode,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IDotMatrixConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switches of a display."""
    async_add_entities(IDotMatrixSwitch(entry.runtime_data, description) for description in SWITCHES)


class IDotMatrixSwitch(IDotMatrixEntity, SwitchEntity):
    """A setting of the display."""

    entity_description: IDotMatrixSwitchDescription

    def __init__(self, device: IDotMatrixDevice, description: IDotMatrixSwitchDescription) -> None:
        super().__init__(device, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.get_fn(self._device)

    def _restore(self, last_state: State) -> None:
        self.entity_description.set_fn(self._device, last_state.state == STATE_ON)

    async def _async_set(self, value: bool) -> None:
        previous = self.entity_description.get_fn(self._device)
        self.entity_description.set_fn(self._device, value)
        try:
            await self.entity_description.apply_fn(self._device)
        except Exception:
            self.entity_description.set_fn(self._device, previous)
            raise

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set(False)
