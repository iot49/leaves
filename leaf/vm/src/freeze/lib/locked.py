import asyncio

class Locked:

    def __init__(self, object):
        self._object = object
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        await self._lock.acquire()
        return self._object

    async def __aexit__(self, *args):
        self._lock.release()
