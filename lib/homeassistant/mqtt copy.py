# MQTT bridge for Entity to Home Assistant


import asyncio
import json
import re

from eventbus import bus
from eventbus.devices import Device

# Convert CamelCase to snake_case (also apply lower to result)
RE_CAMEL_TO_SNAKE = re.compile(r"(?<!^)(?=[A-Z])")


class MQTT:
    def __init__(self, client):
        self.client = client

    async def new_device_listener(self, device):
        # send discovery message whenever a new device is created
        print("DISCOVER", device)
        for msg in device.discovery_messages():
            uid = msg["unique_id"]
            await self.client.publish(
                f"homeassistant/{device.domain}/{uid}/config",
                json.dumps(msg),
            )

    async def action_listener(self):
        # forward action events from mqtt to eventbus
        await self.client.subscribe("leaf/act/#")
        async for msg in self.client.messages:
            uid = str(msg.topic).split("/")[-1]
            print(
                "EMIT",
                {
                    "topic": "!action",
                    "uid": uid,
                    "state": msg.payload,
                },
            )
            await bus.emit({"topic": "!action", "uid": uid, "state": msg.payload})

    async def run(self):
        Device.subscribe(self.new_device_listener)
        asyncio.create_task(self.action_listener())

        @bus.on("!state")
        async def update_state(uid, value, **rest):
            # forward state updates from eventbus to mqtt
            print("MQTT PUB", f"leaf/state/{uid}", value)
            await self.client.publish(f"leaf/state/{uid}", value)

    def discovery_message(self) -> dict[str, object]:
        """
        Generate the discovery message for the item.

        Returns:
            dict[str, object]: The discovery message.

        """
        msg = self.attributes.copy()
        msg["unique_id"] = self.uid
        msg["object_id"] = self.uid
        msg["state_topic"] = f"leaf/state/{self.uid}"
        if "name" not in msg:
            msg["name"] = self.id.capitalize()
        # device info
        dev = self.device.attributes.copy()
        dev["identifiers"] = [f"{bus.leaf_id}-{self.device.id}"]
        if "name" not in dev:
            dev["name"] = self.device.id.capitalize()
        msg["device"] = dev
        return msg

    @property
    def domain(self) -> str:
        """
        Get the Home Assistant domain of the device (e.g. sensor, light, switch, ...)

        Returns:
            str: The domain of the device. Defaults to the snake_case of the class name.

        """
        return RE_CAMEL_TO_SNAKE.sub("_", self.__class__.__name__).lower()

    def state_discovery_message(self) -> dict[str, object]:
        msg = super().discovery_message()
        msg["state_topic"] = f"leaf/state/{self.uid}"
        return msg

    def action_discovery_message(self) -> dict[str, object]:
        """
        Generate the discovery message for the action.

        Returns:
            dict[str, object]: The discovery message.

        """
        msg = super().discovery_message()
        msg["command_topic"] = f"leaf/act/{self.uid}"
        return msg

    # switch

    def discovery_messages(self) -> list[dict[str, object]]:
        # TODO: Home Assistant assigns a state to actions. Should we do the same?
        msg = self.set_action.discovery_message()
        msg["state_topic"] = f"leaf/state/{self.state.uid}"
        return [msg, self.state.discovery_message()]

    def __str__(self):
        return f"{self.__class__.__name__}({self.id}) with {', '.join([v.__str__() for v in self.items.values()])}"

    # light

    def discovery_messages(self) -> list[dict[str, object]]:
        msg = self.set_action.discovery_message()
        if self.dimmable:
            msg["brightness_state_topic"] = f"leaf/state/{self.brightness.uid}"
            msg["brightness_command_topic"] = f"leaf/act/{self.brightness.uid}"
        return [msg]

    async def _simulate_light(self, **args):
        # An actual light would listen for actions, update it's state, and emit the updated state
        if "state" in args:
            await self.state.update(args["state"])
        if self.dimmable and "brightness" in args:
            await self.brightness.update(args["brightness"])
