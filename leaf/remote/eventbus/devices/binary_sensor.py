from . import Device, State
from .util import coerce_on_off


class BinarySensor(Device):
    def __init__(self, id, **attributes):
        super().__init__(id, State("state"), **attributes)

    async def update(self, value):  # type: ignore
        """
        Update the state of the binary sensor.

        Parameters:
        - value: The new value to update the state with.
            Possible values are:
                None (unknown), "ON", "OFF". Other values are mapped to "ON" or "OFF".
        """
        await super().update(self.uid("state"), coerce_on_off(value))
