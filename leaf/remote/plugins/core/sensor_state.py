from eventbus import bus


class SensorState:
    """Keep tack of state values."""

    def __init__(self):
        self._state = {}

        @bus.on("!state")
        def update(topic, src, dst, uid, value, timestamp):
            self._state[uid] = (value, timestamp)

        @bus.on("?state")
        async def get(topic, src, dst, uid=None):
            if uid is None:
                # copy keys to protect against modification in !state by a different task
                for uid in list(self._state.keys()):
                    value, ts = self._state[uid]
                    await bus.emit(topic="!state", uid=uid, value=value, timestamp=ts, dst=src)
            else:
                if uid in self._state:
                    value, ts = self._state[uid]
                    await bus.emit(topic="!state", uid=uid, value=value, timestamp=ts, dst=src)
                else:
                    await bus.emit(topic="#state", uid=uid, error="state not known", dst=src)
