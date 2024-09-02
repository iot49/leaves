import logging
from struct import unpack

from ucryptolib import aes  # type: ignore

from eventbus.event import State

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Victron models
_VICTRON_MODEL = {
    0x01: "Solar_Charger",
    0x02: "Battery_Monitor",
    0x03: "Inverter",
    0x04: "DC/DC_converter",
    0x0C: "VE_Bus",
}

# Victron device state codes
_VICTRON_STATE = {0: "off", 1: "low power", 2: "error", 3: "bulk", 4: "absorption", 5: "float"}


def pad(data):
    n = 16 - len(data)
    return data + bytes([n]) * n


async def update_charger(dev, info, decrypted):
    # Solar charger
    entities = info.get("entities")
    if entities is None:
        dev_id = info.get("id")
        info["entities"] = entities = (
            State(f"{dev_id}.rssi"),
            State(f"{dev_id}.state"),
            State(f"{dev_id}.voltage"),
            State(f"{dev_id}.current"),
            State(f"{dev_id}.energy"),
            State(f"{dev_id}.power"),
        )
    rssi, state, voltage, current, energy, power = entities
    state, error, v, i, y, p, ext = unpack("<BBhhHHH", decrypted)
    await rssi.update(dev.rssi)
    await state.update(_VICTRON_STATE.get(state, str(state)))
    await voltage.update(v / 100)
    await current.update(i / 10)
    await energy.update(y * 10.0)
    await power.update(p)


async def update_soc(dev, info, decrypted):
    # Battery SOC monitor
    entities = info.get("entities")
    if entities is None:
        dev_id = info.get("id")
        info["entities"] = entities = (
            State(f"{dev_id}.rssi"),
            State(f"{dev_id}.time_to_go"),
            State(f"{dev_id}.voltage"),
            State(f"{dev_id}.current"),
            State(f"{dev_id}.energy"),
            State(f"{dev_id}.soc"),
            State(f"{dev_id}.temperature"),
        )
    ttg, v, alarm, aux, i2, i0, consumed, soc = unpack("<HHHHHbHH", decrypted)
    # float("inf") produces invalid json
    # ttg = float("inf") if ttg == 0xFFFF else ttg / 60
    ttg = "inf" if ttg == 0xFFFF else ttg / 60
    c = i0 << 16 | i2
    i = (c >> 2) / 1000
    T = aux / 100 - 273.15 if c & 0b11 == 2 else None
    soc = ((soc & 0x3FFF) >> 4) / 10
    rssi, time_to_go, voltage, current, energy, soc_, temperature = entities
    await rssi.update(dev.rssi)
    await time_to_go.update(ttg)
    await voltage.update(v / 100)
    await current.update(i)
    await energy.update(consumed / 10)
    await soc_.update(soc)
    if T is not None:
        await temperature.update(T)


async def parser(dev, manufacturer, data, info):
    if manufacturer != 0x02E1 or len(data) < 1 or data[0] != 0x10:
        return
    _, model_id, _model, iv, key0 = unpack("<HHBHB", data)
    model = _VICTRON_MODEL.get(_model)
    if _model > 2 or model is None:
        logger.info(f"unsupported Victron model {_model} {model_id} @ {dev.device.addr_hex()}")
        return
    if info is None:
        logger.info(f"DISCOVER: Victron {model} @ {dev.device.addr_hex()}")
        return

    dev_id = info.get("id")
    if dev_id is None:
        logger.error(f"Victron {model} @ {dev.device.addr_hex()}: missing id")
        return

    try:
        key = bytes.fromhex(info.get("key"))
    except (TypeError, ValueError) as e:
        logger.error(f"Victron key missing or invalid key for {dev_id}: {e}")
        return

    if key[0] != key0:
        logger.error(f"Victron key mismatch {key[0]:02x} != {key0:02x} for {dev_id}")
        return

    try:
        cipher = aes(key, 6, iv.to_bytes(16, "little"))
    except TypeError as e:
        logger.error(f"Victron cipher {model} {dev_id}: {e}")
        return

    try:
        decrypted = cipher.decrypt(pad(data[8:]))  # type: ignore
    except ValueError as e:
        logger.error(f"Victron decrypt {model} {dev_id}: {e}")
        return

    if _model == 0x1:
        await update_charger(dev, info, decrypted)
    elif _model == 0x2:
        await update_soc(dev, info, decrypted)
