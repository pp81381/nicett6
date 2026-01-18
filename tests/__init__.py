from asyncio import Event
from asyncio import sleep as asyncio_sleep
from unittest.mock import AsyncMock, MagicMock

from nicett6.tt6_connection import TT6Connection, TT6Reader, TT6Writer


def make_mock_conn(reader_return_value) -> AsyncMock:
    mock_reader = AsyncMock(name="reader", spec=TT6Reader)
    mock_reader.__aiter__.return_value = reader_return_value

    mock_writer = AsyncMock(name="writer", spec=TT6Writer)

    conn = AsyncMock(name="connection", spec=TT6Connection)
    conn.add_reader = MagicMock(return_value=mock_reader)
    conn.get_writer = MagicMock(return_value=mock_writer)
    conn.remove_reader = MagicMock()
    conn.close = MagicMock()
    return conn


class MockSleepManual:
    def __init__(self) -> None:
        self.event: Event = Event()

    async def sleep(self, delay: float) -> None:
        await self.event.wait()
        self.event.clear()
        await asyncio_sleep(0)

    async def wake(self) -> None:
        self.event.set()
        await asyncio_sleep(0)


class MockSleepInstant:
    def __init__(self) -> None:
        self.base: float = 0.0
        self.offset: float = 0.0

    async def sleep(self, secs: float):
        # Take care - can't cope with concurrent sleeps so use precisely
        self.base += 0.001  # Time needs to move forwards
        self.offset += secs
        await asyncio_sleep(0)

    def perf_counter(self) -> float:
        return self.base + self.offset
