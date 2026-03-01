import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock

from nicett6.emulator.cover_emulator import TT6CoverEmulator


class TestCoverMovement(IsolatedAsyncioTestCase):
    """Test Cover movement"""

    def setUp(self):
        self.cover = TT6CoverEmulator("screen", MagicMock(), 0.01, 1.77, 0.08, 1000)

    async def test_step_movements(self):
        self.assertEqual(self.cover.pos, 1000)
        self.assertAlmostEqual(self.cover.drop, 0.0)
        await self.cover.move_to_pos(900)
        self.assertEqual(self.cover.pos, 900)
        await self.cover.move_up()
        self.assertEqual(self.cover.pos, 1000)
        await self.cover.move_down_step()
        self.assertEqual(self.cover.pos, 995)
        self.assertEqual(self.cover.drop, 0.01)
        await self.cover.move_up_step()
        self.assertEqual(self.cover.pos, 1000)
        self.assertEqual(self.cover.drop, 0.0)

    async def test_stop(self):
        mover = asyncio.create_task(self.cover.move_down())
        delay = 3
        await asyncio.sleep(delay)
        await self.cover.stop()
        await mover
        self.assertGreater(self.cover.drop, 0.19)
        self.assertLess(self.cover.drop, 0.24)

    async def test_move_while_moving(self):
        mover = asyncio.create_task(self.cover.move_down())
        delay = 3
        await asyncio.sleep(delay)
        self.assertGreater(self.cover.drop, 0.19)
        self.assertLess(self.cover.drop, 0.24)
        await self.cover.move_up()
        await mover
        self.assertEqual(self.cover.drop, 0)


class TestInvertedCoverMovement(IsolatedAsyncioTestCase):
    """Test Inverted Cover movement"""

    def setUp(self):
        self.cover = TT6CoverEmulator(
            "screen", MagicMock(), 0.01, 1.77, 0.08, 0, inverted_endpoints=True
        )

    async def test_step_movements(self):
        self.assertEqual(self.cover.pos, 0)
        self.assertAlmostEqual(self.cover.drop, 0.0)
        await self.cover.move_to_pos(100)
        self.assertEqual(self.cover.pos, 100)
        await self.cover.move_up()
        self.assertEqual(self.cover.pos, 0)
        await self.cover.move_down_step()
        self.assertEqual(self.cover.pos, 5)
        self.assertEqual(self.cover.drop, 0.01)
        await self.cover.move_up_step()
        self.assertEqual(self.cover.pos, 0)
        self.assertEqual(self.cover.drop, 0.0)
