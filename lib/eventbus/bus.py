import asyncio
import functools
from typing import Awaitable, Callable, TypeAlias

ALL_HANDLER = "*"
NO_HANDLER = "!"


Callback: TypeAlias = Callable[..., Awaitable[None] | None]


class Bus:
    """
    A class that represents an event emitter.

    The EventEmitter class allows registering event handlers for specific topics and emitting events to those handlers.
    """

    def __init__(self, *, sync_queue_size=20, pause=0.1):
        """
        Initializes the event emitter object.

        Args:
            sync_queue_size (int): The maximum size of the emit_sync queue.
            pause (float): Delay between submission of sync events.

        Attributes:
            leaf_id (str): Address of this leaf.
        """
        self.listeners: dict[str, list[Callback]] = {}
        self.event_queue = None
        self.sync_queue_size = sync_queue_size
        self.pause = pause
        self.leaf_id = "leaf_id"

    def subscribe(self, cb: Callback, *topics):
        """Subscribe callback to one or more topics."""
        for topic in topics:
            if topic not in self.listeners:
                self.listeners[topic] = []
            self.listeners[topic].append(cb)

    def unsubscribe(self, cb: Callback, *topics):
        """Unsubscribe callback to one or more topics."""
        for topic in topics:
            if topic in self.listeners:
                self.listeners[topic].remove(cb)

    def unsubscribe_all(self):
        """Remove all callbacks."""
        self.listeners = {}

    def on(self, *topics):
        """
        Decorator function to register a handler for one or more topics.

        Args:
            *topics: Variable number of topics to listen to.

            The following topics have special meaning:
            - '*': A handler that listens to all topics.
            - '!': A handler that listens to topics that have no registered handlers.

        Returns:
            A decorator function that wraps the provided function and adds it to the event map.

        Example:
            @event_emitter.on('topic1', 'topic2')
            def my_listener(topic, **kwargs):
                print(f'Received topic: {topic} with args: {kwargs}')
        """

        def decorator_on(func):
            self.subscribe(func, *topics)

            @functools.wraps(func)
            def wrapper_on(event):
                return func(event)

            return wrapper_on

        return decorator_on

    async def emit(self, event):
        """
        Emits an event to all registered event handlers for the given topic.

        Args:
            event (dict)
        """
        topic = event.get("topic")
        if topic in self.listeners:
            # call registered handlers for the topic
            await self._call_handler(self.listeners[topic], event)
        else:
            # no registered handlers for the topic - call catch-all handler
            await self._call_handler(self.listeners.get(NO_HANDLER, []), event)
        # call registered handlers for all topics
        await self._call_handler(self.listeners.get(ALL_HANDLER, []), event)

    async def emit_kwargs(self, **kwargs):
        """Same as `emit`, but accepts kwargs."""
        await self.emit(kwargs)

    def emit_sync(self, event):
        """
        Emit event from synchronous code.

        Args:
            event (dict)
        """
        if self.event_queue is None:
            try:
                self.event_queue = asyncio.Queue(maxsize=self.sync_queue_size)
            except AttributeError:
                # MicroPython does not currently provide asyncio.Queue
                from asyncio_extra import queue  # type: ignore

                self.event_queue = queue.Queue(maxsize=self.sync_queue_size)
            asyncio.create_task(self._sync_emit_task(self.pause))

        try:
            self.event_queue.put_nowait(event)
        except asyncio.QueueFull:
            pass
            # Note: no log message - as that would generate another emit_sync event!
            print("***** sync event queue overflow")

    def emit_sync_kwargs(self, **kwargs):
        """Same as `emit_sync`, but accepts kwargs."""
        self.emit_sync(kwargs)

    async def _sync_emit_task(self, pause):
        """Helper task to send sync events."""
        while True:
            event = await self.event_queue.get()  # type: ignore
            await self.emit(event)
            await asyncio.sleep(pause)

    async def _call_handler(self, funcs: list[Callback], event):
        """Helper to call sync / async callbacks."""
        for func in funcs:
            res = func(**event)
            if isinstance(res, Awaitable):
                await res
