from eventbus import bus
from eventbus.devices import Device


async def test_entities():
    print()
    bus.leaf_id = "test"

    device1 = Device("device1")
    ent1 = Entity(device1, "ent1")
    ent2 = Entity(device1, "ent2")

    async def action_cb(**args):
        print("ACTION", args)

    action1 = Action(device1, "action1")
    action2 = Action(device1, "action2")
    action1.subscribe(action_cb)
    action2.subscribe(action_cb)

    @bus.on("*")
    def event_printer(**event):
        print("GOT event", event)

    await ent1.update("entity_1_update")
    await ent2.update("entity_1_update")

    await bus.emit_event(
        {"topic": "!action", "action": "action2", "value": "action1_value"}
    )
