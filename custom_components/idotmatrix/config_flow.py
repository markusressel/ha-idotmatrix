"""Config flow of the iDotMatrix integration."""

from __future__ import annotations

import logging
from typing import Any

from bleak.exc import BleakError
from idotmatrix import ScreenSize
from idotmatrix.util.device_info import DeviceInfo
import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak, async_discovered_service_info
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig, NumberSelectorMode

from .const import (
    CONF_IDLE_TIMEOUT,
    CONF_SCREEN_SIZE,
    DEFAULT_IDLE_TIMEOUT,
    DOMAIN,
    MAX_IDLE_TIMEOUT,
    MIN_IDLE_TIMEOUT,
    SCREEN_SIZES,
)
from .device import IDotMatrixDevice

_LOGGER = logging.getLogger(__name__)

LOCAL_NAME_PREFIX = "IDM-"


def _screen_size_key(screen_size: ScreenSize) -> str:
    return next(key for key, value in SCREEN_SIZES.items() if value == screen_size)


class IDotMatrixConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iDotMatrix displays."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        """A display was discovered, by the adapters or the Bluetooth proxies of Home Assistant."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm the discovered display."""
        assert self._discovery_info is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            if (result := await self._async_create_entry(self._discovery_info, errors)) is not None:
                return result

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._discovery_info.name},
            errors=errors,
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick one of the displays that were found."""
        errors: dict[str, str] = {}
        if user_input is not None:
            discovery_info = self._discovered_devices[user_input[CONF_ADDRESS]]
            await self.async_set_unique_id(discovery_info.address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            if (result := await self._async_create_entry(discovery_info, errors)) is not None:
                return result

        current_addresses = self._async_current_ids(include_ignore=False)
        for discovery_info in async_discovered_service_info(self.hass, connectable=True):
            if (
                discovery_info.address in current_addresses
                or discovery_info.address in self._discovered_devices
                or not discovery_info.name.startswith(LOCAL_NAME_PREFIX)
            ):
                continue
            self._discovered_devices[discovery_info.address] = discovery_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            discovery_info.address: f"{discovery_info.name} ({discovery_info.address})"
                            for discovery_info in self._discovered_devices.values()
                        }
                    )
                }
            ),
            errors=errors,
        )

    async def _async_create_entry(
        self, discovery_info: BluetoothServiceInfoBleak, errors: dict[str, str]
    ) -> ConfigFlowResult | None:
        """
        Connects to the display to find out the size of its screen, and creates the entry.
        Returns None and sets an error if that did not work.
        """
        try:
            info = await self._async_read_device_info(discovery_info)
        except (BleakError, TimeoutError, HomeAssistantError):
            _LOGGER.debug("Could not connect to %s", discovery_info.address, exc_info=True)
            errors["base"] = "cannot_connect"
            return None
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error while connecting to %s", discovery_info.address)
            errors["base"] = "unknown"
            return None

        if info is None:
            errors["base"] = "cannot_connect"
            return None
        if info.screen_size is None:
            return self.async_abort(reason="not_supported")

        return self.async_create_entry(
            title=discovery_info.name,
            data={
                CONF_ADDRESS: discovery_info.address,
                CONF_NAME: discovery_info.name,
                CONF_SCREEN_SIZE: _screen_size_key(info.screen_size),
            },
        )

    async def _async_read_device_info(self, discovery_info: BluetoothServiceInfoBleak) -> DeviceInfo | None:
        # the screen size is not known yet, it is only used for images, which are not sent here
        device = IDotMatrixDevice(
            self.hass,
            address=discovery_info.address,
            name=discovery_info.name,
            screen_size=ScreenSize.SIZE_64x64,
            idle_timeout=0,
        )
        try:
            return await device.async_sync_time()
        finally:
            await device.async_disconnect()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return IDotMatrixOptionsFlow()


class IDotMatrixOptionsFlow(OptionsFlow):
    """The options of a display."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_IDLE_TIMEOUT,
                        default=self.config_entry.options.get(CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_IDLE_TIMEOUT,
                            max=MAX_IDLE_TIMEOUT,
                            step=1,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    )
                }
            ),
        )
