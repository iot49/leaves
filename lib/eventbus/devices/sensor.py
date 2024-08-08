from . import Device


class Sensor(Device):
    def __init__(self, device_id, *state_entities, **attributes):
        for _, kind, _, _ in state_entities:
            assert kind == "State", f"Expected State, got {kind}"
        super().__init__(device_id, *state_entities, **attributes)
