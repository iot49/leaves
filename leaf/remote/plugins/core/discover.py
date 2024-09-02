from eventbus import bus


class Discover:
    """Keep tack of discovery messages."""

    def __init__(self):
        self._discoveries = {}

        @bus.on("!discover")
        def update(topic, src, dst, id, message):
            self._discoveries[id] = message

        @bus.on("?discover")
        async def get(topic, src, dst, uid=None):
            if uid is None:
                # copy keys to protect against modification in !state by a different task
                for uid in list(self._discoveries.keys()):
                    value, ts = self._discoveries[uid]
                    await bus.emit(topic="!state", uid=uid, value=value, timestamp=ts, dst=src)
            else:
                if uid in self._discoveries:
                    value, ts = self._discoveries[uid]
                    await bus.emit(topic="!state", uid=uid, value=value, timestamp=ts, dst=src)
                else:
                    await bus.emit(topic="#state", uid=uid, error="state not known", dst=src)
