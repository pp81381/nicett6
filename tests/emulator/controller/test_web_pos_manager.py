from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from nicett6.emulator.controller.web_pos_manager import WebPosManager
from nicett6.emulator.cover_emulator import TT6CoverEmulator
from nicett6.ttbus_device import TTBusDeviceAddress


async def make_test_web_pos_mgr(web_on: bool) -> WebPosManager:
    writer_manager = AsyncMock()
    device_tt_addr = TTBusDeviceAddress(0x02, 0x04)
    device = TT6CoverEmulator("screen", device_tt_addr, 0.01, 1.77, 0.08, 1000)
    web_pos_manager = WebPosManager(writer_manager, web_on)
    device.attach(web_pos_manager)
    await device.notify_observers()
    return web_pos_manager


class TestWebPosManager(IsolatedAsyncioTestCase):
    async def test_web_on(self):
        web_pos_manager = await make_test_web_pos_mgr(True)
        writer_manager = web_pos_manager.writer_manager
        assert isinstance(writer_manager, AsyncMock)
        writer_manager.write_all.assert_awaited_once_with("POS * 02 04 1000 FFFF FF")

    async def test_web_off(self):
        web_pos_manager = await make_test_web_pos_mgr(False)
        writer_manager = web_pos_manager.writer_manager
        assert isinstance(writer_manager, AsyncMock)
        writer_manager.write_all.assert_not_awaited()
