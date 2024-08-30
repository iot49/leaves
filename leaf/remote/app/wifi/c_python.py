import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class WifiException(Exception):
    pass


class ContextHandler:
    async def __aenter__(self):
        pass

    async def __aexit__(self, *args):
        pass


radio = wifi = ContextHandler()
