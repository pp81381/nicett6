from unittest import IsolatedAsyncioTestCase, TestCase

from nicett6.utils import (
    async_get_platform_serial_port,
    check_aspect_ratio,
    get_platform_serial_port,
    hex_arg_to_int,
    pct_arg_to_int,
)


class TestValidationAndConversion(TestCase):
    def test_hex_arg(self):
        self.assertEqual(hex_arg_to_int("00"), 0)
        self.assertEqual(hex_arg_to_int("10"), 16)
        self.assertEqual(hex_arg_to_int("1A"), 26)
        self.assertEqual(hex_arg_to_int("FF"), 255)
        with self.assertRaises(ValueError):
            hex_arg_to_int("")
        with self.assertRaises(ValueError):
            hex_arg_to_int("2")
        with self.assertRaises(ValueError):
            hex_arg_to_int("YY")
        with self.assertRaises(ValueError):
            hex_arg_to_int("100")

    def test_hex_arg_variable(self):
        self.assertEqual(hex_arg_to_int("A", False), 10)
        self.assertEqual(hex_arg_to_int("0A", False), 10)

    def test_pct_arg(self):
        self.assertEqual(pct_arg_to_int("0000"), 0)
        self.assertEqual(pct_arg_to_int("0500"), 500)
        self.assertEqual(pct_arg_to_int("1000"), 1000)
        self.assertEqual(pct_arg_to_int("0999"), 999)
        with self.assertRaises(ValueError):
            pct_arg_to_int("")
        with self.assertRaises(ValueError):
            pct_arg_to_int("FFFF")
        with self.assertRaises(ValueError):
            pct_arg_to_int("01000")

    def test_check_aspect_ratio(self):
        check_aspect_ratio(16 / 9)
        check_aspect_ratio(4 / 3)
        check_aspect_ratio(2.35)
        check_aspect_ratio(2.78)
        check_aspect_ratio(9 / 16)
        with self.assertRaises(ValueError):
            check_aspect_ratio(0.001)
        with self.assertRaises(ValueError):
            check_aspect_ratio(4)


class TestGetSerial(IsolatedAsyncioTestCase):
    def setUp(self):
        self.serial_port = get_platform_serial_port()

    async def test1(self):
        serial_port = await async_get_platform_serial_port()
        self.assertEqual(serial_port, self.serial_port)
