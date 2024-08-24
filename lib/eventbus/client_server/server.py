# ws server @ http://localhost:8080/ws

import aiohttp
from aiohttp import web

app = web.Application()


async def hello(request):
    return web.Response(text="Hello, world")


app.add_routes([web.get("/", hello)])


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    print(f"websocker_handler: {request} {ws}")
    await ws.prepare(request)

    async for msg in ws:
        print(f"msg: {msg}")
        if msg.type == aiohttp.WSMsgType.TEXT:
            if msg.data == "close":
                await ws.close()
            else:
                print("ECHO: %s" % msg.data)
                await ws.send_str(msg.data)
        elif msg.type == aiohttp.WSMsgType.ERROR:
            print("ws connection closed with exception %s" % ws.exception())

    print("websocket connection closed")

    return ws


app.add_routes([web.get("/ws", websocket_handler)])

web.run_app(app)
