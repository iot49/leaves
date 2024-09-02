import asyncio
import json
import logging
from io import StringIO

from .. import bus
from .transport import Transport

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Bridge:
    """
    Bridge eventbus between two leaves.

    Usage:
    - Instantiate with appropriate transport (e.g. websocket or espnet).
    - Set dst_filter (for events to pass to peer). May be updated after calling run.

    Configuration:
    - `receive_timeout` - time to keep connection open when no messages are received [seconds]
    - `max_latency` - flush is called at least at this interval [seconds]
    - `size_threshold` - flush called automatically when buffer size exceeds this
    """

    # time to keep connection open when no messages are receivedan [seconds]
    receive_timeout = 10
    max_latency = 0.5
    size_threshold = 4000

    def __init__(self, peer: str, transport: Transport):
        """
        Create server. Call serve() to start serving.

        Args:
            transport (Transport): The transport object used for communication.
        """
        self.peer = peer
        self.dst_filter = {peer}
        self.transport = transport
        self._buffer = StringIO()
        self._closed = False
        # these stop / unsubscribe when connection is closed
        bus.subscribe(self._sender_cb, "*")
        bus.subscribe(self._bye_cb, "!bye")
        self._flush_task = asyncio.create_task(self._timed_flush_task())

    async def run(self):
        while not self._closed:
            for _ in range(2):
                try:
                    # wait for events from client
                    msg = await asyncio.wait_for(self.transport.receive(), self.receive_timeout)
                    print(f"RECV Bridge.run: {bus.LEAF_ID}: {msg}")
                    # post received events from client to local bus
                    for event in msg.split("\n")[:-1]:
                        logger.debug(f"EMIT {event}")
                        await bus.emit(json.loads(event))
                    break  # we got a message, back to while loop
                except asyncio.TimeoutError:
                    # timeout - check if connection is still alive (client will reply with !echo)
                    await self.emit(
                        {
                            "topic": "?echo",
                            "src": bus.LEAF_ID,
                            "dst": self.peer,
                            "data": "bridge.run: timeout",
                        }
                    )
                    await self.flush()
                except Exception:
                    # receive failed - close connection
                    self._closed = True
                    return
            else:
                # client did not respond to ?echo - close connection & stop server
                self._closed = True
                return
        logger.debug(f"CLOSED connection to {self.peer}")

    async def emit(self, event: dict):
        """Queue event to send to client."""
        json.dump(event, self._buffer)
        self._buffer.write("\n")
        if self._buffer.tell() > self.size_threshold:
            await self.flush()

    async def flush(self):
        """Send queued events to client"""
        data = self._buffer.getvalue()
        if data and not self._closed:
            # no need for timed flush again for a while ...
            self._flush_task.cancel()
            # allocate a new buffer
            self._buffer = StringIO()
            try:
                logger.debug(f"SEND {data}")
                await self.transport.send(data)
            except Exception:
                # something went wrong - assume the connection is lost
                self._closed = True

    async def close(self):
        """Explicitly close the connection. Happens automatically if connection to client is lost."""
        try:
            if not self._closed:
                await self.emit({"topic": "!bye", "src": bus.LEAF_ID, "dst": self.peer})
                await self.flush()
        finally:
            self._closed = True

    async def _sender_cb(self, **event):
        """Pass events from local bus to client."""
        if self._closed:
            bus.unsubscribe(self._sender_cb)
            bus.unsubscribe(self._bye_cb)
        else:
            if event.get("dst") in self.dst_filter:
                await self.emit(event)
                await self.flush()

    async def _bye_cb(self, **event):
        """Handle bye event from client."""
        if event.get("src") == self.peer:
            await self.close()

    async def _timed_flush_task(self):
        while not self._closed:
            try:
                await asyncio.sleep(self.max_latency)
                await self.flush()
            except asyncio.CancelledError:
                pass
