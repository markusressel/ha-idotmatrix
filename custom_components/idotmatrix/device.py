"""The connection to one iDotMatrix display."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from idotmatrix import IDotMatrixClient, ScreenSize
from idotmatrix.connection_manager import CommandRejectedError, ConnectionListener, UploadError
from idotmatrix.transport import BleakTransport
from idotmatrix.util.device_info import DeviceInfo

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothReachabilityIntent
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .const import DOMAIN, HEARTBEAT_INTERVAL

_LOGGER = logging.getLogger(__name__)

DEFAULT_PALETTE = [(255, 0, 0), (255, 165, 0), (255, 255, 0), (0, 255, 0), (0, 0, 255), (160, 32, 240)]


@dataclass
class DeviceState:
    """
    What the integration believes the display shows. The device does not report its state, so this is what was
    sent last (assumed state).
    """

    is_on: bool = True
    brightness: int = 255  # 1-255
    rgb_color: tuple[int, int, int] | None = None
    effect: str | None = None
    flipped: bool = False
    clock_style: str | None = None
    music_sync: str | None = None


class IDotMatrixDevice:
    """Wraps the client of the library: connects on demand over the Bluetooth stack of Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
        screen_size: ScreenSize,
        idle_timeout: float,
    ) -> None:
        self.hass = hass
        self.address = address
        self.name = name
        self.screen_size = screen_size
        self.idle_timeout = idle_timeout
        self.state = DeviceState()
        self.firmware_version: str | None = None

        self._cancel_idle: CALLBACK_TYPE | None = None
        self._listeners: list[CALLBACK_TYPE] = []
        self._connected_listeners: list[Callable[[], Awaitable[Any]]] = []

        ble_device = self._ble_device()
        if ble_device is None:
            raise BleakError(self.unreachable_reason())

        self.client = IDotMatrixClient(
            screen_size=screen_size,
            ble_device=ble_device,
            transport_factory=lambda target, on_disconnected: BleakTransport(
                target, on_disconnected, connector=self._connect
            ),
            # Home Assistant handles the signals itself, and takes care of reconnecting
            install_signal_handlers=False,
        )
        self.client.add_connection_listener(
            ConnectionListener(on_connected=self._on_connected, on_disconnected=self._on_disconnected)
        )
        self.set_idle_timeout(idle_timeout)

    def set_idle_timeout(self, idle_timeout: float) -> None:
        """
        Sets after how many seconds without a command the connection is closed. 0 keeps it open, and checks
        that the display is still there, because every new connection makes the display play an animation.
        """
        self.idle_timeout = idle_timeout
        self.client.set_heartbeat(None if idle_timeout else HEARTBEAT_INTERVAL)
        if idle_timeout:
            self._restart_idle_timer()
        else:
            self._stop_idle_timer()

    def set_screen_size(self, screen_size: ScreenSize) -> None:
        """Sets the size of the screen, after it was found out."""
        self.screen_size = screen_size
        self.client.screen_size = screen_size

    # -- connection ---------------------------------------------------------------------------------------------

    def _ble_device(self) -> BLEDevice | None:
        return bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)

    def unreachable_reason(self) -> str:
        """Why no Bluetooth adapter or proxy can reach the device right now."""
        return (
            f"Could not find the iDotMatrix display {self.address}: "
            + bluetooth.async_address_reachability_diagnostics(
                self.hass, self.address, BluetoothReachabilityIntent.CONNECTION
            )
        )

    async def _connect(
        self, _target: str | BLEDevice, disconnected_callback: Callable[[BleakClient], None]
    ) -> BleakClient:
        """Connects like Home Assistant wants it: over any adapter or Bluetooth proxy that can reach the device."""
        ble_device = self._ble_device()
        if ble_device is None:
            raise BleakError(self.unreachable_reason())
        return await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            self.name,
            disconnected_callback,
            ble_device_callback=self._ble_device,
        )

    @callback
    def update_ble_device(self, ble_device: BLEDevice) -> None:
        """The scanners found the device again, possibly through another adapter or proxy."""
        self.client.set_ble_device(ble_device)

    async def async_disconnect(self) -> None:
        """Closes the connection."""
        self._stop_idle_timer()
        await self.client.disconnect()

    async def _on_connected(self) -> None:
        _LOGGER.debug("Connected to %s", self.address)
        for listener in self._connected_listeners:
            await listener()

    async def _on_disconnected(self) -> None:
        _LOGGER.debug("Disconnected from %s", self.address)

    def add_connected_listener(self, listener: Callable[[], Awaitable[Any]]) -> CALLBACK_TYPE:
        """Calls the listener every time a connection was made."""
        self._connected_listeners.append(listener)
        return lambda: self._connected_listeners.remove(listener)

    # -- idle timeout -------------------------------------------------------------------------------------------

    def _stop_idle_timer(self) -> None:
        if self._cancel_idle is not None:
            self._cancel_idle()
            self._cancel_idle = None

    def _restart_idle_timer(self) -> None:
        self._stop_idle_timer()
        if not self.idle_timeout:
            return

        async def _disconnect(_now: Any) -> None:
            self._cancel_idle = None
            _LOGGER.debug("Closing the idle connection to %s", self.address)
            await self.client.disconnect()

        self._cancel_idle = async_call_later(self.hass, self.idle_timeout, _disconnect)

    # -- commands -----------------------------------------------------------------------------------------------

    async def call(self, action: Awaitable[Any]) -> Any:
        """
        Runs a command of the library, which connects if needed. Errors become `HomeAssistantError`, so the user
        sees why a service call or entity action failed.
        """
        self._stop_idle_timer()
        try:
            return await action
        except (BleakError, TimeoutError, UploadError, CommandRejectedError) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(ex) or type(ex).__name__},
            ) from ex
        except ValueError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_value",
                translation_placeholders={"error": str(ex)},
            ) from ex
        finally:
            self._restart_idle_timer()

    async def async_sync_time(self) -> DeviceInfo | None:
        """Sets the clock of the device to the time of Home Assistant, and returns what the device tells about itself."""
        info = await self.call(self.client.common.get_device_info(dt_util.now().replace(tzinfo=None)))
        if info is not None:
            self.firmware_version = info.firmware_version
        return info

    # -- state --------------------------------------------------------------------------------------------------

    def add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Calls the listener when the assumed state changed."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def async_state_changed(self) -> None:
        """Tells the entities that the assumed state changed."""
        for listener in list(self._listeners):
            listener()
