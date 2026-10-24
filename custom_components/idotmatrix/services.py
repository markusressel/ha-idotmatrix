"""Actions (services) of the iDotMatrix integration. They are entity services of the light of a display."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
import os
from typing import TYPE_CHECKING, Any

from idotmatrix.modules.effect import EffectStyle
from idotmatrix.modules.text import TextColorMode, TextMode
from idotmatrix.util.device_material import SLOTS
from idotmatrix.util.image_utils import ResizeMode
from idotmatrix.util.overlay import POSITIONS, TextOverlay
import voluptuous as vol

from homeassistant.core import ServiceCall
from homeassistant.helpers import config_validation as cv, entity_platform

from .const import CLOCK_STYLES, MODE_EFFECT, MODE_MUSIC
from .media import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_PATH,
    ATTR_URL,
    Source,
    async_fetch,
    async_list_pictures,
    is_gif,
)

if TYPE_CHECKING:
    from .light import IDotMatrixLight

_LOGGER = logging.getLogger(__name__)

RESIZE_MODES = {"fit": ResizeMode.FIT, "fill": ResizeMode.FILL, "stretch": ResizeMode.STRETCH}
TEXT_MODES = {mode.name.lower(): mode for mode in TextMode}
TEXT_COLOR_MODES = {mode.name.lower(): mode for mode in TextColorMode}
EFFECT_STYLES = {style.name.lower(): style for style in EffectStyle}

RGB = vol.All(vol.ExactSequence((cv.byte, cv.byte, cv.byte)), vol.Coerce(tuple))

def _media_content_id(value: Any) -> str:
    """The media picker of the UI gives an object with the id in it."""
    if isinstance(value, dict):
        value = value.get(ATTR_MEDIA_CONTENT_ID)
    return cv.string(value)


def _without_empty_values(data: dict[str, Any]) -> dict[str, Any]:
    """The UI sends fields that were left empty as None or an empty string."""
    return {key: value for key, value in data.items() if value is not None and value != ""}


OVERLAY_SCHEMA = {
    vol.Optional("overlay_text"): cv.string,
    vol.Optional("overlay_position"): vol.In(POSITIONS),
    vol.Optional("overlay_color"): RGB,
    vol.Optional("overlay_font_size"): vol.All(vol.Coerce(int), vol.Range(min=4, max=32)),
    vol.Optional("overlay_background"): cv.boolean,
}


def _overlay_of(options: dict[str, Any]) -> TextOverlay | None:
    """The text that is drawn on top of the picture, if there is one. What is not set is left to the library."""
    if "overlay_text" not in options:
        return None
    kwargs: dict[str, Any] = {}
    for key in ("position", "color", "font_size"):
        if f"overlay_{key}" in options:
            kwargs[key] = options[f"overlay_{key}"]
    if options.get("overlay_background") is False:
        kwargs["background"] = None
    return TextOverlay(options["overlay_text"], **kwargs)


SOURCE_SCHEMA = {
    vol.Exclusive(ATTR_PATH, "source"): cv.string,
    vol.Exclusive(ATTR_URL, "source"): cv.string,
    vol.Exclusive(ATTR_MEDIA_CONTENT_ID, "source"): _media_content_id,
}


def _require_source(data: dict[str, Any]) -> dict[str, Any]:
    if not any(key in data for key in (ATTR_PATH, ATTR_URL, ATTR_MEDIA_CONTENT_ID)):
        raise vol.Invalid("Either path, url or media_content_id is required")
    return data


def _require_folder(data: dict[str, Any]) -> dict[str, Any]:
    if "folder" not in data and ATTR_MEDIA_CONTENT_ID not in data:
        raise vol.Invalid("Either folder or media_content_id is required")
    return data


def _interrupting(handler: Callable[[IDotMatrixLight, ServiceCall], Awaitable[None]]):
    """Whatever else is shown ends a running slideshow, before it has a chance to upload the next picture."""

    async def _handle(entity: IDotMatrixLight, call: ServiceCall) -> None:
        entity._device.stop_slideshow()
        await handler(entity, call)

    return _handle


async def _async_with_file(
    entity: IDotMatrixLight, data: dict[str, Any], action: Callable[[str], Awaitable[Any]]
) -> None:
    path, temporary = await async_fetch(entity.hass, data)
    try:
        await entity._device.upload(action(path))
    finally:
        if temporary:
            await entity.hass.async_add_executor_job(os.unlink, path)


async def _async_show_picture(
    entity: IDotMatrixLight, source: Source, options: dict[str, Any], *, gif: bool | None = None
) -> None:
    """Shows a picture, or an animated GIF if it is one (or `gif` says so)."""
    client = entity._device.client
    if gif is None:
        gif = is_gif(source)
    if gif:
        await _async_with_file(
            entity,
            source,
            lambda path: client.gif.upload_gif_file(
                path,
                resize_mode=RESIZE_MODES[options["resize_mode"]],
                palletize=options.get("palletize", True),
                background_color=options["background_color"],
                duration_per_frame_in_ms=options.get("duration_per_frame"),
                overlay=_overlay_of(options),
            ),
        )
    else:
        # png is only passed when it was set, otherwise the default of the library applies
        png = {"png": options["png"]} if "png" in options else {}
        await _async_with_file(
            entity,
            source,
            lambda path: client.image.show_image_file(
                path,
                resize_mode=RESIZE_MODES[options["resize_mode"]],
                palletize=options.get("palletize", False),
                background_color=options["background_color"],
                overlay=_overlay_of(options),
                **png,
            ),
        )


def _source_of(data: dict[str, Any]) -> Source:
    return {key: data[key] for key in (ATTR_PATH, ATTR_URL, ATTR_MEDIA_CONTENT_ID) if key in data}


async def _show_image(entity: IDotMatrixLight, call: ServiceCall) -> None:
    await _async_show_picture(entity, _source_of(call.data), call.data, gif=False)
    entity._device.async_content_changed()


async def _show_gif(entity: IDotMatrixLight, call: ServiceCall) -> None:
    await _async_show_picture(entity, _source_of(call.data), call.data, gif=True)
    entity._device.async_content_changed()


async def _start_slideshow(entity: IDotMatrixLight, call: ServiceCall) -> None:
    """Shows the pictures of a folder one after another. The folder is read again every round."""
    data = call.data
    device = entity._device
    hass = entity.hass
    folder = data.get("folder")
    media_content_id = data.get(ATTR_MEDIA_CONTENT_ID)
    interval = data["interval"]
    recursive = data["recursive"]

    pictures = await async_list_pictures(hass, folder, media_content_id, recursive)
    if not pictures:
        raise vol.Invalid("There are no pictures in the folder")

    if data["store"]:
        device.stop_slideshow()
        await _async_store_pictures(entity, pictures, data)
        device.async_content_changed()
        return

    async def _run(pictures: list[Source]) -> None:
        while True:
            if data["shuffle"]:
                random.shuffle(pictures)
            for picture in pictures:
                try:
                    await _async_show_picture(entity, picture, data)
                    device.async_content_changed(keep_slideshow=True)
                except Exception:  # noqa: BLE001 - a broken picture or a lost connection must not end the slideshow
                    _LOGGER.warning("Could not show %s, skipping it", picture, exc_info=True)
                await asyncio.sleep(interval)
            # new pictures may have been added
            pictures = await async_list_pictures(hass, folder, media_content_id, recursive) or pictures

    device.stop_slideshow()
    device.slideshow = hass.async_create_background_task(_run(pictures), f"idotmatrix slideshow {device.address}")
    device.async_content_changed(keep_slideshow=True)


async def _async_store_pictures(entity: IDotMatrixLight, pictures: list[Source], data: dict[str, Any]) -> None:
    """
    Stores the pictures in the slots of the display, which then cycles through them by itself, without any uploads
    that interrupt the animation. As many pictures as there are slots are stored, the folder is not read again.
    """
    slots = sorted(data.get("slots", SLOTS))
    if data["shuffle"]:
        pictures = random.sample(pictures, len(pictures))
    if len(pictures) > len(slots):
        _LOGGER.info("Storing %d of the %d pictures, there are only %d slots", len(slots), len(pictures), len(slots))
        pictures = pictures[: len(slots)]

    files: list[tuple[str, bool]] = []
    try:
        for picture in pictures:
            files.append(await async_fetch(entity.hass, picture))
        await entity._device.upload(
            entity._device.client.materials.store(
                [path for path, _ in files],
                slots=slots,
                display_time=data["interval"],
                resize_mode=RESIZE_MODES[data["resize_mode"]],
                palletize=data.get("palletize"),
                background_color=data["background_color"],
                overlay=_overlay_of(data),
            )
        )
    finally:
        for path, temporary in files:
            if temporary:
                await entity.hass.async_add_executor_job(os.unlink, path)


async def _stop_slideshow(entity: IDotMatrixLight, call: ServiceCall) -> None:
    entity._device.stop_slideshow()
    entity._device.async_state_changed()


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
        _without_empty_values,
        cv.make_entity_service_schema(
            {
                **SOURCE_SCHEMA,
                vol.Optional("resize_mode", default="fit"): vol.In(RESIZE_MODES),
                vol.Optional("palletize", default=False): cv.boolean,
                vol.Optional("background_color", default=(0, 0, 0)): RGB,
                vol.Optional("png"): cv.boolean,
                **OVERLAY_SCHEMA,
            }
        ),
        _require_source,
    )
    gif_schema = vol.All(
        _without_empty_values,
        cv.make_entity_service_schema(
            {
                **SOURCE_SCHEMA,
                vol.Optional("resize_mode", default="fit"): vol.In(RESIZE_MODES),
                vol.Optional("palletize", default=True): cv.boolean,
                vol.Optional("background_color", default=(0, 0, 0)): RGB,
                vol.Optional("duration_per_frame"): vol.All(vol.Coerce(int), vol.Range(min=10, max=5000)),
                **OVERLAY_SCHEMA,
            }
        ),
        _require_source,
    )

    slideshow_schema = vol.All(
        _without_empty_values,
        cv.make_entity_service_schema(
            {
                vol.Exclusive("folder", "folder"): cv.string,
                vol.Exclusive(ATTR_MEDIA_CONTENT_ID, "folder"): _media_content_id,
                vol.Optional("interval", default=30): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                vol.Optional("recursive", default=False): cv.boolean,
                vol.Optional("store", default=False): cv.boolean,
                vol.Optional("slots"): vol.All(
                    cv.ensure_list,
                    [vol.All(vol.Coerce(int), vol.Range(min=0, max=SLOTS[-1]))],
                    vol.Length(min=1),
                    vol.Unique(),
                ),
                vol.Optional("shuffle", default=False): cv.boolean,
                vol.Optional("resize_mode", default="fit"): vol.In(RESIZE_MODES),
                vol.Optional("background_color", default=(0, 0, 0)): RGB,
                **OVERLAY_SCHEMA,
            }
        ),
        _require_folder,
    )

    platform.async_register_entity_service("show_image", image_schema, _interrupting(_show_image))
    platform.async_register_entity_service("start_slideshow", slideshow_schema, _start_slideshow)
    platform.async_register_entity_service("stop_slideshow", {}, _stop_slideshow)
    platform.async_register_entity_service("show_gif", gif_schema, _interrupting(_show_gif))
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
        _interrupting(_show_text),
    )
    platform.async_register_entity_service(
        "show_clock",
        {
            vol.Optional("style"): vol.In(CLOCK_STYLES),
            vol.Optional("show_date"): cv.boolean,
            vol.Optional("hour24"): cv.boolean,
            vol.Optional("color"): RGB,
        },
        _interrupting(_show_clock),
    )
    platform.async_register_entity_service(
        "set_effect",
        {
            vol.Required("style"): vol.In(EFFECT_STYLES),
            vol.Required("colors"): vol.All(cv.ensure_list, [RGB], vol.Length(min=2, max=7)),
        },
        _interrupting(_set_effect),
    )
    platform.async_register_entity_service(
        "countdown",
        {
            vol.Required("action"): vol.In(["start", "pause", "restart", "stop"]),
            vol.Optional("minutes", default=1): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
            vol.Optional("seconds", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
        },
        _interrupting(_countdown),
    )
    platform.async_register_entity_service(
        "chronograph",
        {vol.Required("action"): vol.In(["start", "pause", "resume", "reset"])},
        _interrupting(_chronograph),
    )
    platform.async_register_entity_service(
        "scoreboard",
        {
            vol.Required("score_1"): vol.All(vol.Coerce(int), vol.Range(min=0, max=999)),
            vol.Required("score_2"): vol.All(vol.Coerce(int), vol.Range(min=0, max=999)),
        },
        _interrupting(_scoreboard),
    )
    platform.async_register_entity_service(
        "set_pixels",
        {
            vol.Required("color"): RGB,
            vol.Required("pixels"): vol.All(
                cv.ensure_list, [vol.ExactSequence((cv.positive_int, cv.positive_int))], vol.Length(min=1)
            ),
        },
        _interrupting(_set_pixels),
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
        _interrupting(_music_sync),
    )
