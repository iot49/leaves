# MQTT bridge for Entity to Home Assistant


import asyncio
import re

from eventbus import bus

# Convert CamelCase to snake_case (also apply lower to result)
RE_CAMEL_TO_SNAKE = re.compile(r"(?<!^)(?=[A-Z])")


async def init(client):
    @bus.on("!device")
    async def new_device(topic, uid, attributes, states, actions, dst):
        print(f"DISCOVER {uid}")

    @bus.on("!state")
    async def update_state(topic, uid, value, timestamp):
        print(f"UPDATE {uid} = {value}")

    async def action_listener():
        nonlocal client
        await client.subscribe("leaf/act/#")
        async for msg in client.messages:
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

    asyncio.create_task(action_listener())

    await bus.emit(topic="?device", src="me")
