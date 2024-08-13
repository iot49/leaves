import re
import time
from typing import Awaitable, Callable, TypeAlias

from .. import bus

# separation characters in uid's
UID_SEP = "."

# Convert CamelCase to snake_case (also apply lower to result)
RE_CAMEL_TO_SNAKE = re.compile(r"(?<!^)(?=[A-Z])")

# MicroPython time starts from 2000-01-01 on some ports
EPOCH_OFFSET = 946684800 if time.gmtime(0)[0] == 2000 else 0

# callback(device: Device, uid: str, **event: Any) -> Awaitable[None] | None
ActionCallback: TypeAlias = Callable[..., Awaitable[None] | None]


def make_uid(device_id: str, entity_id: str, node_id=bus.leaf_id) -> str:
    """Construct entity uid."""
    return f"{node_id}{UID_SEP}{device_id}{UID_SEP}{entity_id}"


"""
Devices are collections of sensors with a state and actuators that respond to actions.

Client communication is via events:

* `!state` - state update
* `?act` - action request
* `?device` - request device information
* `!device` - device information

The `Device` class implements a registry of devices and their entities (states and actuators). It can 
also be used by actual hardware to send out and respond to these events.

Derived classes such as `binary_sensor`, `switch`, `light` provide customized solutions.
"""


def State(id, **attributes):
    """entity with a value, e.g. temperature sensor"""
    return (id, "State", None, attributes)


def Actuator(id, callback: ActionCallback, **attributes):
    """action, e.g. button press"""
    return (id, "Actuator", callback, attributes)


def Transducer(id, callback: ActionCallback, **attributes):
    """modifiable state, e.g. light on/off state or brightness"""
    return (id, "Transducer", callback, attributes)


class Device:
    _registry = {}  # uid -> device
    _callbacks = {}  # uid -> callback

    def __init__(
        self,
        device_id: str,
        *entities,
        **attributes,
    ):
        """
        Initialize a Device object.

        Args:
            device_id (str): The identifier for the device.
            *entities: sensor states, actuators, and transducers.
            **attributes: Keyword arguments representing attributes of the device.

        Raises:
            AssertionError: If the device_id is not a valid identifier.

        Example:
            ```python
            light = Device(
                        'kitchen_light',
                        Transducer("state", callback),
                        Transducer("brightness", callback),
                        name="Kitchen Light")
            ```

        """
        assert device_id.isidentifier(), f"Invalid device_id: {device_id}"
        self.device_id = device_id
        self.attributes = attributes
        self.entities = {}  # uid -> (kind, callback, attributes)
        self._registry[self.uid()] = self
        for entity_id, kind, callback, attributes in entities:
            assert entity_id.isidentifier(), f"Invalid id: {entity_id}"
            entity_uid = self.uid(entity_id=entity_id)
            self.entities[entity_uid] = (kind, callback, attributes)
            if callback is not None:
                self._callbacks[entity_uid] = callback
        bus.emit_sync(
            topic="!device",
            uid=self.uid(),
            domain=self.domain,
            attributes=self.attributes,
            entities=self.info,
            dst="#server",
        )

    @property
    def info(self):
        return {
            uid: {"kind": kind, "attributes": attr}
            for uid, (kind, _, attr) in self.entities.items()
        }

    @property
    def domain(self):
        """Compatibility with Home Assistant"""
        return RE_CAMEL_TO_SNAKE.sub("_", self.__class__.__name__).lower()

    def uid(self, entity_id: str | None = None) -> str:
        """
        Unique identifier for the device or entity.

        Parameters:
            entity_id (str): Optional. Without returns device uid, with returns entity uid.

        Returns:
            str: The unique identifier.

        Example:
            >>> device = Device('device_id')
            >>> device.uid()
            'leaf_id.device_id'
            >>> device.uid('entity_id')
            'leaf_id.device_id.entity_id'
        """
        return (
            f"{bus.leaf_id}{UID_SEP}{self.device_id}"
            if entity_id is None
            else f"{bus.leaf_id}{UID_SEP}{self.device_id}{UID_SEP}{entity_id}"
        )

    async def update(
        self, entity_id, value, timestamp: float = time.time() + EPOCH_OFFSET
    ):
        """Helper to emit a state update events.

        Args:
            entity_id (str): entity_id or uid of the state.
            value: The new value to set for the entity.
            timestamp (float, optional): The timestamp of the update event. Defaults to the current time.

        """
        await bus.emit(
            topic="!state",
            uid=entity_id if "." in entity_id else self.uid(entity_id=entity_id),
            value=value,
            timestamp=timestamp,
        )

    def __str__(self):
        e = ", ".join([f"{kind}({uid})" for uid, (kind, _, _) in self.entities.items()])
        return f"{self.__class__.__name__}({self.device_id}, {e}, {self.attributes})"


@bus.on("?device")
async def device_info(src, **rest):
    """Send info for all registered devices"""
    for uid, device in Device._registry.items():
        await bus.emit(
            topic="!device",
            uid=uid,
            domain=device.domain,
            attributes=device.attributes,
            entities=device.info,
            dst=src,
        )


@bus.on("?act")
async def act(topic, uid, **event):
    """Call callback for entity"""
    device_uid, _ = uid.rsplit(UID_SEP, 1)
    device = Device._registry.get(device_uid)
    if device is None:
        return
    _, callback, _ = device.entities.get(uid) or (None, None, None)
    if callback is not None:
        event.pop("src", None)
        event.pop("dst", None)
        await callback(device, uid, **event)
