"""Base entity of the iDotMatrix integration."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, MANUFACTURER
from .device import IDotMatrixDevice


class IDotMatrixEntity(RestoreEntity, Entity):
    """An entity of an iDotMatrix display. The state is assumed, the device does not report it."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    # The state is assumed, but with assumed_state Home Assistant shows two buttons with lightning icons instead of
    # one toggle for lights and switches, which looks wrong for a display that follows its commands reliably.
    _attr_assumed_state = False

    def __init__(self, device: IDotMatrixDevice, key: str) -> None:
        self._device = device
        self._attr_unique_id = f"{device.address}_{key}"
        width, height = device.screen_size.value
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, device.address)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=f"{width}x{height}",
            sw_version=device.firmware_version,
        )

    async def async_added_to_hass(self) -> None:
        """Restore the assumed state and listen to changes of it."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._restore(last_state)
        self.async_on_remove(self._device.add_listener(self._handle_state_changed))

    def _restore(self, last_state) -> None:
        """Restores the entity from the last state. Entities that keep state override it."""

    @callback
    def _handle_state_changed(self) -> None:
        self.async_write_ha_state()
