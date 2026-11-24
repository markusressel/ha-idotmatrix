"""Tests of setting up the integration."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from bleak.exc import BleakError
from idotmatrix import ScreenSize
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.idotmatrix.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .conftest import ADDRESS, LIGHT


async def test_setup_and_unload(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    assert setup.state is ConfigEntryState.LOADED
    assert hass.states.get(LIGHT) is not None

    assert await hass.config_entries.async_unload(setup.entry_id)
    await hass.async_block_till_done()

    assert setup.state is ConfigEntryState.NOT_LOADED
    client.disconnect.assert_awaited()


async def test_client_is_created_for_the_home_assistant_stack(setup: MockConfigEntry) -> None:
    from custom_components.idotmatrix import device

    kwargs = device.IDotMatrixClient.call_args.kwargs
    assert kwargs["screen_size"] is ScreenSize.SIZE_64x64
    assert kwargs["install_signal_handlers"] is False
    assert kwargs["ble_device"].address == ADDRESS


async def test_not_ready_if_the_display_is_not_reachable(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock
) -> None:
    config_entry.add_to_hass(hass)
    with patch("custom_components.idotmatrix.device.bluetooth.async_ble_device_from_address", return_value=None):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_is_registered(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    device = dr.async_get(hass).async_get_device_by_connection((dr.CONNECTION_BLUETOOTH, ADDRESS), setup.entry_id)

    assert device is not None
    assert device.manufacturer == "iDotMatrix"
    assert device.model == "64x64"


async def test_time_is_synced_and_firmware_is_registered_on_every_connection(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    listener = client.add_connection_listener.call_args.args[0]

    await listener.on_connected()
    await hass.async_block_till_done()

    client.common.get_device_info.assert_awaited()
    device = dr.async_get(hass).async_get_device_by_connection((dr.CONNECTION_BLUETOOTH, ADDRESS), setup.entry_id)
    assert device.sw_version == "5.09"


async def test_a_failing_time_sync_does_not_break_the_connection(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    client.common.get_device_info.side_effect = BleakError("gone")
    listener = client.add_connection_listener.call_args.args[0]

    await listener.on_connected()


async def test_time_is_set_again_when_the_utc_offset_changes(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    listener = client.add_connection_listener.call_args.args[0]
    await listener.on_connected()
    await hass.async_block_till_done()
    client.common.get_device_info.reset_mock()

    await hass.config.async_set_time_zone("Europe/Berlin")
    now = dt_util.now()
    async_fire_time_changed(hass, now + timedelta(minutes=1))
    await hass.async_block_till_done()
    client.common.get_device_info.assert_awaited_once()

    # unchanged offset, no new sync
    client.common.get_device_info.reset_mock()
    async_fire_time_changed(hass, now + timedelta(minutes=2))
    await hass.async_block_till_done()
    client.common.get_device_info.assert_not_awaited()


async def test_entities_are_unavailable_while_no_scanner_sees_the_display(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock, reachable: None, ble_device
) -> None:
    config_entry.add_to_hass(hass)
    with patch("custom_components.idotmatrix.bluetooth.async_track_unavailable") as track_unavailable:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    on_unavailable = track_unavailable.call_args.args[1]
    assert track_unavailable.call_args.args[2] == ADDRESS
    assert hass.states.get(LIGHT).state != STATE_UNAVAILABLE

    on_unavailable(MagicMock())
    await hass.async_block_till_done()
    assert hass.states.get(LIGHT).state == STATE_UNAVAILABLE

    config_entry.runtime_data.update_ble_device(ble_device)
    await hass.async_block_till_done()
    assert hass.states.get(LIGHT).state != STATE_UNAVAILABLE
    client.set_ble_device.assert_called_with(ble_device)


async def test_a_connected_display_stays_available_when_the_scanners_lose_it(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    """A connected display stops advertising, so the scanners lose it while it works."""
    listener = client.add_connection_listener.call_args.args[0]
    await listener.on_connected()

    setup.runtime_data.async_gone()
    await hass.async_block_till_done()
    assert hass.states.get(LIGHT).state != STATE_UNAVAILABLE

    await listener.on_disconnected()
    await hass.async_block_till_done()
    assert hass.states.get(LIGHT).state == STATE_UNAVAILABLE


async def test_a_connection_makes_the_display_available(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    setup.runtime_data.async_gone()
    await hass.async_block_till_done()

    await client.add_connection_listener.call_args.args[0].on_connected()
    await hass.async_block_till_done()

    assert hass.states.get(LIGHT).state != STATE_UNAVAILABLE
