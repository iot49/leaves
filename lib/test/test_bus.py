import asyncio

from eventbus import bus


async def test_events():
    N = 0
    events = {
        "topic1": {"topic": "topic1", "data": "data1"},
        "topic2": {"topic": "topic2", "data": "data2"},
    }

    async def cb_async(topic, data):
        nonlocal N
        N += 1
        assert events[topic]["data"] == data

    def cb_sync(topic, data):
        nonlocal N
        N += 1
        assert events[topic]["data"] == data

    for cb in [cb_async, cb_sync]:
        N = 0
        bus.subscribe(cb, "topic1")

        # emit to registered handler
        await bus.emit(events["topic1"])
        assert N == 1

        # emit topic with no handler
        await bus.emit(events["topic2"])
        assert N == 1

        # emit to catch event with no handler
        bus.subscribe(cb, "!")
        await bus.emit(events["topic2"])
        assert N == 2

        # emit to all handlers
        bus.subscribe(cb, "*")
        await bus.emit(events["topic2"])
        assert N == 4

        # emit sync event
        bus.emit_sync(events["topic1"])
        await asyncio.sleep(bus.pause + 0.001)
        assert N == 6

        # unsubscribe topic1 handler
        bus.unsubscribe(cb, "topic1")
        await bus.emit(events["topic1"])
        assert N == 7

        # unsubscribe all handlers
        bus.unsubscribe(cb, "*", "!")
        await bus.emit(events["topic1"])
        assert N == 7


# Note: @bus.on handlers cannot be un/resubscribed, causing problems
#       This test runs correctly on its own, but fails when run with other tests
async def DISABLE_test_on():
    N = 0
    events = {
        "topic1": {"topic": "topic1", "data": "data1"},
        "topic2": {"topic": "topic2", "data": "data2"},
    }

    bus.unsubscribe_all()

    @bus.on("topic1")
    async def topic1_cb(topic, data):
        nonlocal N
        N += 1
        assert events[topic]["data"] == data

    # emit to registered handler
    await bus.emit(events["topic1"])
    assert N == 1

    # emit topic with no handler
    await bus.emit(events["topic2"])
    assert N == 1

    # emit to catch to topic without handler
    @bus.on("!")
    async def cb_no(topic, data):
        nonlocal N
        N += 1
        assert events[topic]["data"] == data

    await bus.emit(events["topic2"])
    assert N == 2

    # emit to all handlers
    @bus.on("*")
    async def cb_all(topic, data):
        nonlocal N
        N += 1
        assert events[topic]["data"] == data

    await bus.emit(events["topic2"])
    assert N == 4
