import asyncio
import json

import aiomqtt
from eventbus import bus
from eventbus.devices import UID_SEP


class HassMqtt:
    def __init__(self, client):
        self.client = client
        self._remove = False
        asyncio.create_task(self._action_listener())

        @bus.on("!device")
        async def discovery_listener(uid, domain, attributes, entities, **rest):
            if domain == "sensor":
                # sensor discovery is special in homeassistant
                for entity_id, entity in entities.items():
                    msg = entity["attributes"].copy()
                    msg["unique_id"] = msg["object_id"] = self._unique_id(entity_id)
                    if "name" not in msg:
                        msg["name"] = self.name(entity_id)
                    msg["availability_topic"] = "leaf/availability"
                    msg["state_topic"] = f"leaf/state/{entity_id}"
                    device = attributes.copy()
                    if "name" not in device:
                        device["name"] = self.name(uid)
                    device["identifiers"] = [self._unique_id(uid)]
                    msg["device"] = device
                    await client.publish(
                        f"homeassistant/{domain}/{msg['unique_id']}/config", None if self._remove else json.dumps(msg)
                    )
            else:
                # default case - works for light, switch, binary_sensor, maybe others
                msg = attributes.copy()
                msg["unique_id"] = msg["object_id"] = self._unique_id(uid)
                if "name" not in msg:
                    msg["name"] = msg["name"] = self.name(uid)
                msg["availability_topic"] = "leaf/availability"
                for entity_uid, entity in entities.items():
                    kind = entity["kind"]
                    _, entity_id = entity_uid.rsplit(UID_SEP, 1)
                    topic = "" if entity_id == "state" else entity_id + "_"
                    if kind in ("State", "Transducer"):
                        msg[f"{topic}state_topic"] = f"leaf/state/{entity_uid}"
                    if kind in ("Actuator", "Transducer"):
                        msg[f"{topic}command_topic"] = f"leaf/act/{entity_uid}"
                await client.publish(
                    f"homeassistant/{domain}/{self._unique_id(uid)}/config", None if self._remove else json.dumps(msg)
                )
            # await bus.emit(topic="?state", uid=make_uid(node_id="server", device_id="node_status", entity_id="status"))

        @bus.on("!state")
        async def state_listener(uid, value, **rest):
            if uid.startswith("server.node_status"):
                await client.publish("leaf/availability", "online" if value == "online" else "offline")
            await client.publish(f"leaf/state/{uid}", value)

    async def remove(self, _remove):
        """
        Remove mode. Normally HassMqtt publishes discovery messages to HomeAssistant.
        In remove mode, it sends removal messages instead.

        :param _remove: True to remove devices, False to add them
        """
        self._remove = _remove
        await bus.emit(topic="?device")

    async def _action_listener(self):
        # forward action events from mqtt to eventbus
        await self.client.subscribe("leaf/act/#")
        async for msg in self.client.messages:
            uid = str(msg.topic).split("/")[-1]
            await bus.emit(topic="?act", uid=uid, value=msg.payload.decode(), src="#hass")

    @staticmethod
    def _unique_id(uid):
        """Home Assistant unique_id - no periods"""
        return uid.replace(UID_SEP, "-")

    @staticmethod
    def name(uid):
        """Guess a name from the uid"""
        return uid.split(UID_SEP)[uid.count(UID_SEP)].replace("_", " ").title()

    async def delete_device(self, hass_entity_id):
        domain, uid = hass_entity_id.split(".")
        await self.client.publish(f"homeassistant/{domain}/{uid}/config")


async def init(broker="mqtt"):
    async with aiomqtt.Client(broker) as client:
        hass_mqtt = HassMqtt(client)
        await bus.emit(topic="?device")

        await asyncio.sleep(1)

        # mark nodes as online
        await node_status.update(bus.LEAF_ID, "online")

        await bus.emit(topic="?act", uid=light1.uid("state"), value="on", dst="leaf_id")
        for i in range(10):
            await climate_sensor.update("temperature", 25 * i)
            await climate_sensor.update("humidity", -i)
            await bus.emit(topic="?act", uid=light1.uid("brightness"), value=25 * i)
            await binary_sensor.update(i % 3 == 0)
            await sw1.update(i % 2 == 0)
            await asyncio.sleep(0.6)
        await bus.emit(topic="?act", uid=light1.uid("state"), value="off", dst="leaf_id")

        # mark nodes as offline
        await node_status.update(bus.LEAF_ID, "offline")

        # testing only: remove all entities from HomeAssistant
        await hass_mqtt.remove(True)
