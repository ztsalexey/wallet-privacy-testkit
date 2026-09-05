import argparse
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from wallet_privacy_testkit.cli import _fault_relay, _listen_port, _port


class CliTests(unittest.TestCase):
    def test_target_port_range(self):
        self.assertEqual(_port("1"), 1)
        self.assertEqual(_port("65535"), 65_535)
        for value in ("0", "65536", "-1"):
            with self.assertRaises(argparse.ArgumentTypeError):
                _port(value)

    def test_ephemeral_listen_port(self):
        self.assertEqual(_listen_port("0"), 0)
        with self.assertRaises(argparse.ArgumentTypeError):
            _listen_port("65536")

    def test_existing_event_output_is_rejected_before_relay_start(self):
        with tempfile.TemporaryDirectory() as directory:
            events = Path(directory) / "events.json"
            events.write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                _fault_relay(SimpleNamespace(events=events))


if __name__ == "__main__":
    unittest.main()
