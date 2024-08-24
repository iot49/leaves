import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from eventbus import bus
from eventbus.devices import (
    Actuator,
    Device,
    State,
    Transducer,
    make_uid,
)


@pytest.fixture
def device():
    return Device("device_id")


@pytest.fixture
def callback():
    return MagicMock()


@pytest.fixture
def entity_id():
    return "entity_id"


@pytest.fixture
def entity_uid(device, entity_id):
    return device.uid(entity_id=entity_id)


@pytest.fixture
def event():
    return {"topic": "topic", "data": "data"}


@pytest.fixture
def timestamp():
    return time.time()


async def test_device_init(device):
    assert device.device_id == "device_id"
    assert device.attributes == {}
    assert device.entities == {}
    assert device._registry == {device.uid(): device}


async def test_device_info(device, entity_uid):
    device.entities[entity_uid] = ("State", None, {})
    assert device.info == {entity_uid: {"kind": "State", "attributes": {}}}


async def test_device_domain(device):
    assert device.domain == "device"


async def test_device_uid(device, entity_id):
    assert device.uid() == "leaf_id.device_id"
    assert device.uid(entity_id=entity_id) == "leaf_id.device_id.entity_id"


async def test_device_update(device, entity_id, event):
    bus.emit = AsyncMock()
    await device.update(entity_id, event["data"])
    bus.emit.assert_called_once_with(
        topic="!state",
        uid=device.uid(entity_id=entity_id),
        value=event["data"],
        timestamp=pytest.approx(time.time()),
    )


async def test_device_str(device, entity_uid):
    device.entities[entity_uid] = ("State", None, {})
    assert str(device) == "Device(device_id, State(leaf_id.device_id.entity_id), {})"


async def xtest_device_info_handler(device):
    bus.emit = AsyncMock()
    await bus.emit("topic", src="src", dst="dst")
    bus.emit.assert_called_once_with(
        topic="!device",
        uid=device.uid(),
        domain=device.domain,
        attributes=device.attributes,
        entities=device.info,
        dst="src",
    )


async def xtest_act_handler(device, entity_uid, callback, event):
    device.entities[entity_uid] = ("Actuator", callback, {})
    await bus.emit(topic="?act", uid=entity_uid, **event)
    callback.assert_called_once_with(device, entity_uid, **event)


async def xtest_act_handler_no_device(device, entity_uid, callback, event):
    await bus.emit(topic="?act", uid=entity_uid, **event)
    callback.assert_not_called()


async def xtest_act_handler_no_callback(device, entity_uid, event):
    device.entities[entity_uid] = ("Actuator", None, {})
    await bus.emit(topic="?act", uid=entity_uid, **event)


async def test_act_handler_no_entity(device, entity_uid, callback, event):
    await bus.emit(topic="?act", uid=entity_uid, **event)
    callback.assert_not_called()


def xtest_make_uid():
    assert make_uid("device_id", "entity_id") == "leaf_id.device_id.entity_id"
    assert (
        make_uid("device_id", "entity_id", "node_id") == "node_id.device_id.entity_id"
    )


def test_state():
    assert State("id", attr="value") == ("id", "State", None, {"attr": "value"})


def test_actuator(callback):
    assert Actuator("id", callback, attr="value") == (
        "id",
        "Actuator",
        callback,
        {"attr": "value"},
    )


def test_transducer(callback):
    assert Transducer("id", callback, attr="value") == (
        "id",
        "Transducer",
        callback,
        {"attr": "value"},
    )
