import asyncio

from eventbus.bus import Counter


async def init(eid: str, interval: float = 10, N: int = 1000):
    asyncio.create_task(Counter(eid, interval=interval).counter_task())
