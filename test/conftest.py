import pytest

from eventbus import bus


@pytest.fixture(scope="session", autouse=True)
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def unsubscribe_all():
    bus.unsubscribe_all()
