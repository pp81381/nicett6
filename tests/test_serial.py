import asyncio
from logging import WARNING
from typing import List, Tuple
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, call, patch

from nicett6.consts import RCV_EOL, SEND_EOL
from nicett6.serial import SerialConnection, SerialProtocol, SerialReader, SerialWriter


class MessageAccumulator:
    def __init__(self) -> None:
        self.received: List[bytes] = []

    async def accumulate(self, conn: SerialConnection[bytes]):
        reader = conn.add_reader()
        async for msg in reader:
            self.received.append(msg)


def mock_csc_return_value(
    *args, **kwargs
) -> Tuple[asyncio.Transport, SerialProtocol[bytes]]:
    """returns mock transport and SerialProtocol in args[1]"""
    transport = AsyncMock(spec=asyncio.Transport)
    transport.is_closing.return_value = False
    protocol: SerialProtocol[bytes] = args[1]()
    protocol.connection_made(transport)
    return transport, protocol


class TestConnection(IsolatedAsyncioTestCase):
    def setUp(self):
        patcher = patch(
            "nicett6.serial.create_serial_connection",
            side_effect=mock_csc_return_value,
        )
        self.addCleanup(patcher.stop)
        self.mock_csc = patcher.start()

    async def test_conn(self):
        conn = SerialConnection[bytes](
            lambda x: x,
            RCV_EOL,
            SerialReader[bytes],
            SerialWriter,
            0.05,
        )
        await conn.connect()
        self.mock_csc.assert_called_once()
        self.assertTrue(conn.is_connected)
        p = conn._protocol
        assert p is not None
        self.assertIsInstance(p, SerialProtocol)
        t = p._transport
        assert t is not None
        self.assertIsInstance(t, asyncio.Transport)
        self.assertEqual(p.buf.eol, RCV_EOL)
        conn.close()
        self.assertFalse(conn.is_connected)
        assert isinstance(t, AsyncMock)
        t.close.assert_called_once_with()


class TestReaderAndWriter(IsolatedAsyncioTestCase):
    DATA_RECEIVED12 = b"TEST MESSAGE 1" + RCV_EOL + b"TEST MESSAGE 2" + RCV_EOL
    DATA_RECEIVED56 = b"TEST MESSAGE 5" + RCV_EOL + b"TEST MESSAGE 6" + RCV_EOL
    EXPECTED_MESSAGES12 = [
        b"TEST MESSAGE 1" + RCV_EOL,
        b"TEST MESSAGE 2" + RCV_EOL,
    ]
    EXPECTED_MESSAGES1256 = [
        b"TEST MESSAGE 1" + RCV_EOL,
        b"TEST MESSAGE 2" + RCV_EOL,
        b"TEST MESSAGE 5" + RCV_EOL,
        b"TEST MESSAGE 6" + RCV_EOL,
    ]
    TEST_MESSAGE = b"TEST MESSAGE" + SEND_EOL

    async def asyncSetUp(self) -> None:
        patcher = patch(
            "nicett6.serial.create_serial_connection",
            side_effect=mock_csc_return_value,
        )
        self.addCleanup(patcher.stop)
        self.mock_csc = patcher.start()
        self.conn = SerialConnection[bytes](
            lambda x: x,
            RCV_EOL,
            SerialReader[bytes],
            SerialWriter,
            0.05,
        )
        await self.conn.connect()

    def tearDown(self) -> None:
        self.conn.close()

    @property
    def protocol(self) -> SerialProtocol[bytes]:
        assert self.conn._protocol is not None
        return self.conn._protocol

    @property
    def mocktransport(self) -> AsyncMock:
        transport = self.protocol._transport
        assert transport is not None
        assert isinstance(transport, AsyncMock)
        return transport

    async def test_no_readers(self):
        reader = self.conn.add_reader()
        self.protocol.data_received(self.DATA_RECEIVED12)
        # The messages are just eaten
        self.assertEqual(len(self.protocol.buf.buf), 0)

    async def test_one_reader(self):
        reader = self.conn.add_reader()
        self.protocol.data_received(self.DATA_RECEIVED12)
        self.conn.close()
        messages = [msg async for msg in reader]
        self.assertEqual(messages, self.EXPECTED_MESSAGES12)

    async def test_one_reader_twice(self):
        reader = self.conn.add_reader()
        self.protocol.data_received(self.DATA_RECEIVED12)
        self.conn.close()
        messages = [msg async for msg in reader]
        self.assertEqual(messages, self.EXPECTED_MESSAGES12)
        with self.assertRaises(RuntimeError):
            messages = [msg async for msg in reader]

    async def test_two_readers(self):
        readers = [self.conn.add_reader(), self.conn.add_reader()]
        self.protocol.data_received(self.DATA_RECEIVED12)
        self.conn.close()
        messages0 = [msg async for msg in readers[0]]
        self.assertEqual(messages0, self.EXPECTED_MESSAGES12)
        messages1 = [msg async for msg in readers[1]]
        self.assertEqual(messages1, self.EXPECTED_MESSAGES12)

    async def test_reconnect(self):
        msgs = MessageAccumulator()
        task = asyncio.create_task(msgs.accumulate(self.conn))
        await asyncio.sleep(0)  # Allow the reader to be added
        self.protocol.data_received(self.DATA_RECEIVED12)
        self.conn.disconnect()
        self.assertIsNone(self.conn._protocol)
        await self.conn.connect()
        self.protocol.data_received(self.DATA_RECEIVED56)
        self.conn.close()
        await task
        self.assertEqual(msgs.received, self.EXPECTED_MESSAGES1256)

    async def test_writer(self):
        writer = self.conn.get_writer()
        await writer.write(self.TEST_MESSAGE)
        self.mocktransport.write.assert_called_once_with(self.TEST_MESSAGE)

    async def test_multiple_writes(self):
        log = MagicMock()

        original_sleep = asyncio.sleep

        async def sleep_side_effect(delay):
            # If the lock isn't working then this will allow a message to be written
            # Not sure that this is needed anymore
            await original_sleep(0)
            log("sleep", delay)

        def write_side_effect(msg):
            log("write", msg)

        self.mocktransport.write.side_effect = write_side_effect

        writer = self.conn.get_writer()
        with patch("asyncio.sleep", side_effect=sleep_side_effect):
            await asyncio.wait(
                {
                    asyncio.create_task(writer.write(self.TEST_MESSAGE)),
                    asyncio.create_task(writer.write(self.TEST_MESSAGE)),
                    asyncio.create_task(writer.write(self.TEST_MESSAGE)),
                    asyncio.create_task(writer.write(self.TEST_MESSAGE)),
                    asyncio.create_task(writer.write(self.TEST_MESSAGE)),
                }
            )

        log.assert_has_calls(
            [
                call("write", self.TEST_MESSAGE),
                call("sleep", 0.05),
                call("write", self.TEST_MESSAGE),
                call("sleep", 0.05),
                call("write", self.TEST_MESSAGE),
                call("sleep", 0.05),
                call("write", self.TEST_MESSAGE),
                call("sleep", 0.05),
                call("write", self.TEST_MESSAGE),
            ]
        )

    async def test_disconnected_writer(self):
        self.conn.disconnect()
        writer = self.conn.get_writer()
        with self.assertLogs("nicett6.serial", level=WARNING) as cm:
            await writer.write(self.TEST_MESSAGE)
        self.assertEqual(
            cm.output,
            [
                "WARNING:nicett6.serial:Message not written (not connected): b'TEST MESSAGE\\r\\n'",
            ],
        )

    async def test_process_request(self):
        dummy_request = b"DUMMY MESSAGE" + SEND_EOL
        data1 = b"RESPONSE" + RCV_EOL
        data2 = b"OTHER STUFF" + RCV_EOL
        data3 = b"MORE STUFF" + RCV_EOL
        writer = self.conn.get_writer()
        coro = writer.write(dummy_request)
        task = asyncio.create_task(self.conn.process_request(coro))
        await asyncio.sleep(0)  # Let the task create the reader
        self.protocol.data_received(data1 + data2)
        await asyncio.sleep(0.1)
        self.protocol.data_received(data3)
        messages = await task
        self.mocktransport.write.assert_called_once_with(dummy_request)
        self.assertEqual(messages, [data1, data2, data3])
