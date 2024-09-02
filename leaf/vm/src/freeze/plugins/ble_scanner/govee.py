import logging
from struct import unpack

from eventbus.event import State

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def parser(dev, manufacturer, data, info):
    if dev.name() is None or manufacturer != 0xEC88:
        return
    _, temp, humi, batt = unpack("<BhHB", data)
    if info is None:
        logger.info(f"DISCOVER: Govee TH Sensor {temp/100} C @ {dev.device.addr_hex()}")
    else:
        entities = info.get("entities")
        if entities is None:
            dev_id = info.get("id")
            if dev_id is None:
                logger.error(f"Govee @ {dev.device.addr_hex()}: missing id")
                return
            info["entities"] = entities = (
                State(f"{dev_id}.temperature"),
                State(f"{dev_id}.humidity"),
                State(f"{dev_id}.battery_level"),
                State(f"{dev_id}.rssi"),
            )
        T, H, bat, rssi = entities
        await T.update(temp / 100)
        await H.update(humi / 100)
        await bat.update(batt)
        await rssi.update(dev.rssi)
