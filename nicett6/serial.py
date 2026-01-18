import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Awaitable, Callable, Generic, List, Optional, TypeVar
from weakref import WeakSet

from serial_asyncio_fast import create_serial_connection  # type: ignore[import-untyped]

from nicett6.buffer import MessageBuffer

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class SerialReaderStopSentinel:
    pass


class SerialReader(AsyncIterator[T]):
    """Generic class for Readers"""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[T | SerialReaderStopSentinel] = asyncio.Queue()
        self.is_stopped: bool = False
        self.is_iterated: bool = False

    def message_received(self, msg: T) -> None:
        if not self.is_stopped:
            self.queue.put_nowait(msg)

    def stop(self) -> None:
        if not self.is_stopped:
            self.is_stopped = True
            self.queue.put_nowait(SerialReaderStopSentinel())

    def __aiter__(self) -> AsyncIterator[T]:
        return self

    async def __anext__(self) -> T:
        if self.is_iterated:
            raise RuntimeError("Reader cannot be iterated twice")
        item = await self.queue.get()
        if isinstance(item, SerialReaderStopSentinel):
            self.is_iterated = True
            raise StopAsyncIteration
        return item


class SerialWriter(Generic[T]):
    """Base class for Writers"""

    def __init__(self, conn: "SerialConnection[T]") -> None:
        self.conn = conn

    async def write(self, msg: bytes) -> None:
        await self.conn.write(msg)


class ReaderManager(Generic[T]):
    """
    Keeps track of all of the readers and interfaces them with the Protocol

    Decouples readers from the protocol to simplify reconnection
    Readers survive a disconnection - they are stopped when the session ends
    """

    def __init__(self, decoder: Callable[[bytes], T]) -> None:
        self.decoder = decoder
        self.readers: WeakSet[SerialReader[T]] = WeakSet()

    def add_reader(self, reader: SerialReader[T]) -> None:
        self.readers.add(reader)

    def remove_reader(self, reader: SerialReader[T]) -> None:
        reader.stop()
        self.readers.remove(reader)

    def message_received(self, msg: bytes) -> None:
        _LOGGER.debug(f"data_received: %r", msg)
        decoded_message = self.decoder(msg)
        _LOGGER.debug(f"decoded message: %r", decoded_message)
        for r in self.readers:
            r.message_received(decoded_message)

    def remove_all(self) -> None:
        for r in self.readers:
            r.stop()
        self.readers.clear()


class SerialProtocol(asyncio.Protocol, Generic[T]):
    def __init__(
        self,
        eol: bytes,
        readers: ReaderManager[T],
        post_write_delay: float,
    ) -> None:
        self.readers = readers
        self.buf: MessageBuffer = MessageBuffer(eol)
        self._transport: Optional[asyncio.Transport] = None
        self.send_lock = asyncio.Lock()
        self.post_write_delay = post_write_delay
        self.connection_made_event = asyncio.Event()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        _LOGGER.info("Connection made")
        assert isinstance(transport, asyncio.Transport)
        self._transport = transport
        self.connection_made_event.set()

    def data_received(self, data: bytes) -> None:
        messages: List[bytes] = self.buf.append_chunk(data)
        for msg in messages:
            self.readers.message_received(msg)

    def connection_lost(self, exc: Exception | None) -> None:
        if self.buf.buf != b"":
            _LOGGER.warn(
                "Connection lost with partial message in buffer: %r", self.buf.buf
            )
        else:
            _LOGGER.info("Connection lost")
        self._transport = None

    @property
    def is_open(self):
        return self._transport is not None and not self._transport.is_closing()

    async def write(self, msg: bytes) -> bool:
        if self._transport is None or self._transport.is_closing():
            return False
        async with self.send_lock:
            _LOGGER.debug(f"Writing message {msg!r}")
            self._transport.write(msg)
            await asyncio.sleep(self.post_write_delay)
        return True

    def close_transport(self) -> None:
        if self._transport is not None:
            _LOGGER.debug("Closing transport")
            self._transport.close()
            self._transport = None
        else:
            _LOGGER.debug("Transport already closed")


class SerialConnection(Generic[T]):
    """
    Manages a serial connection

    The lifecycle of the connection is managed by the client
    as opposed to closing upon receipt of an EOF from the device
    If the connection is disconnected then readers wait for the
    next message and writers will discard any messages sent
    Once the connection is re-connected then normal service resumes
    The client can terminate the connection by calling close
    """

    def __init__(
        self,
        decoder: Callable[[bytes], T],
        eol: bytes,
        reader_factory: Callable[[], SerialReader[T]],
        writer_factory: Callable[["SerialConnection[T]"], SerialWriter[T]],
        post_write_delay: float,
        **serial_kwargs,
    ) -> None:
        self.decoder = decoder
        self.eol = eol
        self.reader_factory = reader_factory
        self.writer_factory = writer_factory
        self.post_write_delay = post_write_delay
        self.serial_kwargs = serial_kwargs
        self._protocol: Optional[SerialProtocol[T]] = None
        self._readers: ReaderManager[T] = ReaderManager(decoder)

    @property
    def is_connected(self) -> bool:
        return self._protocol is not None

    async def connect(self) -> None:
        self.disconnect()
        loop = asyncio.get_running_loop()
        protocol = SerialProtocol(self.eol, self._readers, self.post_write_delay)
        await create_serial_connection(loop, lambda: protocol, **self.serial_kwargs)
        await protocol.connection_made_event.wait()
        self._protocol = protocol

    def disconnect(self):
        if self._protocol is not None:
            self._protocol.close_transport()
            self._protocol = None

    def close(self) -> None:
        self._readers.remove_all()
        self.disconnect()

    def add_reader(self) -> SerialReader[T]:
        reader = self.reader_factory()
        self._readers.add_reader(reader)
        return reader

    def remove_reader(self, reader: SerialReader[T]) -> None:
        self._readers.remove_reader(reader)
        reader.stop()

    def get_writer(self) -> SerialWriter[T]:
        return self.writer_factory(self)

    async def write(self, msg: bytes) -> None:
        if self._protocol is not None and self._protocol.is_open:
            await self._protocol.write(msg)
        else:
            _LOGGER.warning(f"Message not written (not connected): {msg!r}")

    async def process_request(self, coro: Awaitable[None], time_window: float = 1.0):
        """
        Send a command and collect the response messages that arrive in time_window

        Usage:
             coro = writer.write("DO SOMETHING")
             messages = await writer.process_request(coro)

        Note that there could be unrelated messages received if web commands are on
        or if another command has just been submitted
        """
        reader: SerialReader[T] = self.add_reader()
        await coro
        await asyncio.sleep(time_window)
        self.remove_reader(reader)
        return [msg async for msg in reader]
