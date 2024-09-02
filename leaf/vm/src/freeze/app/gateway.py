import asyncio
import json
import logging
import os

import aiohttp

from eventbus import Event, event_type, eventbus
from eventbus.event import get_cert, get_config, get_secrets, ping

from . import CERT_DIR, config, led, secrets
from .wifi import wifi

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

DEBUG = False


class Gateway:
    def __init__(self):
        self.connected = False

    async def connnect(self, ws_url) -> str:
        """Connect to earth. Returns when the connection is closed.

        Returns:
            str: disconnect reason.
        """
        async with wifi:
            logger.info(f"Connecting to earth @ {ws_url}")
            try:
                async with aiohttp.ClientSession() as session:
                    # connect to websocket
                    gateway_token = secrets["gateway-token"]
                    async with session.ws_connect(ws_url) as ws:
                        self.connected = True
                        msg = await self._connection(ws, gateway_token)
                    return msg
            except Exception as e:
                logger.error(f"connect error: {e}")
                return f"unreachable: {ws_url}"
            finally:
                self.connected = False

    async def _connection(self, ws, gateway_token) -> str:
        """Handle connection to earth.
        Returns when the connection is closed.
            str: disconnect reason.
        """
        auth_msg = await ws.receive_json()
        logger.debug(f"Received auth request - {auth_msg}")
        if auth_msg["type"] == event_type.GET_AUTH:
            await ws.send_json({"type": event_type.PUT_AUTH, "token": gateway_token})
        hello_msg = await ws.receive_json()
        if hello_msg["type"] == event_type.HELLO_CONNECTED:
            # send pings and receive messages
            self._ws = ws
            logger.info(f"Connected - {hello_msg}")
            led.pattern = led.GREEN

            @eventbus.on("*")
            async def emitter(**event):
                if self.connected:
                    await self.emit_to_ws(event)
                else:
                    eventbus.off(emitter)

            tasks = [
                self._ping_task(hello_msg["param"]["timeout_interval"]),
                self._receiver_task(),
                self._update_task(hello_msg["param"]["versions"]),
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
            return "connection closed"
        else:
            return f"connection failed: {hello_msg}"

    async def _ping_task(self, interval):
        ws = self._ws
        while self.connected:
            # errors handled in connect_task by gather
            await ws.send_json(ping)
            await asyncio.sleep(interval)

    async def _receiver_task(self):
        async for msg in self._ws:
            if not self.connected:
                return
            if msg.type == aiohttp.WSMsgType.TEXT:
                if DEBUG:
                    print(f"received msg-type={msg.type}: {str(msg.data)}")
                await eventbus.emit(json.loads(msg.data))
            elif msg.type == aiohttp.WSMsgType.ERROR:
                print(f"receiver_task: ws returned error {msg}")
                self.connected = False
                return

    async def _update_task(self, versions):
        # config and secrets
        if versions.get("config") != config.get("version"):
            gc = get_config()
            gc["dst"] = "#earth"
            await self.emit_to_ws(gc)
        if versions.get("secrets") != secrets.get("version"):
            await self.emit_to_ws(get_secrets(dst="#earth"))

        # certificates
        version = ""
        version_file = f"{CERT_DIR}/version"
        if os.path.isfile(version_file):
            with open(version_file) as f:
                version = f.read().strip()
        if versions.get("certificates", "") != version:
            # update certificates
            await self.emit_to_ws(get_cert())

    async def emit_to_ws(self, event: Event) -> None:
        if not self.connected:
            return
        dst = event.get("dst", "")
        if dst in ("#clients", "#earth") or dst.startswith("@"):
            if DEBUG:
                print(f"sending {event}")
            try:
                await self._ws.send_json(event)
            except OSError as e:
                self.connected = False
                print(f"failed send_json: {e}")
        else:
            if DEBUG and event.get("type", "") not in (event_type.PING, event_type.PONG):
                (f"skipping {event}")
