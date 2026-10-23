"""Tests of the actions."""

import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from idotmatrix.modules.clock import ClockStyle
from idotmatrix.modules.effect import EffectStyle
from idotmatrix.modules.text import TextColorMode, TextMode
from idotmatrix.util.image_utils import ResizeMode
import pytest
import voluptuous as vol
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.idotmatrix.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import LIGHT


async def _call(hass: HomeAssistant, service: str, **data) -> None:
    await hass.services.async_call(DOMAIN, service, {ATTR_ENTITY_ID: LIGHT, **data}, blocking=True)


async def test_show_text(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await _call(hass, "show_text", text="Hi", mode="blinking", color_mode="rgb", color=[1, 2, 3], speed=50)

    client.text.show_text.assert_awaited_once_with(
        "Hi",
        font_size=16,
        text_mode=TextMode.BLINKING,
        speed=50,
        text_color_mode=TextColorMode.RGB,
        text_color=(1, 2, 3),
        text_bg_color=None,
    )


async def test_show_clock(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await _call(hass, "show_clock", style="hourglass", hour24=False)

    client.clock.show.assert_awaited_once_with(
        ClockStyle.Hourglass, show_date=True, hour24=False, color=(255, 255, 255)
    )
    assert hass.states.get(LIGHT).attributes["effect"] == "Clock"


async def test_set_effect(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await _call(hass, "set_effect", style="vertical_rainbow", colors=[[255, 0, 0], [0, 0, 255]])

    client.effect.show.assert_awaited_once_with(EffectStyle.VERTICAL_RAINBOW, [(255, 0, 0), (0, 0, 255)])


async def test_set_effect_needs_two_colors(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    with pytest.raises(vol.Invalid):
        await _call(hass, "set_effect", style="vertical_rainbow", colors=[[255, 0, 0]])


async def test_countdown(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await _call(hass, "countdown", action="start", minutes=2, seconds=30)
    client.countdown.start.assert_awaited_once_with(2, 30)

    await _call(hass, "countdown", action="pause")
    client.countdown.pause.assert_awaited_once()

    await _call(hass, "countdown", action="stop")
    client.countdown.stop.assert_awaited_once()


async def test_chronograph(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await _call(hass, "chronograph", action="start")
    client.chronograph.start_from_zero.assert_awaited_once()

    await _call(hass, "chronograph", action="resume")
    client.chronograph.resume.assert_awaited_once()


async def test_scoreboard(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await _call(hass, "scoreboard", score_1=3, score_2=999)

    client.scoreboard.show.assert_awaited_once_with(3, 999)


async def test_set_pixels(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await _call(hass, "set_pixels", color=[255, 0, 0], pixels=[[0, 0], [1, 2]])

    client.graffiti.set_pixels.assert_awaited_once_with((255, 0, 0), [(0, 0), (1, 2)])


async def test_set_eco(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await _call(hass, "set_eco", start_time="22:30:00", end_time="06:15:00", brightness=20)

    client.eco.set_mode.assert_awaited_once_with(
        enabled=True, start_hour=22, start_minute=30, end_hour=6, end_minute=15, eco_brightness=20
    )


async def test_music_sync(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    await _call(hass, "music_sync", scene=4, sensitivity=70)

    client.music_sync.set_mic_type.assert_awaited_once_with(4, sensitivity=70)


async def test_show_image_from_a_file(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock, tmp_path: Path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"png")
    hass.config.allowlist_external_dirs = {str(tmp_path)}

    await _call(hass, "show_image", path=str(image), resize_mode="fill", palletize=True)

    client.image.show_image_file.assert_awaited_once_with(
        str(image), resize_mode=ResizeMode.FILL, palletize=True, background_color=(0, 0, 0), png=False
    )


async def test_show_image_needs_a_source(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    with pytest.raises(vol.Invalid):
        await _call(hass, "show_image")


async def test_show_image_not_in_an_allowed_folder(hass: HomeAssistant, setup: MockConfigEntry, tmp_path: Path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"png")

    with pytest.raises(HomeAssistantError, match="not allowed"):
        await _call(hass, "show_image", path=str(image))


async def test_show_image_file_not_found(hass: HomeAssistant, setup: MockConfigEntry, tmp_path: Path) -> None:
    hass.config.allowlist_external_dirs = {str(tmp_path)}

    with pytest.raises(HomeAssistantError, match="does not exist"):
        await _call(hass, "show_image", path=str(tmp_path / "missing.png"))


async def test_show_gif_from_an_url(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    seen = {}

    async def upload(path, **kwargs):
        seen["content"] = Path(path).read_bytes()
        seen["path"] = path
        seen["kwargs"] = kwargs

    client.gif.upload_gif_file.side_effect = upload
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.content.read = AsyncMock(return_value=b"GIF89a")
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(return_value=response)
    session.get.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("custom_components.idotmatrix.services.async_get_clientsession", return_value=session):
        await _call(hass, "show_gif", url="https://example.com/a.gif", duration_per_frame=100)

    assert seen["content"] == b"GIF89a"
    assert seen["kwargs"]["duration_per_frame_in_ms"] == 100
    assert not Path(seen["path"]).exists()  # the temporary file is removed


async def test_download_failure(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    session = MagicMock()
    session.get.side_effect = OSError("no network")

    with patch("custom_components.idotmatrix.services.async_get_clientsession", return_value=session):
        with pytest.raises(HomeAssistantError, match="Could not download"):
            await _call(hass, "show_image", url="https://example.com/a.png")


async def test_invalid_values_from_the_library_are_reported(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    client.text.show_text.side_effect = ValueError("bad color")

    with pytest.raises(HomeAssistantError, match="bad color"):
        await _call(hass, "show_text", text="x")
