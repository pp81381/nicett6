import asyncio
from typing import Tuple
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from nicett6.command_code import CommandCode
from nicett6.connection import TT6Connection, TT6Writer, open_connection
from nicett6.consts import RCV_EOL
from nicett6.decode import AckResponse, ResponseMessageType
from nicett6.multiplexer import MultiplexerProtocol, MultiplexerSerialConnection
from nicett6.ttbus_device import TTBusDeviceAddress


def mock_csc_return_value(
    *args, **kwargs
) -> Tuple[asyncio.Transport, MultiplexerProtocol[bytes]]:
    """returns mock transport and the MultiPlexerProtocol in args[1]"""
    transport = AsyncMock(spec=asyncio.Transport)
    transport.is_closing.return_value = False
    protocol: MultiplexerProtocol[bytes] = args[1]()
    protocol.connection_made(transport)
    return transport, protocol


class TestReaderAndWriter(IsolatedAsyncioTestCase):
    def setUp(self):
        patcher = patch(
            "nicett6.multiplexer.create_serial_connection",
            side_effect=mock_csc_return_value,
        )
        self.addCleanup(patcher.stop)
        self.mock_csc = patcher.start()

    @staticmethod
    def get_protocol(
        conn: TT6Connection,
    ) -> MultiplexerProtocol[ResponseMessageType]:
        assert conn._conn._protocol is not None
        return conn._conn._protocol

    @classmethod
    def get_transport(cls, conn: TT6Connection) -> asyncio.Transport:
        transport = cls.get_protocol(conn)._transport
        assert transport is not None
        return transport

    async def test_reader(self):
        async with open_connection() as conn:
            reader = conn.add_reader()
            self.get_protocol(conn).data_received(b"RSP 3 4 11" + RCV_EOL)
            conn.close()
            messages = [msg async for msg in reader]
            self.assertEqual(len(messages), 1)
            res = messages[0]
            self.assertIsInstance(res, AckResponse)
            assert isinstance(res, AckResponse)
            self.assertEqual(res.tt_addr, TTBusDeviceAddress(0x03, 0x04))
            self.assertEqual(res.cmd_code, CommandCode.MOVE_POS_6)

    async def test_writer(self):
        async with open_connection() as conn:
            writer = conn.get_writer()
            assert isinstance(writer, TT6Writer)
            await writer.send_web_on()
            self.get_transport(conn).write.assert_called_once_with(b"WEB_ON" + RCV_EOL)


class TestOpenConnection(IsolatedAsyncioTestCase):
    async def test1(self):
        with patch("nicett6.connection.open", side_effect=ValueError("Test")):
            with self.assertRaises(ValueError):
                async with open_connection():
                    pass
