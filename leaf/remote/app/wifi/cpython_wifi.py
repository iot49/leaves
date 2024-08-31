from uuid import getnode as get_mac


class ContextHandler:
    async def __aenter__(self):
        pass

    async def __aexit__(self, *args):
        pass

class Radio(ContextHandler):
    async def mac_address(self) -> str:
        return ":".join(
            [f"{(get_mac() >> i) & 0xff:02x}" for i in range(0, 48, 8)]
        )
    

class Wifi(ContextHandler):
    pass