"""Tests of the clock settings, the clock light and the night mode."""

from unittest.mock import MagicMock

from bleak.exc import BleakError
from idotmatrix.modules.clock import ClockStyle
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.light import ATTR_RGB_COLOR, DOMAIN as LIGHT_DOMAIN
from homeassistant.components.number import ATTR_VALUE, DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE as NUMBER_SET_VALUE
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN, SERVICE_SELECT_OPTION
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE as TIME_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import LIGHT

CLOCK_LIGHT = "light.idm_123456_clock"
CLOCK_STYLE = "select.idm_123456_clock_style"
SHOW_DATE = "switch.idm_123456_clock_shows_date"
HOUR24 = "switch.idm_123456_clock_24_hour_format"
SHOW_CLOCK = "button.idm_123456_show_clock"
NIGHT_MODE = "switch.idm_123456_night_mode_enabled"
NIGHT_START = "time.idm_123456_night_mode_start"
NIGHT_END = "time.idm_123456_night_mode_end"
NIGHT_BRIGHTNESS = "number.idm_123456_night_mode_brightness"


async def _switch(hass: HomeAssistant, entity_id: str, on: bool) -> None:
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON if on else SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )


async def _select_style(hass: HomeAssistant, option: str) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN, SERVICE_SELECT_OPTION, {ATTR_ENTITY_ID: CLOCK_STYLE, "option": option}, blocking=True
    )


async def test_clock_style_is_unknown_while_something_else_is_shown(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    await _select_style(hass, "color")
    assert hass.states.get(CLOCK_STYLE).state == "color"

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: LIGHT, ATTR_RGB_COLOR: (1, 2, 3)}, blocking=True
    )

    # so the same style can be chosen again to show the clock
    assert hass.states.get(CLOCK_STYLE).state == STATE_UNKNOWN

    await _select_style(hass, "color")

    assert client.clock.show.await_count == 2
    assert hass.states.get(CLOCK_STYLE).state == "color"


async def test_show_clock_button_shows_the_clock_with_one_command(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    await _select_style(hass, "hourglass")
    client.clock.show.reset_mock()

    await hass.services.async_call(BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: SHOW_CLOCK}, blocking=True)

    client.clock.show.assert_awaited_once_with(
        ClockStyle.Hourglass, show_date=True, hour24=True, color=(255, 255, 255)
    )


async def test_clock_light_shows_the_clock_in_a_color(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    assert hass.states.get(CLOCK_LIGHT).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: CLOCK_LIGHT, ATTR_RGB_COLOR: (10, 200, 30)}, blocking=True
    )

    client.clock.show.assert_awaited_once_with(
        ClockStyle.RGBSwipeOutline, show_date=True, hour24=True, color=(10, 200, 30)
    )
    assert hass.states.get(CLOCK_LIGHT).state == STATE_ON
    assert hass.states.get(CLOCK_LIGHT).attributes[ATTR_RGB_COLOR] == (10, 200, 30)
    assert hass.states.get(LIGHT).attributes["effect"] == "Clock"


async def test_clock_light_turned_on_again_shows_the_clock_again(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    for _ in range(2):
        await hass.services.async_call(LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: CLOCK_LIGHT}, blocking=True)

    assert client.clock.show.await_count == 2


async def test_clock_light_is_off_when_something_else_is_shown(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    await hass.services.async_call(LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: CLOCK_LIGHT}, blocking=True)
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: LIGHT, ATTR_RGB_COLOR: (1, 2, 3)}, blocking=True
    )

    assert hass.states.get(CLOCK_LIGHT).state == STATE_OFF


async def test_clock_light_turn_off_turns_the_screen_off(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    await hass.services.async_call(LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: CLOCK_LIGHT}, blocking=True)

    client.common.turn_off.assert_awaited_once()
    assert hass.states.get(LIGHT).state == STATE_OFF


async def test_date_switch_changes_the_shown_clock(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    await hass.services.async_call(LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: CLOCK_LIGHT}, blocking=True)
    client.clock.show.reset_mock()

    await _switch(hass, SHOW_DATE, False)

    client.clock.show.assert_awaited_once_with(
        ClockStyle.RGBSwipeOutline, show_date=False, hour24=True, color=(255, 255, 255)
    )
    assert hass.states.get(SHOW_DATE).state == STATE_OFF


async def test_clock_settings_do_not_change_the_display_if_the_clock_is_not_shown(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    await _switch(hass, SHOW_DATE, False)
    await _switch(hass, HOUR24, False)

    client.clock.show.assert_not_awaited()

    await hass.services.async_call(BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: SHOW_CLOCK}, blocking=True)

    client.clock.show.assert_awaited_once_with(
        ClockStyle.RGBSwipeOutline, show_date=False, hour24=False, color=(255, 255, 255)
    )


async def test_night_mode(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await hass.services.async_call(
        TIME_DOMAIN, TIME_SET_VALUE, {ATTR_ENTITY_ID: NIGHT_START, "time": "23:30:00"}, blocking=True
    )
    await hass.services.async_call(
        TIME_DOMAIN, TIME_SET_VALUE, {ATTR_ENTITY_ID: NIGHT_END, "time": "07:15:00"}, blocking=True
    )
    await hass.services.async_call(
        NUMBER_DOMAIN, NUMBER_SET_VALUE, {ATTR_ENTITY_ID: NIGHT_BRIGHTNESS, ATTR_VALUE: 20}, blocking=True
    )
    await _switch(hass, NIGHT_MODE, True)

    client.eco.set_mode.assert_awaited_with(
        enabled=True, start_hour=23, start_minute=30, end_hour=7, end_minute=15, eco_brightness=20
    )
    assert hass.states.get(NIGHT_START).state == "23:30:00"
    assert hass.states.get(NIGHT_END).state == "07:15:00"
    assert hass.states.get(NIGHT_MODE).state == STATE_ON


async def test_night_mode_defaults(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    assert hass.states.get(NIGHT_MODE).state == STATE_OFF
    assert hass.states.get(NIGHT_START).state == "22:00:00"
    assert hass.states.get(NIGHT_END).state == "06:00:00"
    assert float(hass.states.get(NIGHT_BRIGHTNESS).state) == 10


async def test_a_failing_night_mode_command_keeps_the_old_value(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    client.eco.set_mode.side_effect = BleakError("gone")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            TIME_DOMAIN, TIME_SET_VALUE, {ATTR_ENTITY_ID: NIGHT_START, "time": "23:30:00"}, blocking=True
        )

    assert hass.states.get(NIGHT_START).state == "22:00:00"


async def test_set_eco_action_updates_the_night_mode_entities(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    await hass.services.async_call(
        "idotmatrix",
        "set_eco",
        {ATTR_ENTITY_ID: LIGHT, "start_time": "21:00:00", "end_time": "05:00:00", "brightness": 30},
        blocking=True,
    )

    assert hass.states.get(NIGHT_START).state == "21:00:00"
    assert hass.states.get(NIGHT_MODE).state == STATE_ON
    assert float(hass.states.get(NIGHT_BRIGHTNESS).state) == 30
