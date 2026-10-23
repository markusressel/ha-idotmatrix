"""Tests of the light entity."""

from unittest.mock import MagicMock

from bleak.exc import BleakError
from idotmatrix.modules.effect import EffectStyle
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_EFFECT, ATTR_RGB_COLOR, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import LIGHT


async def _turn_on(hass: HomeAssistant, **data) -> None:
    await hass.services.async_call(LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: LIGHT, **data}, blocking=True)


async def test_initial_state(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    assert hass.states.get(LIGHT).state == STATE_ON


async def test_turn_off_and_on(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await hass.services.async_call(LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: LIGHT}, blocking=True)

    client.common.turn_off.assert_awaited_once()
    assert hass.states.get(LIGHT).state == STATE_OFF

    await _turn_on(hass)

    client.common.turn_on.assert_awaited_once()
    assert hass.states.get(LIGHT).state == STATE_ON


async def test_brightness_is_scaled_to_percent(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await _turn_on(hass, **{ATTR_BRIGHTNESS: 128})

    client.common.set_brightness.assert_awaited_once_with(50)
    assert hass.states.get(LIGHT).attributes[ATTR_BRIGHTNESS] == 128


async def test_brightness_is_at_least_five_percent(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await _turn_on(hass, **{ATTR_BRIGHTNESS: 1})

    client.common.set_brightness.assert_awaited_once_with(5)


async def test_color(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await _turn_on(hass, **{ATTR_RGB_COLOR: (10, 20, 30)})

    client.color.show_color.assert_awaited_once_with((10, 20, 30))
    assert hass.states.get(LIGHT).attributes[ATTR_RGB_COLOR] == (10, 20, 30)


async def test_effect(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await _turn_on(hass, **{ATTR_EFFECT: "Rainbow (vertical)"})

    assert client.effect.show.await_args.args[0] is EffectStyle.VERTICAL_RAINBOW
    assert hass.states.get(LIGHT).attributes[ATTR_EFFECT] == "Rainbow (vertical)"


async def test_clock_effect(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await _turn_on(hass, **{ATTR_EFFECT: "Clock"})

    client.clock.show.assert_awaited_once()


async def test_a_failing_command_is_reported(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    client.common.turn_off.side_effect = BleakError("out of range")

    with pytest.raises(HomeAssistantError, match="out of range"):
        await hass.services.async_call(LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: LIGHT}, blocking=True)

    assert hass.states.get(LIGHT).state == STATE_ON
