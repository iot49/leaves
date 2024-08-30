import asyncio

from eventbus.bus import Reflect

reflect = None


async def init(interval: float = 10):
    global reflect
    reflect = Reflect(interval=interval)
    asyncio.create_task(reflect.emitter_task())
