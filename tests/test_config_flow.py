"""Tests of the config flow."""

from unittest.mock import MagicMock, patch

from bleak.exc import BleakError
from idotmatrix.util.device_info import DeviceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.idotmatrix.const import CONF_IDLE_TIMEOUT, CONF_SCREEN_SIZE, DOMAIN
from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import ADDRESS, NAME


def _service_info(ble_device, name: str = NAME, address: str = ADDRESS) -> BluetoothServiceInfoBleak:
    from habluetooth import BluetoothServiceInfoBleak as Info
    from bleak.backends.scanner import AdvertisementData

    ble_device.name = name
    ble_device.address = address
    return Info(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        source="local",
        device=ble_device,
        advertisement=AdvertisementData(
            local_name=name, manufacturer_data={}, service_data={}, service_uuids=[], tx_power=None, rssi=-60, platform_data=()
        ),
        connectable=True,
        time=0,
        tx_power=None,
    )


async def test_bluetooth_discovery(hass: HomeAssistant, ble_device, client: MagicMock, reachable: None) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=_service_info(ble_device)
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"] == {"name": NAME}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_ADDRESS: ADDRESS, CONF_NAME: NAME, CONF_SCREEN_SIZE: "64x64"}
    assert result["result"].unique_id == ADDRESS


async def test_the_connection_of_the_flow_is_handed_to_the_entry(
    hass: HomeAssistant, ble_device, client: MagicMock, reachable: None
) -> None:
    """Every connection makes the display play an animation, so the entry must not connect a second time."""
    from custom_components.idotmatrix import device as device_module

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=_service_info(ble_device)
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
    await hass.async_block_till_done()

    assert result["result"].state is ConfigEntryState.LOADED
    assert device_module.IDotMatrixClient.call_count == 1
    client.disconnect.assert_not_awaited()
    assert client.screen_size.name == "SIZE_64x64"
    assert not hass.data[DOMAIN]["pending_devices"]


async def test_the_connection_of_a_failed_flow_is_closed(
    hass: HomeAssistant, ble_device, client: MagicMock, reachable: None
) -> None:
    client.common.get_device_info.return_value = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=_service_info(ble_device)
    )

    await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    client.disconnect.assert_awaited()
    assert not hass.data.get(DOMAIN, {}).get("pending_devices")


async def test_bluetooth_discovery_of_a_configured_display_is_aborted(
    hass: HomeAssistant, ble_device, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=_service_info(ble_device)
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_cannot_connect(
    hass: HomeAssistant, ble_device, client: MagicMock, reachable: None
) -> None:
    client.common.get_device_info.side_effect = BleakError("no")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=_service_info(ble_device)
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    client.common.get_device_info.side_effect = None
    client.common.get_device_info.return_value = DeviceInfo("5.09", 3, False, 1)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SCREEN_SIZE] == "32x32"


async def test_no_answer_is_cannot_connect(
    hass: HomeAssistant, ble_device, client: MagicMock, reachable: None
) -> None:
    client.common.get_device_info.return_value = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=_service_info(ble_device)
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    assert result["errors"] == {"base": "cannot_connect"}


async def test_unexpected_error(hass: HomeAssistant, ble_device, client: MagicMock, reachable: None) -> None:
    client.common.get_device_info.side_effect = RuntimeError("boom")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=_service_info(ble_device)
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    assert result["errors"] == {"base": "unknown"}


async def test_unsupported_screen_is_aborted(
    hass: HomeAssistant, ble_device, client: MagicMock, reachable: None
) -> None:
    client.common.get_device_info.return_value = DeviceInfo("5.09", 11, False, 1)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=_service_info(ble_device)
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_user_step_lists_the_displays_that_were_found(
    hass: HomeAssistant, ble_device, client: MagicMock, reachable: None
) -> None:
    other = MagicMock(address="11:22:33:44:55:66")
    other_info = _service_info(MagicMock(), name="Headphones", address="11:22:33:44:55:66")
    with patch(
        "custom_components.idotmatrix.config_flow.async_discovered_service_info",
        return_value=[_service_info(ble_device), other_info],
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert list(result["data_schema"].schema[CONF_ADDRESS].container) == [ADDRESS]

        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={CONF_ADDRESS: ADDRESS})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SCREEN_SIZE] == "64x64"


async def test_user_step_without_displays(hass: HomeAssistant) -> None:
    with patch("custom_components.idotmatrix.config_flow.async_discovered_service_info", return_value=[]):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_skips_configured_displays(
    hass: HomeAssistant, ble_device, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    with patch(
        "custom_components.idotmatrix.config_flow.async_discovered_service_info",
        return_value=[_service_info(ble_device)],
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

    assert result["reason"] == "no_devices_found"


async def test_options(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    result = await hass.config_entries.options.async_init(setup.entry_id)

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input={CONF_IDLE_TIMEOUT: 120})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert setup.options == {CONF_IDLE_TIMEOUT: 120}
