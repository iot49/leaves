# ruff: noqa: F401
# ruff: noqa: E402


"""
global:
    bus: Bus
    Note: set bus.LEAF_ID before use!
"""

from .ev_bus import Bus

bus = Bus()

from .devices import Actuator, Device, State, Transducer, make_uid
from .devices.binary_sensor import BinarySensor
from .devices.light import Light
from .devices.sensor import Sensor
from .devices.switch import Switch


@bus.on("?echo")
async def echo(topic, src, dst, data=None):
    """All leaves respond to ?echo events."""
    global bus
    if src == bus.LEAF_ID:
        return
    await bus.emit(topic="!echo", dst=src, data=data)
