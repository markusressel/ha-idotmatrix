"""Tests of the actions."""

import asyncio
import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from idotmatrix.modules.clock import ClockStyle
from idotmatrix.modules.effect import EffectStyle
from idotmatrix.modules.text import TextColorMode, TextMode
from idotmatrix.util.image_utils import ResizeMode
from PIL import UnidentifiedImageError
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
    response.content_type = "image/gif"
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(return_value=response)
    session.get.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("custom_components.idotmatrix.media.async_get_clientsession", return_value=session):
        await _call(hass, "show_gif", url="https://example.com/a.gif", duration_per_frame=100)

    assert seen["content"] == b"GIF89a"
    assert seen["kwargs"]["duration_per_frame_in_ms"] == 100
    assert not Path(seen["path"]).exists()  # the temporary file is removed


async def test_download_failure(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    session = MagicMock()
    session.get.side_effect = OSError("no network")

    with patch("custom_components.idotmatrix.media.async_get_clientsession", return_value=session):
        with pytest.raises(HomeAssistantError, match="Could not download"):
            await _call(hass, "show_image", url="https://example.com/a.png")


async def test_invalid_values_from_the_library_are_reported(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    client.text.show_text.side_effect = ValueError("bad color")

    with pytest.raises(HomeAssistantError, match="bad color"):
        await _call(hass, "show_text", text="x")


def _session(content: bytes = b"png", content_type: str = "image/png") -> MagicMock:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.content.read = AsyncMock(return_value=content)
    response.content_type = content_type
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(return_value=response)
    session.get.return_value.__aexit__ = AsyncMock(return_value=False)
    return session


async def test_show_image_from_a_path_of_home_assistant(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock
) -> None:
    """The cover of a media player is served by Home Assistant itself, so the address is relative."""
    session = _session()

    with (
        patch("custom_components.idotmatrix.media.async_get_clientsession", return_value=session),
        patch("custom_components.idotmatrix.media.get_url", return_value="http://ha.local:8123"),
        patch("custom_components.idotmatrix.media.async_sign_path", side_effect=lambda hass, path, *a, **kw: path + "&authSig=1"),
    ):
        await _call(hass, "show_image", url="/api/media_player_proxy/media_player.x?token=abc")

    session.get.assert_called_once_with("http://ha.local:8123/api/media_player_proxy/media_player.x?token=abc&authSig=1")
    client.image.show_image_file.assert_awaited_once()


async def test_show_image_from_a_media_source(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    session = _session()
    play_media = MagicMock(url="/media/local/a.png")

    with (
        patch("custom_components.idotmatrix.media.async_get_clientsession", return_value=session),
        patch(
            "custom_components.idotmatrix.media.media_source.async_resolve_media", AsyncMock(return_value=play_media)
        ) as resolve,
        patch("custom_components.idotmatrix.media.get_url", return_value="http://ha.local:8123"),
        patch("custom_components.idotmatrix.media.async_sign_path", side_effect=lambda hass, path, *a, **kw: path + "?authSig=1"),
    ):
        await _call(hass, "show_image", media_content_id="media-source://media_source/local/a.png")

    resolve.assert_awaited_once_with(hass, "media-source://media_source/local/a.png", None)
    session.get.assert_called_once_with("http://ha.local:8123/media/local/a.png?authSig=1")
    client.image.show_image_file.assert_awaited_once()


@pytest.fixture
def fast_slideshow():
    """The pause between two pictures of a slideshow is only a switch of the event loop."""
    real_sleep = asyncio.sleep

    async def sleep(_delay: float) -> None:
        await real_sleep(0.01)

    with patch("custom_components.idotmatrix.services.asyncio.sleep", sleep):
        yield


async def _wait_for(condition) -> None:
    for _ in range(200):
        if condition():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("timed out")


def _shown(client: MagicMock) -> list[str]:
    return [Path(call.args[0]).name for call in client.image.show_image_file.await_args_list]


async def test_slideshow_cycles_through_a_folder(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock, tmp_path: Path, fast_slideshow: None
) -> None:
    for name in ("b.jpg", "a.png", "notes.txt"):
        (tmp_path / name).write_bytes(b"x")
    hass.config.allowlist_external_dirs = {str(tmp_path)}

    await _call(hass, "start_slideshow", folder=str(tmp_path), interval=10)
    await _wait_for(lambda: len(client.image.show_image_file.await_args_list) >= 3)
    await _call(hass, "stop_slideshow")

    assert _shown(client)[:3] == ["a.png", "b.jpg", "a.png"]
    shown = len(client.image.show_image_file.await_args_list)
    await asyncio.sleep(0.05)
    assert len(client.image.show_image_file.await_args_list) == shown


async def test_slideshow_shows_animated_gifs_as_gifs(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock, tmp_path: Path, fast_slideshow: None
) -> None:
    (tmp_path / "a.gif").write_bytes(b"x")
    hass.config.allowlist_external_dirs = {str(tmp_path)}

    await _call(hass, "start_slideshow", folder=str(tmp_path))
    await _wait_for(lambda: client.gif.upload_gif_file.await_count >= 1)
    await _call(hass, "stop_slideshow")

    client.image.show_image_file.assert_not_awaited()


async def test_slideshow_picks_up_new_pictures(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock, tmp_path: Path, fast_slideshow: None
) -> None:
    (tmp_path / "a.png").write_bytes(b"x")
    hass.config.allowlist_external_dirs = {str(tmp_path)}

    await _call(hass, "start_slideshow", folder=str(tmp_path))
    await _wait_for(lambda: len(_shown(client)) >= 1)
    (tmp_path / "b.png").write_bytes(b"x")
    await _wait_for(lambda: "b.png" in _shown(client))
    await _call(hass, "stop_slideshow")


async def test_slideshow_goes_on_after_a_broken_picture(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock, tmp_path: Path, fast_slideshow: None
) -> None:
    for name in ("a.png", "b.png"):
        (tmp_path / name).write_bytes(b"x")
    hass.config.allowlist_external_dirs = {str(tmp_path)}
    client.image.show_image_file.side_effect = [ValueError("broken"), None, None]

    await _call(hass, "start_slideshow", folder=str(tmp_path))
    await _wait_for(lambda: len(client.image.show_image_file.await_args_list) >= 3)
    await _call(hass, "stop_slideshow")


async def test_showing_something_else_ends_the_slideshow(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock, tmp_path: Path, fast_slideshow: None
) -> None:
    (tmp_path / "a.png").write_bytes(b"x")
    hass.config.allowlist_external_dirs = {str(tmp_path)}
    await _call(hass, "start_slideshow", folder=str(tmp_path))
    await _wait_for(lambda: len(_shown(client)) >= 1)

    await _call(hass, "show_text", text="Hi")

    shown = len(_shown(client))
    await asyncio.sleep(0.1)
    assert len(_shown(client)) == shown


async def test_slideshow_needs_pictures(hass: HomeAssistant, setup: MockConfigEntry, tmp_path: Path) -> None:
    hass.config.allowlist_external_dirs = {str(tmp_path)}

    with pytest.raises(vol.Invalid, match="no pictures"):
        await _call(hass, "start_slideshow", folder=str(tmp_path))


async def test_slideshow_needs_a_folder(hass: HomeAssistant, setup: MockConfigEntry) -> None:
    with pytest.raises(vol.Invalid, match="folder or media_content_id"):
        await _call(hass, "start_slideshow")


async def test_fields_left_empty_in_the_ui_are_ignored(
    hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock, tmp_path: Path
) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"x")
    hass.config.allowlist_external_dirs = {str(tmp_path)}

    await _call(hass, "show_image", path=str(image), url=None, media_content_id=None)
    await _call(hass, "show_image", path=str(image), url="", media_content_id="")

    assert client.image.show_image_file.await_count == 2


async def test_media_picker_value_is_accepted(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    session = _session()
    play_media = MagicMock(url="/media/local/a.png")

    with (
        patch("custom_components.idotmatrix.media.async_get_clientsession", return_value=session),
        patch("custom_components.idotmatrix.media.media_source.async_resolve_media", AsyncMock(return_value=play_media)),
        patch("custom_components.idotmatrix.media.get_url", return_value="http://x"),
        patch("custom_components.idotmatrix.media.async_sign_path", side_effect=lambda hass, path, *a, **kw: path),
    ):
        await _call(
            hass,
            "show_image",
            media_content_id={
                "media_content_id": "media-source://media_source/local/a.png",
                "media_content_type": "image/png",
            },
        )

    session.get.assert_called_once_with("http://x/media/local/a.png")


async def test_download_that_is_not_a_picture(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    session = _session(b"<html>login</html>", content_type="text/html")

    with patch("custom_components.idotmatrix.media.async_get_clientsession", return_value=session):
        with pytest.raises(HomeAssistantError, match="not a picture, but text/html"):
            await _call(hass, "show_image", url="https://example.com/a.png")

    client.image.show_image_file.assert_not_awaited()


async def test_broken_picture_is_reported(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    client.image.show_image_file.side_effect = UnidentifiedImageError("cannot identify image file")
    session = _session()

    with patch("custom_components.idotmatrix.media.async_get_clientsession", return_value=session):
        with pytest.raises(HomeAssistantError, match="cannot identify"):
            await _call(hass, "show_image", url="https://example.com/a.png")

async def test_image_entity_url_is_signed(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    """/api/image_proxy answers 403 without a token or signature."""
    session = _session()

    with (
        patch("custom_components.idotmatrix.media.async_get_clientsession", return_value=session),
        patch("custom_components.idotmatrix.media.get_url", return_value="http://ha.local:8123"),
    ):
        await _call(hass, "show_image", url="/api/image_proxy/image.cover")

    url = session.get.call_args.args[0]
    assert url.startswith("http://ha.local:8123/api/image_proxy/image.cover?authSig=")


async def test_image_entity_url_is_signed(hass: HomeAssistant, setup: MockConfigEntry, client: MagicMock) -> None:
    """/api/image_proxy answers 403 without a token or signature."""
    session = _session()

    with (
        patch("custom_components.idotmatrix.media.async_get_clientsession", return_value=session),
        patch("custom_components.idotmatrix.media.get_url", return_value="http://ha.local:8123"),
    ):
        await _call(hass, "show_image", url="/api/image_proxy/image.cover")

    url = session.get.call_args.args[0]
    assert url.startswith("http://ha.local:8123/api/image_proxy/image.cover?authSig=")
