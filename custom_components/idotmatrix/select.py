"""Selects of the display: clock style and music sync scene."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IDotMatrixConfigEntry
from .const import CLOCK_STYLES, MODE_CLOCK, MODE_MUSIC
from .device import IDotMatrixDevice
from .entity import IDotMatrixEntity

# the device microphone scenes 1-5 were tried on a 64x64, there may be more
MUSIC_SYNC_SCENES = ["1", "2", "3", "4", "5"]


@dataclass(frozen=True, kw_only=True)
class IDotMatrixSelectDescription(SelectEntityDescription):
    """
    Describes a select. Choosing an option shows something, so the select only has an option while that is shown.
    Otherwise it is unknown, which makes it possible to choose the same option again.
    """

    mode: str
    select_fn: Callable[[IDotMatrixDevice, str], Awaitable[object]]
    get_fn: Callable[[IDotMatrixDevice], str | None]
    set_fn: Callable[[IDotMatrixDevice, str], None]


async def _select_clock_style(device: IDotMatrixDevice, option: str) -> None:
    device.state.clock_style = option
    await device.async_show_clock()


async def _select_music_scene(device: IDotMatrixDevice, option: str) -> None:
    await device.call(device.client.music_sync.set_mic_type(int(option)))
    device.state.music_scene = option
    device.async_content_changed(MODE_MUSIC)


SELECTS = (
    IDotMatrixSelectDescription(
        key="clock_style",
        translation_key="clock_style",
        options=list(CLOCK_STYLES),
        mode=MODE_CLOCK,
        select_fn=_select_clock_style,
        get_fn=lambda device: device.state.clock_style,
        set_fn=lambda device, option: setattr(device.state, "clock_style", option),
    ),
    IDotMatrixSelectDescription(
        key="music_sync",
        translation_key="music_sync",
        options=MUSIC_SYNC_SCENES,
        mode=MODE_MUSIC,
        select_fn=_select_music_scene,
        get_fn=lambda device: device.state.music_scene,
        set_fn=lambda device, option: setattr(device.state, "music_scene", option),
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
    """The option that was chosen last, while it is shown."""

    entity_description: IDotMatrixSelectDescription

    def __init__(self, device: IDotMatrixDevice, description: IDotMatrixSelectDescription) -> None:
        super().__init__(device, description.key)
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        if self._device.state.mode != self.entity_description.mode:
            return None
        return self.entity_description.get_fn(self._device)

    def _restore(self, last_state: State) -> None:
        if last_state.state in self.entity_description.options:
            self.entity_description.set_fn(self._device, last_state.state)
            self._device.state.mode = self.entity_description.mode

    async def async_select_option(self, option: str) -> None:
        self._device.stop_slideshow()
        await self.entity_description.select_fn(self._device, option)
