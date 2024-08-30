import logging

import aioble  # type: ignore

from . import govee, victron

logger = logging.getLogger(__name__)


async def init(duration_ms: int = 1000, active=True, devices={}) -> None:
    parsers = [govee.parser, victron.parser]
    while True:
        async with aioble.scan(duration_ms=duration_ms, active=active) as scanner:
            async for dev in scanner:
                addr = dev.device.addr_hex()
                info = devices.get(addr)
                for manufacturer, data in dev.manufacturer():
                    logger.debug(f"{dev.name() or '':25} {addr} manuf=0x{manufacturer:04x} data={data}")
                    for parser in parsers:
                        await parser(dev, manufacturer, data, info)
