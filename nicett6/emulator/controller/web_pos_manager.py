from nicett6.emulator.cover_emulator import TT6CoverEmulator
from nicett6.utils import AsyncObservable, AsyncObserver

from .writer_manager import WriterManager


class WebPosManager(AsyncObserver):
    """
    Manage WEB_COMMANDS mode

    This object observes a set of devices
    The writer_manager keeps track of the writers for all client connections
    If WEB_COMMANDS are ON then this object will send a position message to
    all clients when a device notifies of an update
    """

    def __init__(self, writer_manager: WriterManager, web_on: bool) -> None:
        super().__init__()
        self.writer_manager = writer_manager
        self.web_on = web_on

    async def update(self, observable: AsyncObservable) -> None:
        if isinstance(observable, TT6CoverEmulator) and self.web_on:
            await self.writer_manager.write_all(observable.fmt_pos_msg())
