from . import ActionCallback, Device, Transducer
from .util import coerce_on_off


class Light(Device):
    def __init__(self, id, callback: ActionCallback, **attributes):
        super().__init__(
            id,
            Transducer("state", callback),
            Transducer("brightness", callback),
            **attributes,
        )

    async def update(self, entity_id, value):  # type: ignore
        if entity_id.endswith("state"):
            value = coerce_on_off(value)
        await super().update(entity_id, value)
