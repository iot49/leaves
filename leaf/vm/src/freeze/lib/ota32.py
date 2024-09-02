# OTA manages a MicroPython firmware update over-the-air.
# It assumes that there are two "app" partitions in the partition table and updates the one
# that is not currently running. When the update is complete, it sets the new partition as
# the next one to boot. If it does not reset/restart, use machine.reset() explicitly.

# https://github.com/tve/mqboard/blob/master/mqrepl/mqrepl.py#L23-L71

import binascii
import gc
import hashlib
import logging
import sys
from urllib.urequest import urlopen

import machine  # type: ignore
from esp32 import Partition  # type: ignore

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

BLOCKLEN = 4096  # data bytes in a flash block


class OTA:
    # constructor, follow by calling ota(...)
    #     :progress_cb: async callback reporting number of bytes flashed, -1 when done
    def __init__(self, progress_cb, dry_run=True):
        self._progress_cb = progress_cb
        self._dry_run = dry_run
        # the partition we are writing to
        self.part = Partition(Partition.RUNNING).get_next_update()

        # sha of the new app, computed in _app_data
        self.sha = hashlib.sha256()

        # keeping track (_app_data)
        self.block = 0
        self.buf = bytearray(BLOCKLEN)
        self.buflen = 0  # length of current content of self.buf
        if sys.platform != "esp32":
            raise ValueError("N/A")

    # load app into the next partition and set it as the next one to boot upon restart
    #     :param:  url
    #     :sha256: sha256
    async def ota(self, url, sha256):
        logger.debug(f"OTA flash {url}")
        buffer = bytearray(BLOCKLEN)
        mv = memoryview(buffer)
        sock = urlopen(url)
        size = 0
        try:
            while True:
                sz = sock.readinto(buffer)
                if not sz:
                    break
                await self._app_data(mv[0:sz])
                size += sz
                await self._progress_cb(size)
                logger.debug(f"wrote {size} bytes")
            await self._finish(sha256)
        finally:
            sock.close()
            buffer = None
            gc.collect()

    # accept chunks of the app and write to self.part
    async def _app_data(self, data, last=False):
        global BLOCKLEN
        data_len = len(data)
        self.sha.update(data)
        if self.buflen + data_len >= BLOCKLEN:
            # got a full block, assemble it and write to flash
            cpylen = BLOCKLEN - self.buflen
            self.buf[self.buflen : BLOCKLEN] = data[:cpylen]
            assert len(self.buf) == BLOCKLEN
            if not self._dry_run:
                self.part.writeblocks(self.block, self.buf)
            self.block += 1
            data_len -= cpylen
            if data_len > 0:
                self.buf[:data_len] = data[cpylen:]
            self.buflen = data_len
        else:
            self.buf[self.buflen : self.buflen + data_len] = data
            self.buflen += data_len
            if last and self.buflen > 0:
                for i in range(BLOCKLEN - self.buflen):
                    self.buf[self.buflen + i] = 0xFF  # erased flash is ff
                if not self._dry_run:
                    self.part.writeblocks(self.block, self.buf)
                assert len(self.buf) == BLOCKLEN

    # finish writing the app to the partition and check the sha
    async def _finish(self, check_sha):
        # flush the app buffer and complete the write
        await self._app_data(b"", last=False)
        await self._app_data(b"", last=True)
        del self.buf
        # check the sha
        if check_sha is not None:
            calc_sha = binascii.hexlify(self.sha.digest())
            check_sha = check_sha.encode()
            if calc_sha != check_sha:
                raise ValueError(f"SHA mismatch\n    calc:  {calc_sha}\n    check: {check_sha}")
        logger.debug("OTA: flashed new firmware")
        logger.debug("call `Partition.mark_app_valid_cancel_rollback()`.")
        if not self._dry_run:
            self.part.set_boot()
            machine.reset()
