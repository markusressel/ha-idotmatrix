"""Actions (services) of the iDotMatrix integration. They are entity services of the light of a display."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import os
import tempfile
from typing import TYPE_CHECKING, Any

from idotmatrix.modules.effect import EffectStyle
from idotmatrix.modules.text import TextColorMode, TextMode
from idotmatrix.util.image_utils import ResizeMode
import voluptuous as vol

from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLOCK_STYLES, DOMAIN, MODE_EFFECT, MODE_MUSIC

if TYPE_CHECKING:
    from .light import IDotMatrixLight

ATTR_PATH = "path"
ATTR_URL = "url"

RESIZE_MODES = {"fit": ResizeMode.FIT, "fill": ResizeMode.FILL, "stretch": ResizeMode.STRETCH}
TEXT_MODES = {mode.name.lower(): mode for mode in TextMode}
TEXT_COLOR_MODES = {mode.name.lower(): mode for mode in TextColorMode}
EFFECT_STYLES = {style.name.lower(): style for style in EffectStyle}

RGB = vol.All(vol.ExactSequence((cv.byte, cv.byte, cv.byte)), vol.Coerce(tuple))
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024

SOURCE_SCHEMA = {
    vol.Exclusive(ATTR_PATH, "source"): cv.string,
    vol.Exclusive(ATTR_URL, "source"): cv.url,
}


def _require_source(data: dict[str, Any]) -> dict[str, Any]:
    if ATTR_PATH not in data and ATTR_URL not in data:
        raise vol.Invalid("Either path or url is required")
    return data


async def _async_fetch(entity: IDotMatrixLight, data: dict[str, Any]) -> tuple[str, bool]:
    """
    Returns the path of the file to show, and whether it is a temporary file that has to be deleted.
    Local files must be in a folder that is allowed by `allowlist_external_dirs`.
    """
    hass = entity.hass
    if ATTR_PATH in data:
        path = data[ATTR_PATH]
        if not hass.config.is_allowed_path(path):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="path_not_allowed", translation_placeholders={"path": path}
            )
        if not await hass.async_add_executor_job(os.path.isfile, path):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="file_not_found", translation_placeholders={"path": path}
            )
        return path, False

    url = data[ATTR_URL]
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(30), session.get(url) as response:
            response.raise_for_status()
            content = await response.content.read(MAX_DOWNLOAD_BYTES + 1)
    except (TimeoutError, Exception) as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="download_failed",
            translation_placeholders={"url": url, "error": str(ex) or type(ex).__name__},
        ) from ex
    if len(content) > MAX_DOWNLOAD_BYTES:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="download_too_large")

    def _write() -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".img") as file:
            file.write(content)
            return file.name

    return await hass.async_add_executor_job(_write), True


async def _async_with_file(
    entity: IDotMatrixLight, data: dict[str, Any], action: Callable[[str], Awaitable[Any]]
) -> None:
    path, temporary = await _async_fetch(entity, data)
    try:
        await entity._device.call(action(path))
    finally:
        if temporary:
            await entity.hass.async_add_executor_job(os.unlink, path)


async def _show_image(entity: IDotMatrixLight, call: ServiceCall) -> None:
    data = call.data
    await _async_with_file(
        entity,
        data,
        lambda path: entity._device.client.image.show_image_file(
            path,
            resize_mode=RESIZE_MODES[data["resize_mode"]],
            palletize=data["palletize"],
            background_color=data["background_color"],
            png=data["png"],
        ),
    )
    entity._device.async_content_changed()


async def _show_gif(entity: IDotMatrixLight, call: ServiceCall) -> None:
    data = call.data
    await _async_with_file(
        entity,
        data,
        lambda path: entity._device.client.gif.upload_gif_file(
            path,
            resize_mode=RESIZE_MODES[data["resize_mode"]],
            palletize=data["palletize"],
            background_color=data["background_color"],
            duration_per_frame_in_ms=data.get("duration_per_frame"),
        ),
    )
    entity._device.async_content_changed()


async def _show_text(entity: IDotMatrixLight, call: ServiceCall) -> None:
    data = call.data
    await entity._device.call(
        entity._device.client.text.show_text(
            data["text"],
            font_size=data["font_size"],
            text_mode=TEXT_MODES[data["mode"]],
            speed=data["speed"],
            text_color_mode=TEXT_COLOR_MODES[data["color_mode"]],
            text_color=data.get("color"),
            text_bg_color=data.get("background_color"),
        )
    )
    entity._device.async_content_changed()


async def _show_clock(entity: IDotMatrixLight, call: ServiceCall) -> None:
    """Shows the clock. What is not given is taken from the settings of the clock entities."""
    state = entity._device.state
    for name in ("style", "show_date", "hour24", "color"):
        if name in call.data:
            setattr(state, f"clock_{name}", call.data[name])
    await entity._device.async_show_clock()


async def _set_effect(entity: IDotMatrixLight, call: ServiceCall) -> None:
    data = call.data
    await entity._device.call(entity._device.client.effect.show(EFFECT_STYLES[data["style"]], data["colors"]))
    entity._device.state.effect = None
    entity._device.async_content_changed(MODE_EFFECT)


async def _countdown(entity: IDotMatrixLight, call: ServiceCall) -> None:
    data = call.data
    countdown = entity._device.client.countdown
    action = data["action"]
    if action == "start":
        await entity._device.call(countdown.start(data["minutes"], data["seconds"]))
    else:
        await entity._device.call({"pause": countdown.pause, "restart": countdown.restart, "stop": countdown.stop}[action]())
    entity._device.async_content_changed()


async def _chronograph(entity: IDotMatrixLight, call: ServiceCall) -> None:
    chronograph = entity._device.client.chronograph
    method = {
        "start": chronograph.start_from_zero,
        "pause": chronograph.pause,
        "resume": chronograph.resume,
        "reset": chronograph.reset,
    }[call.data["action"]]
    await entity._device.call(method())
    entity._device.async_content_changed()


async def _scoreboard(entity: IDotMatrixLight, call: ServiceCall) -> None:
    await entity._device.call(entity._device.client.scoreboard.show(call.data["score_1"], call.data["score_2"]))
    entity._device.async_content_changed()


async def _set_pixels(entity: IDotMatrixLight, call: ServiceCall) -> None:
    pixels = [tuple(pixel) for pixel in call.data["pixels"]]
    await entity._device.call(entity._device.client.graffiti.set_pixels(call.data["color"], pixels))
    entity._device.async_content_changed()


async def _set_eco(entity: IDotMatrixLight, call: ServiceCall) -> None:
    data = call.data
    state = entity._device.state
    state.night_enabled = data["enabled"]
    state.night_start = data["start_time"]
    state.night_end = data["end_time"]
    state.night_brightness = data["brightness"]
    await entity._device.async_apply_night_mode()


async def _music_sync(entity: IDotMatrixLight, call: ServiceCall) -> None:
    await entity._device.call(
        entity._device.client.music_sync.set_mic_type(call.data["scene"], sensitivity=call.data["sensitivity"])
    )
    entity._device.state.music_scene = str(call.data["scene"])
    entity._device.async_content_changed(MODE_MUSIC)


def async_setup_services() -> None:
    """Register the actions on the light platform, which every display has."""
    platform = entity_platform.async_get_current_platform()

    image_schema = vol.All(
        cv.make_entity_service_schema(
            {
                **SOURCE_SCHEMA,
                vol.Optional("resize_mode", default="fit"): vol.In(RESIZE_MODES),
                vol.Optional("palletize", default=False): cv.boolean,
                vol.Optional("background_color", default=(0, 0, 0)): RGB,
                vol.Optional("png", default=False): cv.boolean,
            }
        ),
        _require_source,
    )
    gif_schema = vol.All(
        cv.make_entity_service_schema(
            {
                **SOURCE_SCHEMA,
                vol.Optional("resize_mode", default="fit"): vol.In(RESIZE_MODES),
                vol.Optional("palletize", default=True): cv.boolean,
                vol.Optional("background_color", default=(0, 0, 0)): RGB,
                vol.Optional("duration_per_frame"): vol.All(vol.Coerce(int), vol.Range(min=10, max=5000)),
            }
        ),
        _require_source,
    )

    platform.async_register_entity_service("show_image", image_schema, _show_image)
    platform.async_register_entity_service("show_gif", gif_schema, _show_gif)
    platform.async_register_entity_service(
        "show_text",
        {
            vol.Required("text"): cv.string,
            vol.Optional("font_size", default=16): vol.All(vol.Coerce(int), vol.Range(min=4, max=64)),
            vol.Optional("mode", default="marquee"): vol.In(TEXT_MODES),
            vol.Optional("speed", default=95): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional("color_mode", default="white"): vol.In(TEXT_COLOR_MODES),
            vol.Optional("color"): RGB,
            vol.Optional("background_color"): RGB,
        },
        _show_text,
    )
    platform.async_register_entity_service(
        "show_clock",
        {
            vol.Optional("style"): vol.In(CLOCK_STYLES),
            vol.Optional("show_date"): cv.boolean,
            vol.Optional("hour24"): cv.boolean,
            vol.Optional("color"): RGB,
        },
        _show_clock,
    )
    platform.async_register_entity_service(
        "set_effect",
        {
            vol.Required("style"): vol.In(EFFECT_STYLES),
            vol.Required("colors"): vol.All(cv.ensure_list, [RGB], vol.Length(min=2, max=7)),
        },
        _set_effect,
    )
    platform.async_register_entity_service(
        "countdown",
        {
            vol.Required("action"): vol.In(["start", "pause", "restart", "stop"]),
            vol.Optional("minutes", default=1): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
            vol.Optional("seconds", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
        },
        _countdown,
    )
    platform.async_register_entity_service(
        "chronograph",
        {vol.Required("action"): vol.In(["start", "pause", "resume", "reset"])},
        _chronograph,
    )
    platform.async_register_entity_service(
        "scoreboard",
        {
            vol.Required("score_1"): vol.All(vol.Coerce(int), vol.Range(min=0, max=999)),
            vol.Required("score_2"): vol.All(vol.Coerce(int), vol.Range(min=0, max=999)),
        },
        _scoreboard,
    )
    platform.async_register_entity_service(
        "set_pixels",
        {
            vol.Required("color"): RGB,
            vol.Required("pixels"): vol.All(
                cv.ensure_list, [vol.ExactSequence((cv.positive_int, cv.positive_int))], vol.Length(min=1)
            ),
        },
        _set_pixels,
    )
    platform.async_register_entity_service(
        "set_eco",
        {
            vol.Optional("enabled", default=True): cv.boolean,
            vol.Required("start_time"): cv.time,
            vol.Required("end_time"): cv.time,
            vol.Optional("brightness", default=10): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        },
        _set_eco,
    )
    platform.async_register_entity_service(
        "music_sync",
        {
            vol.Optional("scene", default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
            vol.Optional("sensitivity", default=50): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        },
        _music_sync,
    )
