import json
import socket
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path

from wallet_privacy_testkit.capture import (
    TLSForwarder,
    TLSRecordParser,
    TraceRecorder,
    summarize_trace,
)


class _EchoHandler(socketserver.BaseRequestHandler):
    def handle(self):
        payload = self.request.recv(65_536)
        self.request.sendall(payload)


class CaptureTests(unittest.TestCase):
    def test_parser_handles_fragmented_and_coalesced_records(self):
        first = b"\x17\x03\x03\x00\x03abc"
        second = b"\x16\x03\x03\x00\x02de"
        parser = TLSRecordParser()
        self.assertEqual(parser.feed(first[:2]), [])
        self.assertEqual(
            parser.feed(first[2:] + second[:6]),
            [{"content_type": 23, "record_bytes": 8}],
        )
        self.assertEqual(
            parser.feed(second[6:]), [{"content_type": 22, "record_bytes": 7}]
        )
        self.assertEqual(parser.buffer, b"")

    def test_parser_rejects_non_tls_input(self):
        with self.assertRaisesRegex(ValueError, "TLS record framing"):
            TLSRecordParser().feed(b"GET / HTTP/1.1\r\n")

    def test_forwarder_preserves_bytes_and_records_only_metadata(self):
        upstream = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _EchoHandler)
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                trace = Path(directory) / "trace.jsonl"
                recorder = TraceRecorder(trace)
                forwarder = TLSForwarder(upstream.server_address, recorder)
                payload = b"\x17\x03\x03\x00\x06secret"
                try:
                    with socket.create_connection(forwarder.server_address) as client:
                        client.sendall(payload)
                        self.assertEqual(client.recv(65_536), payload)
                finally:
                    forwarder.close()
                    recorder.close()
                summary = summarize_trace(trace)
                self.assertEqual(summary["client_bytes"], len(payload))
                self.assertEqual(summary["server_bytes"], len(payload))
                self.assertEqual(summary["largest_client_application_record"], len(payload))
                self.assertTrue(summary["complete_accounting"])
                self.assertNotIn("secret", trace.read_text())
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join()

    def test_summary_rejects_incomplete_accounting(self):
        rows = [
            {"event": "connect", "connection": 1, "t_ns": 1},
            {
                "event": "chunk",
                "connection": 1,
                "t_ns": 2,
                "direction": "c2s",
                "bytes": 10,
            },
            {
                "event": "tls_record",
                "connection": 1,
                "t_ns": 3,
                "direction": "c2s",
                "content_type": 23,
                "record_bytes": 9,
            },
            {
                "event": "chunk",
                "connection": 1,
                "t_ns": 4,
                "direction": "s2c",
                "bytes": 5,
            },
            {
                "event": "tls_record",
                "connection": 1,
                "t_ns": 5,
                "direction": "s2c",
                "content_type": 23,
                "record_bytes": 5,
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.jsonl"
            trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "incomplete c2s"):
                summarize_trace(trace)


if __name__ == "__main__":
    unittest.main()
