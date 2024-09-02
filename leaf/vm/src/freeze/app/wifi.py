import asyncio
import logging

import network  # type: ignore

from . import config

SLEEP_MS = 200

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class WifiException(Exception):
    pass


class _Radio:
    def __init__(self):
        self._enabled_count = 0
        self._sta = network.WLAN(network.STA_IF)

    def __aenter__(self):
        if self._enabled_count < 1:
            self._sta.active(True)
            logger.debug("radio ON")
        self._enabled_count += 1

    def __aexit__(self, *args):
        self._enabled_count -= 1
        if self._enabled_count < 1:
            try:
                self._sta.active(False)
            except OSError:
                pass
            logger.debug("radio OFF")

    def scan(self):
        return "\n".join([f"{r[0].decode():40} ch={r[2]:2} rssi={r[3]:3}dbM" for r in self._sta.scan() if r[0]])

    def ssids(self):
        return [r[0].decode() for r in self._sta.scan() if r[0]]


class _Wifi:
    def __init__(self):
        self._enabled_count = 0
        # network.hostname(f"app.{eventbus.config.get('domain', default='leaf.local')}")
        # mDNS works (GL-iNet) but no periods in hostname!
        network.hostname("leaf")

    @property
    def channel(self):
        return radio._sta.config("channel")

    @property
    def ip(self):
        return radio._sta.ifconfig()[0]

    @property
    def ip_bytes(self):
        return bytes([int(x) for x in self.ip.split(".")])

    @property
    def netmask(self):
        return radio._sta.ifconfig()[1]

    @property
    def gateway_ip(self):
        return radio._sta.ifconfig()[2]

    @property
    def dns_ip(self):
        return radio._sta.ifconfig()[3]

    @property
    def hostname(self):
        return network.hostname()

    async def __aenter__(self):
        if self._enabled_count > 0:
            # already connected
            return
        # make sure radio is on
        radio.__aenter__()
        ssids = radio.ssids()
        for w in config.get("wifi"):
            if w["ssid"] in ssids:
                logger.info("Connecting to {}".format(w["ssid"]))
                radio._sta.connect(w["ssid"], w["pwd"])
                # wait for connection
                for _ in range(10_000 // SLEEP_MS):
                    if radio._sta.isconnected():
                        self.ssid = w["ssid"]
                        print()
                        logger.info(f"Connected to {self.ssid} @ {self.ip}")
                        self._enabled_count += 1
                        return
                    await asyncio.sleep_ms(SLEEP_MS)  # type: ignore
                    print(".", end="")
        raise WifiException("Connection failed")

    async def __aexit__(self, *args):
        self._enabled_count -= 1
        if self._enabled_count < 1:
            try:
                radio._sta.disconnect()
            except OSError:
                pass
            radio.__aexit__()
            logger.info("disconnected from Wifi")


radio = _Radio()
wifi = _Wifi()
