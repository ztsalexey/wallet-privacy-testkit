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


class _RespondAfterEOF(socketserver.BaseRequestHandler):
    def handle(self):
        payload = bytearray()
        while chunk := self.request.recv(65_536):
            payload.extend(chunk)
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

    def test_half_close_preserves_the_peer_response(self):
        upstream = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _RespondAfterEOF)
        worker = threading.Thread(target=upstream.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                trace = Path(directory) / "trace.jsonl"
                recorder = TraceRecorder(trace)
                forwarder = TLSForwarder(upstream.server_address, recorder)
                payload = b"\x17\x03\x03\x00\x06secret"
                try:
                    with socket.create_connection(forwarder.server_address, timeout=3) as client:
                        client.sendall(payload)
                        client.shutdown(socket.SHUT_WR)
                        received = bytearray()
                        while chunk := client.recv(65_536):
                            received.extend(chunk)
                        self.assertEqual(received, payload)
                finally:
                    forwarder.close()
                    recorder.close()
                summary = summarize_trace(trace)
                self.assertEqual(summary['client_bytes'], len(payload))
                self.assertEqual(summary['server_bytes'], len(payload))
                self.assertTrue(summary['complete_accounting'])
        finally:
            upstream.shutdown()
            upstream.server_close()
            worker.join()

    def test_summary_rejects_invalid_and_cross_connection_accounting(self):
        valid = [
            {'event': 'connect', 'connection': 1, 't_ns': 0},
            {'event': 'chunk', 'connection': 1, 't_ns': 1, 'direction': 'c2s', 'bytes': 20},
            {'event': 'tls_record', 'connection': 1, 't_ns': 2, 'direction': 'c2s',
             'content_type': 23, 'record_bytes': 20},
            {'event': 'close', 'connection': 1, 't_ns': 3},
        ]
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / 'trace.jsonl'
            def write(rows):
                trace.write_text(''.join(json.dumps(row) + '\n' for row in rows))

            write(valid)
            self.assertTrue(summarize_trace(trace)['complete_accounting'])
            mutations = [
                lambda rows: rows[0].update(t_ns=-1),
                lambda rows: rows[1].update(t_ns=True),
                lambda rows: rows[1].update(direction='unknown'),
                lambda rows: rows[1].update(bytes=-20),
                lambda rows: rows[2].update(content_type=999),
                lambda rows: rows[2].update(record_bytes=20.0),
                lambda rows: rows[2].update(connection=2),
                lambda rows: rows[2].update(t_ns=0),
                lambda rows: rows[3].update(event='unrecognized'),
                lambda rows: rows.pop(0),
            ]
            for mutate in mutations:
                with self.subTest(mutation=mutate):
                    rows = [dict(row) for row in valid]
                    mutate(rows)
                    write(rows)
                    with self.assertRaises(ValueError):
                        summarize_trace(trace)
            # These two streams total 40 chunk and record bytes, but one
            # stream is incomplete and the other contains an orphan record.
            rows = [dict(row) for row in valid]
            rows[2]['record_bytes'] = 10
            second = [dict(row, connection=2, t_ns=row['t_ns'] + 4) for row in valid]
            second[2]['record_bytes'] = 30
            write(rows + second)
            with self.assertRaises(ValueError):
                summarize_trace(trace)

            write(valid[:-1])
            with self.assertRaisesRegex(ValueError, 'unclosed'):
                summarize_trace(trace)
            self.assertFalse(summarize_trace(trace, require_complete=False)['complete_accounting'])


if __name__ == "__main__":
    unittest.main()
