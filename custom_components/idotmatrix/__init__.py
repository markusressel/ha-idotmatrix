"""The iDotMatrix integration."""

from __future__ import annotations

import logging

from bleak.exc import BleakError

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import CONF_IDLE_TIMEOUT, CONF_SCREEN_SIZE, DEFAULT_IDLE_TIMEOUT, DOMAIN, PENDING_DEVICES, SCREEN_SIZES
from .device import IDotMatrixDevice

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.LIGHT, Platform.SELECT, Platform.SWITCH, Platform.TEXT]

type IDotMatrixConfigEntry = ConfigEntry[IDotMatrixDevice]


async def async_setup_entry(hass: HomeAssistant, entry: IDotMatrixConfigEntry) -> bool:
    """Set up an iDotMatrix display from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    idle_timeout = entry.options.get(CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT)

    # the config flow leaves the display connected, a new connection would make it play its animation again
    device: IDotMatrixDevice | None = hass.data.get(DOMAIN, {}).get(PENDING_DEVICES, {}).pop(address, None)
    if device is not None:
        device.set_idle_timeout(idle_timeout)
    else:
        try:
            device = IDotMatrixDevice(
                hass,
                address=address,
                name=entry.data.get(CONF_NAME) or entry.title,
                screen_size=SCREEN_SIZES[entry.data[CONF_SCREEN_SIZE]],
                idle_timeout=idle_timeout,
            )
        except BleakError as ex:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"reason": str(ex)},
            ) from ex

    @callback
    def _async_update_ble(
        service_info: bluetooth.BluetoothServiceInfoBleak, change: bluetooth.BluetoothChange
    ) -> None:
        """The scanners saw the display again, maybe through another adapter or Bluetooth proxy."""
        device.update_ble_device(service_info.device)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher({ADDRESS: address}),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )

    async def _on_connected() -> None:
        """The clock of the display is set on every connection, as the official app does it."""
        try:
            info = await device.async_sync_time()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Could not set the time of %s", address, exc_info=True)
            return
        if info is not None:
            registry = dr.async_get(hass)
            if registered := registry.async_get_device_by_connection(
                (dr.CONNECTION_BLUETOOTH, address), entry.entry_id
            ):
                registry.async_update_device(registered.id, sw_version=info.firmware_version)

    entry.async_on_unload(device.add_connected_listener(_on_connected))

    async def _async_stop(_event: Event) -> None:
        """Close the connection cleanly, so the display is free for the next connection."""
        await device.async_disconnect()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop))

    entry.runtime_data = device
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: IDotMatrixConfigEntry) -> None:
    """The options changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: IDotMatrixConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_disconnect()
    return unloaded
