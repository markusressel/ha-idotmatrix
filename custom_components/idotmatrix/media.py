"""Getting pictures to show: files, urls and media sources of Home Assistant."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import MediaClass
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url

from .const import DOMAIN

ATTR_PATH = "path"
ATTR_URL = "url"
ATTR_MEDIA_CONTENT_ID = "media_content_id"

_LOGGER = logging.getLogger(__name__)

MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}

# a source of a picture, as a dict with one of the keys above
Source = dict[str, str]


def is_gif(source: Source) -> bool:
    return any(value.lower().split("?")[0].endswith(".gif") for value in source.values())


def _error(key: str, **placeholders: str) -> HomeAssistantError:
    return HomeAssistantError(translation_domain=DOMAIN, translation_key=key, translation_placeholders=placeholders)


async def async_fetch(hass: HomeAssistant, source: Source) -> tuple[str, bool]:
    """
    Returns the path of the file to show, and whether it is a temporary file that has to be deleted.
    Local files must be in a folder that is allowed by `allowlist_external_dirs`.
    """
    if ATTR_PATH in source:
        path = source[ATTR_PATH]
        if not hass.config.is_allowed_path(path):
            raise _error("path_not_allowed", path=path)
        if not await hass.async_add_executor_job(os.path.isfile, path):
            raise _error("file_not_found", path=path)
        return path, False

    if ATTR_MEDIA_CONTENT_ID in source:
        try:
            play_media = await media_source.async_resolve_media(hass, source[ATTR_MEDIA_CONTENT_ID], None)
        except media_source.MediaSourceError as ex:
            raise _error("download_failed", url=source[ATTR_MEDIA_CONTENT_ID], error=str(ex)) from ex
        url = async_process_play_media_url(hass, play_media.url)
    else:
        url = source[ATTR_URL]
        if url.startswith("/"):
            # f.e. the cover of a media player, which is served by Home Assistant itself
            url = get_url(hass) + url

    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(30), session.get(url) as response:
            response.raise_for_status()
            content_type = response.content_type
            content = await response.content.read(MAX_DOWNLOAD_BYTES + 1)
    except (TimeoutError, Exception) as ex:
        raise _error("download_failed", url=url, error=str(ex) or type(ex).__name__) from ex
    if len(content) > MAX_DOWNLOAD_BYTES:
        raise _error("download_too_large")
    if not content_type.startswith("image/") and content_type != "application/octet-stream":
        # f.e. a login page or an error message, which would only fail later with a hard to understand error
        _LOGGER.warning("%s answered with %s, starting with %r", url, content_type, content[:200])
        raise _error("not_an_image", url=url, content_type=content_type)

    def _write() -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".img") as file:
            file.write(content)
            return file.name

    return await hass.async_add_executor_job(_write), True


async def async_list_pictures(hass: HomeAssistant, folder: str | None, media_content_id: str | None) -> list[Source]:
    """The pictures in a folder of the file system, or in a folder of a media source. Not recursive."""
    if folder is not None:
        if not hass.config.is_allowed_path(folder):
            raise _error("path_not_allowed", path=folder)

        def _list() -> list[Source]:
            try:
                names = sorted(os.listdir(folder))
            except OSError:
                return []
            return [
                {ATTR_PATH: os.path.join(folder, name)}
                for name in names
                if os.path.splitext(name)[1].lower() in IMAGE_EXTENSIONS
            ]

        return await hass.async_add_executor_job(_list)

    try:
        browsed = await media_source.async_browse_media(hass, media_content_id)
    except media_source.MediaSourceError as ex:
        raise _error("download_failed", url=str(media_content_id), error=str(ex)) from ex
    return [
        {ATTR_MEDIA_CONTENT_ID: child.media_content_id}
        for child in browsed.children or []
        if child.media_class == MediaClass.IMAGE and child.can_play
    ]
