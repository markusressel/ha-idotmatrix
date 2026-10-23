"""Selects of the display: clock style and music sync scene."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from idotmatrix.modules.clock import ClockStyle

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IDotMatrixConfigEntry
from .device import IDotMatrixDevice
from .entity import IDotMatrixEntity

CLOCK_STYLES = {
    "rgb_swipe_outline": ClockStyle.RGBSwipeOutline,
    "christmas_tree": ClockStyle.ChristmasTree,
    "checkers": ClockStyle.Checkers,
    "color": ClockStyle.Color,
    "hourglass": ClockStyle.Hourglass,
    "alarm_clock": ClockStyle.AlarmClock,
    "outlines": ClockStyle.Outlines,
    "rgb_corners": ClockStyle.RGBCorners,
}
# the device microphone scenes 1-5 were tried on a 64x64, there may be more
MUSIC_SYNC_SCENES = ["1", "2", "3", "4", "5"]


@dataclass(frozen=True, kw_only=True)
class IDotMatrixSelectDescription(SelectEntityDescription):
    """Describes a select, and what choosing an option does."""

    select_fn: Callable[[IDotMatrixDevice, str], Awaitable[object]]
    get_fn: Callable[[IDotMatrixDevice], str | None]
    set_fn: Callable[[IDotMatrixDevice, str], None]


SELECTS = (
    IDotMatrixSelectDescription(
        key="clock_style",
        translation_key="clock_style",
        options=list(CLOCK_STYLES),
        select_fn=lambda device, option: device.call(device.client.clock.show(CLOCK_STYLES[option])),
        get_fn=lambda device: device.state.clock_style,
        set_fn=lambda device, option: setattr(device.state, "clock_style", option),
    ),
    IDotMatrixSelectDescription(
        key="music_sync",
        translation_key="music_sync",
        options=MUSIC_SYNC_SCENES,
        select_fn=lambda device, option: device.call(device.client.music_sync.set_mic_type(int(option))),
        get_fn=lambda device: device.state.music_sync,
        set_fn=lambda device, option: setattr(device.state, "music_sync", option),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IDotMatrixConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the selects of a display."""
    async_add_entities(IDotMatrixSelect(entry.runtime_data, description) for description in SELECTS)


class IDotMatrixSelect(IDotMatrixEntity, SelectEntity):
    """Showing a clock style or a music sync scene is an action, the option is the last one that was chosen."""

    entity_description: IDotMatrixSelectDescription

    def __init__(self, device: IDotMatrixDevice, description: IDotMatrixSelectDescription) -> None:
        super().__init__(device, description.key)
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        return self.entity_description.get_fn(self._device)

    def _restore(self, last_state: State) -> None:
        if last_state.state in self.entity_description.options:
            self.entity_description.set_fn(self._device, last_state.state)

    async def async_select_option(self, option: str) -> None:
        await self.entity_description.select_fn(self._device, option)
        self.entity_description.set_fn(self._device, option)
        self._device.async_state_changed()
