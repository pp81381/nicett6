import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Coroutine, Dict

from nicett6.ttbus_device import TTBusDeviceAddress
from nicett6.utils import AsyncObservable, check_pos

_LOGGER = logging.getLogger(__name__)


class MoverManager:
    """
    Helper class to manage cover movement

    The cover can only be moving to one position at a time.
    If a second request is made while the Cover is already moving then the
    current mover_coro is stopped by sending it a stop event and then the
    new mover_coro is initiated.
    The holder of current_mover_lock is the current mover and is supposed to
    periodically wait on stop_event (see self._sleep)
    The holder of next_mover_lock is the next mover and this routine will send a
    stop event to the current mover on its behalf
    The next_mover_lock is released as soon as the next mover aquires the
    current_mover_lock and becomes the current mover

    Note that the __init__ method creates asyncio objects that require the
    event loop to be running - you can get obscure errors in non-asyncio
    unittests if you construct an object of this type in them
    """

    def __init__(self) -> None:
        self.next_mover_lock = asyncio.Lock()
        self.current_mover_lock = asyncio.Lock()
        self.stop_event = asyncio.Event()

    async def mover_manager(self, mover_coro: Coroutine[None, None, None]) -> None:
        """Make sure that only one mover_coro is active at any time"""
        async with AsyncExitStack() as next_mover_cm:
            await next_mover_cm.enter_async_context(self.next_mover_lock)
            if self.current_mover_lock.locked():
                self.stop_event.set()
            async with self.current_mover_lock:
                if self.stop_event.is_set():
                    self.stop_event.clear()
                await next_mover_cm.aclose()
                await mover_coro

    async def sleep(self, delay):
        """Sleep for delay unless interrupted by a stop_event.  Return False if stopped."""
        try:
            await asyncio.wait_for(self.stop_event.wait(), delay)
            return False
        except asyncio.TimeoutError:
            return True


class TT6CoverEmulator(AsyncObservable):
    """
    Emulate a Cover with a stepper motor that moves at a constant rate

    The step_len is the unit of movement and is specified in metres
    The unadjusted_max_drop is specified in metres (the actual drop will be rounded down to a fixed number of steps)
    The speed is specified in metres/sec
    The initial_pos is specified in thousandths (1000 = fully up; 0 = fully down)
    The inverted_endpoints flag can be set if the position is reported with 0 = fully down and 1000 = fully up

    As an example, a screen might have a 2.0m drop and the mask might have a 0.5m drop
    Both covers might move at 0.05 metres/sec in steps of 0.01 metres
    The mask would drop in 10 secs
    The screen would drop in 40 secs
    """

    STEPS_PER_NOTIFICATION = 10

    def __init__(
        self,
        name: str,
        tt_addr: TTBusDeviceAddress,
        step_len: float,
        unadjusted_max_drop: float,
        speed: float,
        initial_pos: int,
        inverted_endpoints: bool = False,
    ) -> None:
        super().__init__()
        self.name = name
        self.tt_addr = tt_addr
        self.step_len = step_len
        self.unadjusted_max_drop = unadjusted_max_drop
        self.max_drop = int(self.unadjusted_max_drop // self.step_len) * self.step_len
        self.pos_increment_per_step = int(
            1000 * self.step_len / self.unadjusted_max_drop
        )
        self.speed = speed
        self.pos = check_pos("intitial_pos", initial_pos)
        self._mover_manager: MoverManager | None = None
        self.presets: Dict[str, int] = {}
        self._secs_per_pos_increment = self.step_len / (
            self.speed * self.pos_increment_per_step
        )
        self.inverted_endpoints = inverted_endpoints

    @property
    def drop(self) -> float:
        if self.inverted_endpoints:
            return self.step_len * self.pos / self.pos_increment_per_step
        else:
            return self.step_len * (1000 - self.pos) / self.pos_increment_per_step

    @property
    def hex_pos(self) -> int:
        return round(self.pos * 0.255)

    def _get_mover_manager(self) -> MoverManager:
        if self._mover_manager is None:
            self._mover_manager = MoverManager()
        return self._mover_manager

    def log_position(self, message: str) -> None:
        _LOGGER.info(f"Pos for {self.name}: pos {self.pos} ({message})")

    async def _move(self, pos_increment: int, notify: bool) -> bool:
        """Move pos by increment.  Return False if stop event received."""
        delay = abs(self._secs_per_pos_increment * pos_increment)
        if await self._get_mover_manager().sleep(delay):
            self.pos += pos_increment
            self.log_position(f"moved {pos_increment}")
            if notify:
                await self.notify_observers()
            return True
        else:
            self.log_position(f"stopped")
            # TODO: Calculate partial move?   Otherwise this isn't needed.
            if notify:
                await self.notify_observers()
            return False

    async def _move_to_pos(self, to_pos: int, notify: bool) -> None:
        if self.pos == to_pos:
            self.log_position("movement not needed")
            return

        self.log_position(f"movement initiated to pos {to_pos}")

        to_move = to_pos - self.pos
        move_per_notification = (
            self.pos_increment_per_step
            * self.STEPS_PER_NOTIFICATION
            * (1 if to_move >= 0 else -1)
        )
        num_notifications = to_move // move_per_notification

        for _ in range(num_notifications):
            if not await self._move(move_per_notification, notify):
                self.log_position(f"movement interrupted at {self.pos}")
                return

        residual_move = to_move - (num_notifications * move_per_notification)
        if residual_move != 0 and not await self._move(residual_move, notify):
            self.log_position(f"movement interrupted at {self.pos}")
            return

        self.log_position(f"movement complete")

    async def move_to_pos(self, to_pos: int) -> None:
        """Move to pos where pos is 0 for fully down to 1000 for fully up"""
        await self._get_mover_manager().mover_manager(self._move_to_pos(to_pos, True))

    async def _move_increment(self, requested_increment: int, notify: bool) -> None:
        """Relative pos movement where positive is up and negative is down"""
        to_pos = self.pos + requested_increment
        if to_pos < 0:
            to_pos = 0
        elif to_pos > 1000:
            to_pos = 1000
        increment = to_pos - self.pos
        if increment != requested_increment:
            self.log_position(
                f"requested relative movement of {requested_increment} limited to {increment}"
            )
        if increment == 0:
            self.log_position(f"relative move not needed - already at {to_pos}")
        else:
            self.log_position(
                f"relative movement of {increment} initiated to position {to_pos}"
            )
            await self._get_mover_manager().mover_manager(
                self._move_to_pos(to_pos, notify)
            )

    async def stop(self) -> None:
        """Stop any movement in progress"""
        self.log_position("stop movement requested")
        await self._get_mover_manager().mover_manager(asyncio.sleep(0))

    async def move_to_hex_pos(self, hex_pos: int) -> None:
        """Move to hex_pos where hex_pos is 0 for fully down to 255 for fully up"""
        if hex_pos < 0 or hex_pos > 255:
            raise ValueError(
                f"Invalid hex_pos specified for cover {self.name}: range is 0 for fully down to 255 for fully up"
            )
        pos = round(hex_pos / 0.255)
        await self.move_to_pos(pos)

    async def move_down(self) -> None:
        """Move to lower limit"""
        await self.move_to_pos(1000 if self.inverted_endpoints else 0)

    async def move_up(self) -> None:
        """Move to upper limit"""
        await self.move_to_pos(0 if self.inverted_endpoints else 1000)

    async def move_down_step(self) -> None:
        direction = 1 if self.inverted_endpoints else -1
        await self._move_increment(direction * self.pos_increment_per_step, False)

    async def move_up_step(self) -> None:
        direction = -1 if self.inverted_endpoints else 1
        await self._move_increment(direction * self.pos_increment_per_step, False)

    def init_preset(self, preset_name: str, pos: int) -> None:
        self.presets[preset_name] = check_pos(preset_name, pos)

    async def move_preset(self, preset_name: str) -> None:
        if preset_name in self.presets:
            await self.move_to_pos(self.presets[preset_name])

    async def store_preset(self, preset_name: str) -> None:
        self.presets[preset_name] = self.pos

    async def del_preset(self, preset_name: str) -> None:
        if preset_name in self.presets:
            del self.presets[preset_name]

    def fmt_pos_msg(self) -> str:
        return f"POS * {self.tt_addr.address:02X} {self.tt_addr.node:02X} {self.pos:04d} FFFF FF"

    def fmt_ack_msg(self, target_pos: int) -> str:
        return f"POS # {self.tt_addr.address:02X} {self.tt_addr.node:02X} {target_pos:04d} FFFF FF"
