import asyncio
import logging

import network  # type: ignore
from . import WifiException

"""MicroPython wifi."""

CONNECT_SLEEP_MS = 200

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Radio:
    def __init__(self):
        self._enabled_count = 0
        self._sta = network.WLAN(network.STA_IF)
        
    async def __aenter__(self):
        if self._enabled_count < 1:
            self._sta.active(True)
        self._enabled_count += 1
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self._enabled_count -= 1
        if self._enabled_count < 1:
            try:
                self._sta.active(False)
            except OSError:
                pass

    def scan(self):
        return "\n".join(
            [
                f"{r[0].decode():40} ch={r[2]:2} rssi={r[3]:3}dbM"
                for r in self._sta.scan()
                if r[0]
            ]
        )

    def ssids(self):
        return [r[0].decode() for r in self._sta.scan() if r[0]]
    
    async def mac_address(self) -> str:
        async with self:
            wlan_mac = self._sta.config("mac")
            return ":".join([f"{b:02x}" for b in wlan_mac])



class Wifi:
    def __init__(self):
        self._enabled_count = 0
        # network.hostname(f"app.{eventbus.config.get('domain', default='leaf.local')}")
        # mDNS works (GL-iNet) but no periods in hostname!
        network.hostname("leaf")

    @property
    def hostname(self):
        import network  # type: ignore

        return network.hostname()

    @property
    def ip(self):
        return radio._sta.ifconfig()[0]  # type: ignore

    async def __aenter__(self):
        global radio
        if self._enabled_count > 0:
            # already connected
            return
        # make sure radio is on
        radio.__aenter__()
        ssids = radio.ssids()  # type: ignore
        from .. import config

        for w in config.get("wifi"):
            if w["ssid"] in ssids:
                logger.info("Connecting to {}".format(w["ssid"]))
                radio._sta.connect(w["ssid"], w["pwd"])  # type: ignore
                # wait for connection
                for _ in range(10_000 // CONNECT_SLEEP_MS):
                    if radio._sta.isconnected():  # type: ignore
                        self.ssid = w["ssid"]
                        print()
                        logger.info(f"Connected to {self.ssid} @ {self.ip}")
                        self._enabled_count += 1
                        return
                    await asyncio.sleep_ms(CONNECT_SLEEP_MS)  # type: ignore
                    print(".", end="")
        raise WifiException("Connection failed")
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self._enabled_count -= 1
        if self._enabled_count < 1:
            try:
                radio._sta.disconnect()  # type: ignore
            except OSError:
                pass
            radio.__aexit__()
            logger.info("disconnected from Wifi")

