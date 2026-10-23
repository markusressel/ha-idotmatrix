"""Fixtures for the iDotMatrix tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.device import BLEDevice
from idotmatrix.util.device_info import DeviceInfo
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.idotmatrix.const import CONF_SCREEN_SIZE, DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant

ADDRESS = "AA:BB:CC:DD:EE:FF"
NAME = "IDM-123456"
LIGHT = "light.idm_123456"

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations: None, enable_bluetooth: None) -> None:
    """Load the integration from custom_components, and a Bluetooth stack without adapters."""


@pytest.fixture
def ble_device() -> BLEDevice:
    return BLEDevice(ADDRESS, NAME, {})


@pytest.fixture
def device_info() -> DeviceInfo:
    return DeviceInfo(firmware_version="5.09", screen_type=4, password_protected=False, switch_status=1)


@pytest.fixture
def client(device_info: DeviceInfo) -> Generator[MagicMock]:
    """The client of the library, so that no display is needed."""
    with patch("custom_components.idotmatrix.device.IDotMatrixClient") as client_cls:
        client = client_cls.return_value
        for module in (
            "common",
            "color",
            "clock",
            "effect",
            "image",
            "gif",
            "text",
            "countdown",
            "chronograph",
            "scoreboard",
            "graffiti",
            "eco",
            "music_sync",
            "materials",
        ):
            setattr(client, module, MagicMock())
        for module, methods in {
            "common": ["turn_on", "turn_off", "set_brightness", "set_screen_flipped", "reset", "freeze_screen"],
            "color": ["show_color"],
            "clock": ["show"],
            "effect": ["show"],
            "image": ["show_image_file"],
            "gif": ["upload_gif_file"],
            "text": ["show_text"],
            "countdown": ["start", "pause", "restart", "stop"],
            "chronograph": ["start_from_zero", "pause", "resume", "reset"],
            "scoreboard": ["show"],
            "graffiti": ["set_pixels"],
            "eco": ["set_mode"],
            "music_sync": ["set_mic_type"],
            "materials": ["store", "clear"],
        }.items():
            for method in methods:
                setattr(getattr(client, module), method, AsyncMock())
        client.common.get_device_info = AsyncMock(return_value=device_info)
        client.disconnect = AsyncMock()
        yield client


@pytest.fixture
def reachable(ble_device: BLEDevice) -> Generator[None]:
    """The Bluetooth stack can reach the display."""
    with patch(
        "custom_components.idotmatrix.device.bluetooth.async_ble_device_from_address", return_value=ble_device
    ):
        yield


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        title=NAME,
        data={CONF_ADDRESS: ADDRESS, CONF_NAME: NAME, CONF_SCREEN_SIZE: "64x64"},
    )


@pytest.fixture
async def setup(hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock, reachable: None) -> MockConfigEntry:
    """A configured display."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
