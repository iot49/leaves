from . import ActionCallback, Device, Transducer
from .util import coerce_on_off


class Switch(Device):
    def __init__(self, id, callback: ActionCallback, **attributes):
        super().__init__(
            id,
            Transducer("state", callback),
            **attributes,
        )

    async def update(self, value):  # type: ignore
        """
        Update the state of the switch.

        Args:
            value: ON, OFF, or None.
        """
        await super().update("state", coerce_on_off(value))
