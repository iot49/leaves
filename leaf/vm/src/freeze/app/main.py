import asyncio
import json
import logging
import sys
import time

import esp32  # type: ignore
import ntptime  # type: ignore

from eventbus import event_type, eventbus

from . import (
    DOMAIN,
    config,
    led,
    ota,  # noqa: F401
    secrets,
)
from .gateway import Gateway  # type: ignore
from .wifi import wifi

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@eventbus.on(event_type.PUT_CONFIG)
def put_config(data, version, **event):
    with open("/config.json", "w") as f:
        logger.info(f"Updating config from {config.get('version')} --> {version}")
        f.write(json.dumps(data))


@eventbus.on(event_type.PUT_SECRETS)
def put_secrets(data, version, **event):
    with open("/secrets.json", "w") as f:
        logger.info(f"Updating config from {secrets.get('version')} --> {version}")
        f.write(json.dumps(data))


@eventbus.on(event_type.PUT_CERT)
def put_cert(data, version, **event):
    with open("/secrets.json", "w") as f:
        logger.info(f"Updating certs --> {version}")
        f.write(json.dumps(data))


async def main_task(ws_url):
    async with wifi:
        led.pattern = led.GREEN_BLINK_FAST
        ntptime.settime()
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time()))
        logger.info(f"Time set to {t}")

        # load plugins
        # plugins = config.get(f"trees/{tree_id}/branches/{branch_id}/plugins", {})
        plugins = config.get("trees/plugins", {})
        print("load plugins", plugins)
        for mod, param in plugins.items():
            try:
                m = __import__(mod, None, None, (), 0)
                if "init" in m.__dict__:
                    if isinstance(m.init, type(main_task)):
                        asyncio.create_task(m.init(**(param or {})))
                    else:
                        m.init(**(param or {}))
                logger.info(f"Loaded plugin {mod} with {param}")
            except ImportError as e:
                logger.error(f"import {mod}: {e}")

        # since we got here, we assume the app is working
        logger.debug("esp32.Partition.mark_app_valid_cancel_rollback()")
        esp32.Partition.mark_app_valid_cancel_rollback()

        # connect to earth
        gateway = Gateway()
        reconnect_delay = 1
        while True:
            try:
                msg = await gateway.connnect(ws_url)
                print(f"Disconnected from {ws_url}: {msg}, reconnecting in {reconnect_delay} seconds")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(5, reconnect_delay * 2)
            except Exception as e:
                print("main_task - gateway disconnected", e)


async def main(ws_url=f"wss://{DOMAIN}/gateway/ws", logging_level=logging.INFO):
    logger.setLevel(logging_level)
    logger.info("Starting main")
    asyncio.create_task(led.run())
    led.pattern = led.GREEN_BLINK_SLOW
    while True:
        try:
            await main_task(ws_url)
        except Exception as e:
            print("exception in main", e)

            sys.print_exception(e)  # type: ignore
            logger.exception(f"??? main: {e}", exc_info=e)
        finally:
            asyncio.new_event_loop()
