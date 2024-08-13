from . import bus, singleton


@singleton
class SensorState:
    """Keep tack of state values."""

    def __init__(self):
        self._state = {}

        @bus.on("!state")
        def update(uid, value, timestamp, **rest):
            self._state[uid] = (value, timestamp)

        @bus.on("?state")
        async def get(src, uid=None, **rest):
            if uid is None:
                # copy keys to protect against modification in !state by a different task
                for uid in list(self._state.keys()):
                    value, ts = self._state[uid]
                    await bus.emit(
                        topic="!state", uid=uid, value=value, timestamp=ts, dst=src
                    )
            else:
                if uid in self._state:
                    value, ts = self._state[uid]
                    await bus.emit(
                        topic="!state", uid=uid, value=value, timestamp=ts, dst=src
                    )
                else:
                    await bus.emit(
                        topic="#state", uid=uid, error="state not known", dst=src
                    )
