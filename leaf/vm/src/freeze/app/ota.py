import logging

import version  # type: ignore
from ota32 import OTA as OTA32  # type: ignore

from app import wifi  # type: ignore
from eventbus import event_type, eventbus

from . import DOMAIN

logger = logging.getLogger(__name__)


async def progress_cb(bytes_written):
    await eventbus.emit({"type": event_type.OTA_PROGRESS, "bytes_written": bytes_written})


async def ota(tag=version.TAG, sha=None, dry_run=False):
    if version.TAG == tag:
        logger.debug(f"already on release {tag} - no OTA needed")
        await eventbus.emit({"type": event_type.OTA_COMPLETE, "tag": tag})
        return

    async with wifi:
        try:
            ota = OTA32(progress_cb, dry_run=dry_run)
            # url = f"https://github.com/{version.GITHUB_REPOSITORY}/releases/download/{tag}/{version.BOARD}-firmware.bin"
            url = f"http://{DOMAIN}/api/vm/{tag}/{version.BOARD}/firmware.bin"
            await ota.ota(url, sha)
            await eventbus.emit({"type": event_type.OTA_COMPLETE, "tag": tag})
        except OSError as e:
            logger.debug(f"OTA failed: {e}")
            await eventbus.emit({"type": event_type.OTA_FAILED, "error": str(e)})


@eventbus.on(event_type.OTA)
async def ota_event(param, **event):
    if event.get("type") == event_type.OTA:
        try:
            await ota(**param)
        except TypeError as e:
            await eventbus.emit({"type": event_type.OTA_FAILED, "incorrect param": str(e)})
