import asyncio

from app import wifi
from eventbus import Bridge
from microdot import Microdot, abort
from microdot.websocket import WebSocket, websocket_upgrade

app = Microdot()


WebSocket.max_message_length = 1024 * 1024


@app.route("/")
async def index(request):
    return "Hello leaf!"


@app.route("/ping")
async def ping(request):
    return "pong"


@app.route("/ws")
async def ws(request):
    # authenticate
    peer = request.cookies.get("leaf-token")
    print("\n\nnew connection with token", peer)
    if peer is None:
        abort(401)

    # open websocket
    transport = await websocket_upgrade(request)
    # TODO: close any existing connection for this client
    bridge = Bridge(peer, transport)  # type: ignore
    await bridge.run()


async def init(host="localhost", port=5000, debug=False, ssl=None):
    async with wifi:
        asyncio.create_task(app.start_server(host=host, port=port, debug=debug, ssl=ssl))
