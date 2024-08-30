# ruff: noqa: F401
# ruff: noqa: E402

from .ev_bus import Bus

bus = Bus()

from .devices import Actuator, Device, State, Transducer, make_uid
from .devices.binary_sensor import BinarySensor
from .devices.light import Light
from .devices.sensor import Sensor
from .devices.switch import Switch
from .listeners.config import Config
from .listeners.log import Log
from .listeners.sensor_state import SensorState


@bus.on("?echo")
async def echo(topic, src, dst, data=None):
    """All leaves respond to ?echo events."""
    global bus
    if src == bus.LEAF_ID:
        return
    await bus.emit(topic="!echo", dst=src, data=data)
