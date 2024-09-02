import asyncio
import logging
import sys
import time
from typing import Awaitable

from eventbus import bus
from util import is_micropython

from .cfg import Config
from .wifi import Radio, Wifi

radio = Radio()
wifi = Wifi()
config = Config()

if is_micropython():
    from .led import LED

    led = LED()


# logging must be configured before any actual logging
def configure_logging():
    class LogHandler(logging.Handler):
        """Post !log events. Subscribe elsewhere to display them"""

        def emit(self, record):
            try:
                timestamp = record.created
            except Exception:
                # Micropython logging uses record.ct
                EPOCH_OFFSET = 946684800 if time.gmtime(0)[0] == 2000 else 0
                timestamp = record.ct + EPOCH_OFFSET  # type: ignore
            # TODO: trap invalid messages (e.g. binary data)
            self.format(record)
            bus.emit_sync(
                topic="!log",
                levelname=record.levelname,
                levelno=record.levelno,
                timestamp=timestamp,
                name=record.name,
                message=record.message,
                src=bus.LEAF_ID,
                dst="root",
            )

    root_logger = logging.getLogger()
    # remove default handler
    root_logger.handlers = []
    root_logger.addHandler(LogHandler())


def global_exception_handler(loop, context):
    print("---------- Global exception handler", context)
    print(context)
    try:
        # Micropython
        sys.print_exception(context["exception"])  # type: ignore
    except:  # noqa: E722
        pass
    # stop event loop
    loop.stop()

    # re-raise exception
    raise context.get("exception", Exception("No exception"))


async def app_main():
    # trap unhandled exceptions
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(global_exception_handler)

    # set LEAF_ID
    bus.LEAF_ID = await config.leaf_id()

    # logging
    configure_logging()

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.info(f"Starting leaf {bus.LEAF_ID}")

    # load plugins
    config.update()
    print(config.get())
    plugins = config.get("leaves/root/plugins", {})
    print("LOADING", plugins)
    for module, param in plugins.items():
        param = param or {}
        m = __import__(module, None, None, ("all",), 0)
        print("init", module, param, hasattr(m, "init"))
        if hasattr(m, "init"):
            res = m.init(**param)
            if isinstance(res, Awaitable):
                await res

    # don't exit
    while True:
        await asyncio.sleep(1)
