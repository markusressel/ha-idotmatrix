"""Tests of the switch, select, button and text entities."""

from unittest.mock import MagicMock

from idotmatrix.modules.clock import ClockStyle
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN, SERVICE_SELECT_OPTION
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.text import DOMAIN as TEXT_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

FLIP = "switch.idm_123456_flip_display"
CLOCK_STYLE = "select.idm_123456_clock_style"
MUSIC_SYNC = "select.idm_123456_music_sync_scene"
MESSAGE = "text.idm_123456_message"


async def test_flip(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    assert hass.states.get(FLIP).state == STATE_OFF

    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: FLIP}, blocking=True)

    client.common.set_screen_flipped.assert_awaited_once_with(True)
    assert hass.states.get(FLIP).state == STATE_ON

    await hass.services.async_call(SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: FLIP}, blocking=True)

    client.common.set_screen_flipped.assert_awaited_with(False)
    assert hass.states.get(FLIP).state == STATE_OFF


async def test_clock_style(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN, SERVICE_SELECT_OPTION, {ATTR_ENTITY_ID: CLOCK_STYLE, "option": "hourglass"}, blocking=True
    )

    client.clock.show.assert_awaited_once_with(
        ClockStyle.Hourglass, show_date=True, hour24=True, color=(255, 255, 255)
    )
    assert hass.states.get(CLOCK_STYLE).state == "hourglass"


async def test_music_sync(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN, SERVICE_SELECT_OPTION, {ATTR_ENTITY_ID: MUSIC_SYNC, "option": "3"}, blocking=True
    )

    client.music_sync.set_mic_type.assert_awaited_once_with(3)
    assert hass.states.get(MUSIC_SYNC).state == "3"


async def test_text(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await hass.services.async_call(
        TEXT_DOMAIN, SERVICE_SET_VALUE, {ATTR_ENTITY_ID: MESSAGE, "value": "Hello"}, blocking=True
    )

    client.text.show_text.assert_awaited_once_with("Hello")
    assert hass.states.get(MESSAGE).state == "Hello"


async def test_buttons(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    for entity_id in ("button.idm_123456_restart", "button.idm_123456_freeze_or_unfreeze", "button.idm_123456_sync_time"):
        await hass.services.async_call(BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True)

    client.common.reset.assert_awaited_once()
    client.common.freeze_screen.assert_awaited_once()
    client.common.get_device_info.assert_awaited()


async def test_lights_and_switches_are_not_marked_as_assumed_state(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    """Home Assistant shows two lightning buttons instead of a toggle for entities with an assumed state."""
    for entity_id in (
        "light.idm_123456",
        "light.idm_123456_clock",
        "switch.idm_123456_flip_display",
        "switch.idm_123456_night_mode",
        "switch.idm_123456_clock_shows_date",
    ):
        assert "assumed_state" not in hass.states.get(entity_id).attributes, entity_id
