from contextlib import redirect_stderr
from io import StringIO
from unittest import TestCase
from unittest.mock import mock_open, patch

from nicett6.emulator.config import build_config, default_config_file
from nicett6.emulator.controller.line_handler import PRESET_POS_5


class TestConfig(TestCase):
    def setUp(self):
        self.filename = default_config_file()

    def test_build_config1(self):
        config = build_config(["-f", self.filename])
        self.assertEqual(config["port"], 50200)
        self.assertEqual(config["web_on"], False)
        self.assertEqual(len(config["covers"]), 4)
        screen = config["covers"][0]
        self.assertEqual(screen.name, "screen")
        self.assertAlmostEqual(screen.step_len, 0.01)
        self.assertAlmostEqual(screen.unadjusted_max_drop, 1.77)
        self.assertAlmostEqual(screen.speed, 0.08)
        self.assertAlmostEqual(screen.pos, 1000)
        self.assertFalse(screen.inverted_endpoints)
        mask = config["covers"][1]
        self.assertEqual(mask.name, "mask")
        self.assertFalse(mask.inverted_endpoints)
        blind = config["covers"][2]
        self.assertEqual(blind.name, "blind")
        self.assertFalse(blind.inverted_endpoints)
        inverse_blind = config["covers"][3]
        self.assertEqual(inverse_blind.name, "inverse blind")
        self.assertTrue(inverse_blind.inverted_endpoints)

    def test_build_config2(self):
        config = build_config(["-f", self.filename, "-w", "-p", "50300"])
        self.assertEqual(config["web_on"], True)
        self.assertEqual(config["port"], 50300)

    def test_build_config3(self):
        config = build_config(["-f", self.filename, "-i", "screen", "750"])
        self.assertEqual(len(config["covers"]), 4)
        screen = config["covers"][0]
        self.assertAlmostEqual(screen.pos, 750)

    def test_build_config4(self):
        """Test web_on=true, preset_pos_5 set in config file"""
        test_json = """
        {
            "web_on": true,
            "covers": [
                {
                    "address": 2,
                    "node": 4,
                    "name": "screen",
                    "step_len": 0.01,
                    "max_drop": 1.77,
                    "speed": 0.08,
                    "pos": 1000,
                    "preset_pos_5": 500
                }
            ]
        }
        """
        with patch("nicett6.emulator.config.open", mock_open(read_data=test_json)) as m:
            dummy_filename = "dummy"
            config = build_config(["-f", dummy_filename])
            m.assert_called_once_with(dummy_filename)
            self.assertEqual(config["port"], 50200)
            self.assertEqual(config["web_on"], True)
            self.assertEqual(len(config["covers"]), 1)
            screen = config["covers"][0]
            self.assertEqual(screen.name, "screen")
            self.assertAlmostEqual(screen.step_len, 0.01)
            self.assertAlmostEqual(screen.unadjusted_max_drop, 1.77)
            self.assertAlmostEqual(screen.speed, 0.08)
            self.assertEqual(screen.pos, 1000)
            self.assertEqual(len(screen.presets), 1)
            self.assertEqual(screen.presets[PRESET_POS_5], 500)

    def test_build_config5a(self):
        """Test web_on config"""
        test_json = """{"web_on": true}"""
        with patch("nicett6.emulator.config.open", mock_open(read_data=test_json)):
            config = build_config([])
            self.assertEqual(config["web_on"], True)

    def test_build_config5b(self):
        """Test web_on config"""
        test_json = """{"web_on": false}"""
        with patch("nicett6.emulator.config.open", mock_open(read_data=test_json)):
            config = build_config([])
            self.assertEqual(config["web_on"], False)

    def test_build_config5c(self):
        """Test --web_on override"""
        test_json = """{"web_on": false}"""
        with patch("nicett6.emulator.config.open", mock_open(read_data=test_json)):
            config = build_config(["-w"])
            self.assertEqual(config["web_on"], True)

    def test_build_config5d(self):
        """Test --web_off override"""
        test_json = """{"web_on": true}"""
        with patch("nicett6.emulator.config.open", mock_open(read_data=test_json)):
            config = build_config(["-W"])
            self.assertEqual(config["web_on"], False)

    def test_build_config5e(self):
        """Test combination of --web_off and --web_on override"""
        test_json = """{"web_on": false}"""
        with patch("nicett6.emulator.config.open", mock_open(read_data=test_json)):
            config = build_config(["-W", "-w"])
            self.assertEqual(config["web_on"], True)

    def test_build_config5f(self):
        """Test combination of --web_on and --web_off override"""
        test_json = """{"web_on": true}"""
        with patch("nicett6.emulator.config.open", mock_open(read_data=test_json)):
            config = build_config(["-w", "-W"])
            self.assertEqual(config["web_on"], False)

    def test_build_config_err1(self):
        ioerr = StringIO()
        with redirect_stderr(ioerr):
            with self.assertRaises(SystemExit):
                build_config(["-f", self.filename, "-i", "screen", "xyz"])
            expected_message = "error: Invalid value specified for screen: xyz\n"
            message = ioerr.getvalue()[-len(expected_message) :]
            self.assertEqual(expected_message, message)

    def test_build_config_err2(self):
        ioerr = StringIO()
        with redirect_stderr(ioerr):
            with self.assertRaises(SystemExit):
                build_config(["-f", self.filename, "-i", "screen", "1010"])
            expected_message = "error: Invalid initial_pos specified for screen (range is 0 for fully down to 1000 for fully up)\n"
            message = ioerr.getvalue()[-len(expected_message) :]
            self.assertEqual(expected_message, message)

    def test_build_config_err3(self):
        ioerr = StringIO()
        with redirect_stderr(ioerr):
            with self.assertRaises(SystemExit):
                build_config(["-f", self.filename, "-i", "screen2", "0.0"])
            expected_message = "error: Invalid cover_name: screen2\n"
            message = ioerr.getvalue()[-len(expected_message) :]
            self.assertEqual(expected_message, message)
