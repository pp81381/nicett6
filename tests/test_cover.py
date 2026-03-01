import logging
from dataclasses import dataclass
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from nicett6.cover import Cover, PostMovementNotifier, wait_for_motion_to_complete
from tests import MockSleepInstant, MockSleepManual


class TestCover(IsolatedAsyncioTestCase):
    def setUp(self):
        self.sleeper = MockSleepInstant()
        pc_patcher = patch("nicett6.cover.perf_counter", self.sleeper.perf_counter)
        sleep_patcher = patch("nicett6.cover.asyncio_sleep", self.sleeper.sleep)
        self.mock_perf_counter = pc_patcher.start()
        self.mock_sleep = sleep_patcher.start()
        self.addCleanup(pc_patcher.stop)
        self.addCleanup(sleep_patcher.stop)
        self.cover = Cover("Test", 0.8)

    async def test1(self):
        self.assertEqual(self.cover.pos, 1000)
        self.assertAlmostEqual(self.cover.drop, 0)

    async def test2(self):
        await self.cover.set_pos(0)
        self.assertAlmostEqual(self.cover.drop, 0.8)

    async def test3(self):
        await self.cover.set_pos(500)
        self.assertAlmostEqual(self.cover.drop, 0.4)

    async def test4(self):
        with self.assertRaises(ValueError):
            await self.cover.set_pos(-1)

    async def test5(self):
        with self.assertRaises(ValueError):
            await self.cover.set_pos(1001)

    async def test6(self):
        self.assertEqual(self.cover.is_moving, False)
        self.assertEqual(self.cover.is_fully_up, True)

    async def test7(self):
        await self.cover.set_pos(500)
        self.assertEqual(self.cover.is_fully_up, False)
        self.assertEqual(self.cover.is_moving, True)
        self.assertEqual(self.cover.is_going_down, True)
        self.assertEqual(self.cover.is_going_up, False)
        await self.mock_sleep(Cover.MOVEMENT_THRESHOLD_INTERVAL + 0.1)
        self.assertEqual(self.cover.is_fully_up, False)
        self.assertEqual(self.cover.is_moving, False)
        self.assertEqual(self.cover.is_going_down, False)
        self.assertEqual(self.cover.is_going_up, False)
        await self.cover.set_pos(500)
        # Not really a movement but we don't know whether
        # it's the first of a sequence of pos messages
        self.assertEqual(self.cover.is_moving, True)
        await self.cover.set_pos(1000)
        self.assertEqual(self.cover.is_fully_up, False)
        self.assertEqual(self.cover.is_moving, True)
        self.assertEqual(self.cover.is_going_down, False)
        self.assertEqual(self.cover.is_going_up, True)
        await self.mock_sleep(Cover.MOVEMENT_THRESHOLD_INTERVAL + 0.1)
        self.assertEqual(self.cover.is_fully_up, True)
        self.assertEqual(self.cover.is_moving, False)
        self.assertEqual(self.cover.is_going_down, False)
        self.assertEqual(self.cover.is_going_up, False)

    async def test8(self) -> None:
        """Emulate a sequence of movement messages coming in"""

        @dataclass
        class Test8SubTest:
            name: str
            pos_to_set: int | None
            sleep_before_check: float
            expected_pos: int
            expected_is_fully_up: bool
            expected_is_moving: bool
            expected_is_going_down: bool
            expected_is_going_up: bool

        tests = [
            Test8SubTest("Init state", None, 0.0, 1000, True, False, False, False),
            Test8SubTest(
                "After down web cmd", 1000, 0.0, 1000, False, True, False, False
            ),
            Test8SubTest("Down step 1", 900, 0.0, 900, False, True, True, False),
            Test8SubTest("Down step 2", 800, 0.0, 800, False, True, True, False),
            Test8SubTest("Final step down", 700, 0.0, 700, False, True, True, False),
            Test8SubTest(
                "Idle after down",
                None,
                self.cover.MOVEMENT_THRESHOLD_INTERVAL + 0.1,
                700,
                False,
                False,
                False,
                False,
            ),
            Test8SubTest("After up web cmd", 700, 0.0, 700, False, True, False, False),
            Test8SubTest("Up step 1", 800, 0.0, 800, False, True, False, True),
            Test8SubTest("Up step 2", 900, 0.0, 900, False, True, False, True),
            Test8SubTest("Final step up", 1000, 0.0, 1000, False, True, False, True),
            Test8SubTest(
                "Idle after up",
                None,
                self.cover.MOVEMENT_THRESHOLD_INTERVAL + 0.1,
                1000,
                True,
                False,
                False,
                False,
            ),
        ]

        for t in tests:
            with self.subTest(t.name):
                if t.pos_to_set is not None:
                    await self.cover.set_pos(t.pos_to_set)
                await self.mock_sleep(t.sleep_before_check)
                self.assertEqual(self.cover.pos, t.expected_pos)
                self.assertEqual(self.cover.is_fully_up, t.expected_is_fully_up)
                self.assertEqual(self.cover.is_moving, t.expected_is_moving)
                self.assertEqual(self.cover.is_going_down, t.expected_is_going_down)
                self.assertEqual(self.cover.is_going_up, t.expected_is_going_up)

    async def test10(self):
        self.assertTrue(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.cover.set_pos(800)
        self.assertEqual(self.cover._prev_pos, 1000)
        self.assertFalse(self.cover.is_fully_up)
        self.assertTrue(self.cover.is_moving)
        self.assertTrue(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.mock_sleep(Cover.MOVEMENT_THRESHOLD_INTERVAL + 0.01)
        self.assertEqual(self.cover._prev_pos, 1000)  #!!
        self.assertFalse(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.cover.set_idle()
        self.assertEqual(self.cover._prev_pos, 800)  # !!
        self.assertFalse(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.cover.moved()  # We are moving but we don't know the direction yet
        self.assertEqual(self.cover._prev_pos, 800)
        self.assertFalse(self.cover.is_fully_up)
        self.assertTrue(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)

    async def test11(self):
        self.assertTrue(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.cover.set_going_up()
        self.assertFalse(self.cover.is_fully_up)
        self.assertTrue(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertTrue(self.cover.is_going_up)

    async def test12(self):
        self.assertTrue(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.cover.set_going_down()
        self.assertFalse(self.cover.is_fully_up)
        self.assertTrue(self.cover.is_moving)
        self.assertTrue(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)

    async def test13(self):
        self.assertTrue(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.cover.set_target_pos_hint(500)
        self.assertFalse(self.cover.is_fully_up)
        self.assertTrue(self.cover.is_moving)
        self.assertTrue(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)

    async def test14(self):
        await self.cover.set_pos(0)
        await self.mock_sleep(Cover.MOVEMENT_THRESHOLD_INTERVAL + 0.01)
        self.assertFalse(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.cover.set_target_pos_hint(500)
        self.assertFalse(self.cover.is_fully_up)
        self.assertTrue(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertTrue(self.cover.is_going_up)

    async def test15(self):
        await self.cover.set_pos(0)
        await self.cover.set_idle()
        self.assertFalse(self.cover.is_fully_up)
        self.assertTrue(self.cover.is_fully_down)

    async def test16(self):
        await self.cover.set_pos(500)
        await self.cover.set_idle()
        self.assertFalse(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_fully_down)

    async def test17(self):
        await self.cover.set_pos(1000)
        await self.cover.set_idle()
        self.assertTrue(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_fully_down)

    async def test18(self):
        with self.assertLogs("nicett6.cover", level=logging.WARNING) as cm:
            self.cover.log("Test Logging", logging.WARNING)
        self.assertEqual(
            cm.output,
            [
                "WARNING:nicett6.cover:Test Logging; name: Test; max_drop: 0.8; pos: 1000; "
                "_prev_pos: 1000; is_moving: False; is_going_down: False; is_going_up: False; "
                "is_fully_down: False; is_fully_up: True; "
            ],
        )


class TestCoverNotifer(IsolatedAsyncioTestCase):
    async def test1(self):
        """Test the notifier"""

        sleeper = MockSleepInstant()
        manual_sleeper = MockSleepManual()
        with (
            patch("nicett6.cover.asyncio_sleep", sleeper.sleep) as mock_sleep,
            patch("nicett6.cover.perf_counter", sleeper.perf_counter),
            patch("nicett6.cover.notifier_asyncio_sleep", manual_sleeper.sleep),
        ):
            cover = Cover("Test", 0.8)

            self.assertTrue(cover.is_fully_up)
            self.assertFalse(cover.is_moving)
            self.assertFalse(cover.is_going_down)
            self.assertFalse(cover.is_going_up)
            self.assertIsNone(cover._notifier._task)

            # moved() should start task; we also know direction immediately
            await cover.set_pos(800)
            self.assertEqual(cover._prev_pos, 1000)
            self.assertFalse(cover.is_fully_up)
            self.assertTrue(cover.is_moving)
            self.assertTrue(cover.is_going_down)
            self.assertFalse(cover.is_going_up)
            self.assertIsNotNone(cover._notifier._task)
            if cover._notifier._task is not None:
                self.assertFalse(cover._notifier._task.done())

            # wait for motion to to complete but task still running
            await mock_sleep(Cover.MOVEMENT_THRESHOLD_INTERVAL + 0.01)
            self.assertEqual(cover._prev_pos, 1000)  # set_idle() not called yet
            self.assertFalse(cover.is_fully_up)
            self.assertFalse(cover.is_moving)
            self.assertFalse(cover.is_going_down)
            self.assertFalse(cover.is_going_up)
            self.assertIsNotNone(cover._notifier._task)
            if cover._notifier._task is not None:
                self.assertFalse(cover._notifier._task.done())

            # tell notifier sleep to complete so that task completes
            await mock_sleep(PostMovementNotifier.POST_MOVEMENT_ALLOWANCE + 0.02)
            await manual_sleeper.wake()
            await cover.idle_event.wait()
            self.assertEqual(cover._prev_pos, 800)
            self.assertFalse(cover.is_fully_up)
            self.assertFalse(cover.is_moving)
            self.assertFalse(cover.is_going_down)
            self.assertFalse(cover.is_going_up)
            self.assertIsNotNone(cover._notifier._task)
            if cover._notifier._task is not None:
                self.assertTrue(cover._notifier._task.done())

            # Flag that we are moving - however, we don't know the direction yet (restarts background task)
            await cover.moved()
            self.assertEqual(cover._prev_pos, 800)
            self.assertFalse(cover.is_fully_up)
            self.assertTrue(cover.is_moving)
            self.assertFalse(cover.is_going_down)
            self.assertFalse(cover.is_going_up)

            self.assertIsNotNone(cover._notifier._task)
            if cover._notifier._task is not None:
                self.assertFalse(cover._notifier._task.done())
            await cover.stop_notifier()
            self.assertIsNotNone(cover._notifier._task)
            if cover._notifier._task is not None:
                self.assertTrue(cover._notifier._task.done())


class TestWaitForMotionToComplete(IsolatedAsyncioTestCase):
    async def test_wait_for_motion_to_complete(self):
        sleeper = MockSleepInstant()
        with (
            patch("nicett6.cover.asyncio_sleep", sleeper.sleep),
            patch("nicett6.cover.perf_counter", sleeper.perf_counter),
        ):
            cover = Cover("Test", 0.8)
            self.assertFalse(cover.is_moving)
            await cover.moved()
            self.assertTrue(cover.is_moving)
            self.assertAlmostEqual(sleeper.offset, 0.0)
            await wait_for_motion_to_complete([cover])
            self.assertAlmostEqual(sleeper.offset, 2.8)
            self.assertFalse(cover.is_moving)


class TestCoverInverted(IsolatedAsyncioTestCase):
    def setUp(self):
        self.sleeper = MockSleepInstant()
        pc_patcher = patch("nicett6.cover.perf_counter", self.sleeper.perf_counter)
        sleep_patcher = patch("nicett6.cover.asyncio_sleep", self.sleeper.sleep)
        self.mock_perf_counter = pc_patcher.start()
        self.mock_sleep = sleep_patcher.start()
        self.addCleanup(pc_patcher.stop)
        self.addCleanup(sleep_patcher.stop)
        self.cover = Cover("Test", 0.8, inverted_endpoints=True)

    async def test1(self):
        self.assertEqual(self.cover.pos, 0)
        self.assertAlmostEqual(self.cover.drop, 0)

    async def test2(self):
        await self.cover.set_pos(1000)
        self.assertAlmostEqual(self.cover.drop, 0.8)

    async def test3(self):
        await self.cover.set_pos(500)
        self.assertAlmostEqual(self.cover.drop, 0.4)

    async def test4(self):
        with self.assertRaises(ValueError):
            await self.cover.set_pos(-1)

    async def test5(self):
        with self.assertRaises(ValueError):
            await self.cover.set_pos(1001)

    async def test6(self):
        self.assertEqual(self.cover.is_moving, False)
        self.assertEqual(self.cover.is_fully_up, True)

    async def test7(self):
        await self.cover.set_pos(500)
        self.assertEqual(self.cover.is_fully_up, False)
        self.assertEqual(self.cover.is_moving, True)
        self.assertEqual(self.cover.is_going_down, True)
        self.assertEqual(self.cover.is_going_up, False)
        await self.mock_sleep(Cover.MOVEMENT_THRESHOLD_INTERVAL + 0.1)
        self.assertEqual(self.cover.is_fully_up, False)
        self.assertEqual(self.cover.is_moving, False)
        self.assertEqual(self.cover.is_going_down, False)
        self.assertEqual(self.cover.is_going_up, False)
        await self.cover.set_pos(500)
        # Not really a movement but we don't know whether
        # it's the first of a sequence of pos messages
        self.assertEqual(self.cover.is_moving, True)
        await self.cover.set_pos(1000)
        self.assertEqual(self.cover.is_fully_down, False)
        self.assertEqual(self.cover.is_moving, True)
        self.assertEqual(self.cover.is_going_down, True)
        self.assertEqual(self.cover.is_going_up, False)
        await self.mock_sleep(Cover.MOVEMENT_THRESHOLD_INTERVAL + 0.1)
        self.assertEqual(self.cover.is_fully_down, True)
        self.assertEqual(self.cover.is_moving, False)
        self.assertEqual(self.cover.is_going_down, False)
        self.assertEqual(self.cover.is_going_up, False)

    async def test10(self):
        self.assertTrue(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.cover.set_pos(800)
        self.assertEqual(self.cover._prev_pos, 0)
        self.assertFalse(self.cover.is_fully_up)
        self.assertTrue(self.cover.is_moving)
        self.assertTrue(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.mock_sleep(Cover.MOVEMENT_THRESHOLD_INTERVAL + 0.01)
        self.assertEqual(self.cover._prev_pos, 0)  #!!
        self.assertFalse(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.cover.set_idle()
        self.assertEqual(self.cover._prev_pos, 800)  # !!
        self.assertFalse(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.cover.moved()  # We are moving but we don't know the direction yet
        self.assertEqual(self.cover._prev_pos, 800)
        self.assertFalse(self.cover.is_fully_up)
        self.assertTrue(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)

    async def test11(self):
        self.assertTrue(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.cover.set_going_up()
        self.assertFalse(self.cover.is_fully_up)
        self.assertTrue(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertTrue(self.cover.is_going_up)

    async def test12(self):
        self.assertTrue(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.cover.set_going_down()
        self.assertFalse(self.cover.is_fully_up)
        self.assertTrue(self.cover.is_moving)
        self.assertTrue(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)

    async def test13(self):
        self.assertTrue(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.cover.set_target_pos_hint(500)
        self.assertFalse(self.cover.is_fully_up)
        self.assertTrue(self.cover.is_moving)
        self.assertTrue(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)

    async def test14(self):
        await self.cover.set_pos(1000)
        await self.mock_sleep(Cover.MOVEMENT_THRESHOLD_INTERVAL + 0.01)
        self.assertFalse(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertFalse(self.cover.is_going_up)
        await self.cover.set_target_pos_hint(500)
        self.assertFalse(self.cover.is_fully_up)
        self.assertTrue(self.cover.is_moving)
        self.assertFalse(self.cover.is_going_down)
        self.assertTrue(self.cover.is_going_up)

    async def test15(self):
        await self.cover.set_pos(1000)
        await self.cover.set_idle()
        self.assertFalse(self.cover.is_fully_up)
        self.assertTrue(self.cover.is_fully_down)

    async def test16(self):
        await self.cover.set_pos(500)
        await self.cover.set_idle()
        self.assertFalse(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_fully_down)

    async def test17(self):
        await self.cover.set_pos(0)
        await self.cover.set_idle()
        self.assertTrue(self.cover.is_fully_up)
        self.assertFalse(self.cover.is_fully_down)

    async def test18(self):
        with self.assertLogs("nicett6.cover", level=logging.WARNING) as cm:
            self.cover.log("Test Logging", logging.WARNING)
        self.assertEqual(
            cm.output,
            [
                "WARNING:nicett6.cover:Test Logging; name: Test; max_drop: 0.8; pos: 0; "
                "_prev_pos: 0; is_moving: False; is_going_down: False; is_going_up: False; "
                "is_fully_down: False; is_fully_up: True; "
            ],
        )
