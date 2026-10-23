"""Tests of the connection handling of a display."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.exc import BleakError
from idotmatrix.connection_manager import UploadError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.idotmatrix.const import CONF_IDLE_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .conftest import ADDRESS


async def test_the_connection_is_closed_when_it_is_idle(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    device = setup.runtime_data
    client.disconnect.reset_mock()

    await device.call(client.common.turn_on())
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    client.disconnect.assert_not_awaited()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()

    client.disconnect.assert_awaited_once()


async def test_the_idle_timeout_can_be_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock, reachable: None
) -> None:
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={CONF_IDLE_TIMEOUT: 10})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    client.disconnect.reset_mock()

    await config_entry.runtime_data.call(client.common.turn_on())
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()

    client.disconnect.assert_awaited_once()


async def test_a_new_command_restarts_the_idle_timer(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    device = setup.runtime_data
    cancels = [MagicMock(), MagicMock()]

    with patch("custom_components.idotmatrix.device.async_call_later", side_effect=cancels) as call_later:
        await device.call(client.common.turn_on())
        await device.call(client.common.turn_on())

    assert [call.args[1] for call in call_later.call_args_list] == [60, 60]
    cancels[0].assert_called_once()
    cancels[1].assert_not_called()


async def test_no_idle_timer_without_a_timeout(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock, reachable: None
) -> None:
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={CONF_IDLE_TIMEOUT: 0})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with patch("custom_components.idotmatrix.device.async_call_later") as call_later:
        await config_entry.runtime_data.call(client.common.turn_on())

    call_later.assert_not_called()


@pytest.mark.parametrize("error", [BleakError("x"), TimeoutError(), UploadError("rejected")])
async def test_library_errors_become_home_assistant_errors(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock, error: Exception
) -> None:
    device = setup.runtime_data
    client.common.turn_on.side_effect = error

    with pytest.raises(HomeAssistantError):
        await device.call(client.common.turn_on())


async def test_a_newer_ble_device_is_handed_to_the_client(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock, ble_device
) -> None:
    setup.runtime_data.update_ble_device(ble_device)

    client.set_ble_device.assert_called_once_with(ble_device)


async def test_connect_uses_bleak_retry_connector(
    hass: HomeAssistant, setup: MockConfigEntry, ble_device
) -> None:
    from custom_components.idotmatrix import device as device_module

    callback = MagicMock()
    with patch.object(device_module, "establish_connection", AsyncMock(return_value="connected")) as establish:
        result = await setup.runtime_data._connect(ble_device, callback)

    assert result == "connected"
    assert establish.await_args.args[1] is ble_device
    assert establish.await_args.args[3] is callback
    assert establish.await_args.kwargs["ble_device_callback"]().address == ADDRESS


async def test_connect_fails_if_the_display_is_not_reachable(hass: HomeAssistant, setup: MockConfigEntry, ble_device) -> None:
    with patch("custom_components.idotmatrix.device.bluetooth.async_ble_device_from_address", return_value=None):
        with pytest.raises(BleakError, match="Could not find"):
            await setup.runtime_data._connect(ble_device, MagicMock())
