import asyncio
import logging
import sys
import time
from pprint import pprint

from eventbus import Config, Log, bus
from util import is_micropython

global config, radio, wifi, mac_address


# logging must be configured before any actual logging
def configure_logging():
    class LogHandler(logging.Handler):
        def emit(self, record):
            try:
                timestamp = record.created
            except Exception:
                EPOCH_OFFSET = 946684800 if time.gmtime(0)[0] == 2000 else 0
                timestamp = record.ct + EPOCH_OFFSET  # type: ignore
            # print("app_main LogHandler", record.msg, dir(record))
            self.format(record)
            bus.emit_sync(
                topic="!log",
                levelname=record.levelname,
                levelno=record.levelno,
                timestamp=timestamp,
                name=record.name,
                message=record.message,
                src=bus.LEAF_ID or "?",
                dst="root",
            )

    root_logger = logging.getLogger()
    # remove default handler
    root_logger.handlers = []
    root_logger.addHandler(LogHandler())


def global_exception_handler(loop, context):
    print("---------- Global exception handler", context)
    pprint(context)
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
    global config, radio, wifi

    # config
    config = Config()
    bus.LEAF_ID = config.leaf_id()

    # logging
    configure_logging()
    Log()
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    logger.info(f"Starting leaf {bus.LEAF_ID}")

    # wifi
    if is_micropython():
        from .wifi.micro_python import radio, wifi
    else:
        from .wifi.c_python import radio, wifi

    # event_net
    from eventbus.event_net import webserver  # isort:skip

    await webserver.init()

    # don't exit
    while True:
        await asyncio.sleep(1)
