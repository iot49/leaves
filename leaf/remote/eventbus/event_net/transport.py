class Transport:
    """
    Abstract class encapsulating the communication between client and server.
    Implementations may provide e.g.:
        * encryption
        * guaranteed delivery
        * automatic reconnection
    """

    async def send(self, message: str):
        """Send message to peer. Raise Exception on failure (e.g. connection lost)."""
        raise NotImplementedError

    async def receive(self) -> str:
        """Receive message from peer. Raise Exception on failure (e.g. connection lost)."""
        raise NotImplementedError

    @property
    def closed(self) -> bool:
        """Optional - implement if transport knows about connection status."""
        return False


class AioTransport(Transport):
    def __init__(self, ws):
        self.ws = ws

    async def send(self, message: str):
        await self.ws.send_str(message)

    async def receive(self) -> str:
        return await self.ws.receive_str()
