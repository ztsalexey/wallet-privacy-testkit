"""Record observable TLS lengths and timing while forwarding bytes unchanged."""

import errno
import json
import selectors
import socket
import socketserver
import threading
import time
from pathlib import Path

TLS_HEADER_BYTES = 5
TLS_MAX_CIPHERTEXT_BYTES = 18_432
TLS_CONTENT_TYPES = frozenset((20, 21, 22, 23, 24))
TLS_APPLICATION_DATA = 23
VALID_DIRECTIONS = ("c2s", "s2c")


class TLSRecordParser:
    """Reassemble visible TLS record headers across arbitrary TCP reads."""

    def __init__(self):
        self.buffer = bytearray()
        self.invalid = False

    def feed(self, payload):
        if self.invalid:
            return []
        self.buffer.extend(payload)
        records = []
        while len(self.buffer) >= TLS_HEADER_BYTES:
            content_type = self.buffer[0]
            major_version = self.buffer[1]
            ciphertext_bytes = int.from_bytes(self.buffer[3:5], "big")
            if (
                content_type not in TLS_CONTENT_TYPES
                or major_version != 3
                or ciphertext_bytes > TLS_MAX_CIPHERTEXT_BYTES
            ):
                self.buffer.clear()
                self.invalid = True
                raise ValueError("stream does not have supported TLS record framing")
            record_bytes = ciphertext_bytes + TLS_HEADER_BYTES
            if len(self.buffer) < record_bytes:
                break
            records.append(
                {"content_type": content_type, "record_bytes": record_bytes}
            )
            del self.buffer[:record_bytes]
        return records


class TraceRecorder:
    """Write metadata-only JSON Lines events to a new file."""

    def __init__(self, path):
        self.path = Path(path)
        self.file = self.path.open("x", encoding="utf-8")
        self.lock = threading.Lock()
        self.connection_count = 0

    def emit(self, event, connection, **fields):
        with self.lock:
            row = {
                "event": event,
                "connection": connection,
                "t_ns": time.monotonic_ns(),
                **fields,
            }
            self.file.write(json.dumps(row, separators=(",", ":")) + "\n")
            self.file.flush()

    def next_connection(self):
        with self.lock:
            self.connection_count += 1
            return self.connection_count

    def close(self):
        with self.lock:
            if not self.file.closed:
                self.file.close()


class TLSForwarder(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = False
    block_on_close = True

    def __init__(self, target, recorder, listen_host="127.0.0.1", listen_port=0):
        self.target = target
        self.recorder = recorder
        self.stopping = threading.Event()
        super().__init__((listen_host, listen_port), _ForwardHandler)
        self.worker = threading.Thread(target=self.serve_forever, daemon=True)
        self.worker.start()

    def close(self):
        self.stopping.set()
        self.shutdown()
        self.server_close()
        self.worker.join()


class _ForwardHandler(socketserver.BaseRequestHandler):
    def handle(self):
        server = self.server
        recorder = server.recorder
        connection = recorder.next_connection()
        recorder.emit("connect", connection)
        try:
            with socket.create_connection(server.target, timeout=5) as upstream:
                endpoints = (self.request, upstream)
                for endpoint in endpoints:
                    endpoint.settimeout(5)
                    endpoint.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                parsers = {direction: TLSRecordParser() for direction in VALID_DIRECTIONS}
                with selectors.DefaultSelector() as selector:
                    selector.register(self.request, selectors.EVENT_READ, (upstream, "c2s"))
                    selector.register(upstream, selectors.EVENT_READ, (self.request, "s2c"))
                    while selector.get_map() and not server.stopping.is_set():
                        for key, _ in selector.select(timeout=0.1):
                            destination, direction = key.data
                            payload = key.fileobj.recv(65_536)
                            if not payload:
                                # TCP EOF closes one direction. The peer can
                                # still return data after receiving that EOF.
                                selector.unregister(key.fileobj)
                                try:
                                    destination.shutdown(socket.SHUT_WR)
                                except OSError as error:
                                    if error.errno != errno.ENOTCONN:
                                        raise
                                continue
                            recorder.emit(
                                "chunk", connection, direction=direction, bytes=len(payload)
                            )
                            try:
                                for record in parsers[direction].feed(payload):
                                    recorder.emit(
                                        "tls_record", connection, direction=direction, **record
                                    )
                            except ValueError:
                                recorder.emit("parse_error", connection, direction=direction)
                            destination.sendall(payload)
        except OSError as error:
            if not server.stopping.is_set():
                recorder.emit(
                    "connection_error", connection, error=type(error).__name__
                )
        finally:
            recorder.emit("close", connection)


def read_trace(path):
    rows = []
    with Path(path).open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON at line {line_number}") from error
            if not isinstance(row, dict) or "event" not in row:
                raise ValueError(f"invalid trace event at line {line_number}")
            rows.append(row)
    if not rows:
        raise ValueError("trace is empty")
    return rows


def summarize_trace(path, require_complete=True):
    events = read_trace(path)
    accounting, open_connections = {}, set()
    previous_time = -1
    for row in events:
        event, connection, timestamp = row['event'], row.get('connection'), row.get('t_ns')
        if type(timestamp) is not int or timestamp < 0 or timestamp < previous_time:
            raise ValueError('trace timestamps must be nonnegative and chronological')
        previous_time = timestamp
        if type(connection) is not int or connection < 0:
            raise ValueError('invalid trace connection identifier')
        if event == 'observation_boundary':
            if connection != 0:
                raise ValueError('observation boundaries must use connection zero')
            continue
        if connection == 0:
            raise ValueError('traffic events require a positive connection identifier')
        if event == 'connect':
            if connection in accounting:
                raise ValueError('duplicate trace connection')
            accounting[connection] = {direction: [0, 0] for direction in VALID_DIRECTIONS}
            open_connections.add(connection)
            continue
        if connection not in open_connections:
            raise ValueError('trace event outside an open connection')
        if event == 'close':
            open_connections.remove(connection)
            continue
        if event == 'connection_error':
            continue
        if event not in ('chunk', 'tls_record', 'parse_error'):
            raise ValueError('unknown trace event')
        direction = row.get('direction')
        if direction not in VALID_DIRECTIONS:
            raise ValueError('invalid trace direction')
        if event == 'parse_error':
            continue
        chunk_bytes, record_bytes = accounting[connection][direction]
        if event == 'chunk':
            size = row.get('bytes')
            if type(size) is not int or size <= 0:
                raise ValueError('chunk size must be a positive integer')
            chunk_bytes += size
        else:
            size, content_type = row.get('record_bytes'), row.get('content_type')
            if (type(size) is not int or not TLS_HEADER_BYTES <= size <= TLS_MAX_CIPHERTEXT_BYTES + TLS_HEADER_BYTES
                    or type(content_type) is not int or content_type not in TLS_CONTENT_TYPES):
                raise ValueError('invalid TLS record observation')
            record_bytes += size
            if record_bytes > chunk_bytes:
                raise ValueError('TLS records exceed captured bytes on their connection')
        accounting[connection][direction] = [chunk_bytes, record_bytes]
    failures = [
        row for row in events if row["event"] in ("parse_error", "connection_error")
    ]
    if failures:
        kinds = sorted({row["event"] for row in failures})
        raise ValueError(f"trace contains capture failures: {', '.join(kinds)}")
    complete = not open_connections and all(
        chunks == records for directions in accounting.values() for chunks, records in directions.values()
    )
    if require_complete:
        for connection, directions in accounting.items():
            for direction, (chunks, records) in directions.items():
                if chunks != records:
                    raise ValueError(f'incomplete {direction} TLS record accounting on connection {connection}: '
                                     f'{chunks} chunk bytes, {records} complete record bytes')
        if open_connections:
            raise ValueError('trace contains unclosed connections; capture may be truncated')
    chunks = [row for row in events if row["event"] == "chunk"]
    records = [row for row in events if row["event"] == "tls_record"]
    if not chunks or not records:
        raise ValueError("trace has no captured TLS traffic")
    totals = {}
    for direction in VALID_DIRECTIONS:
        chunk_bytes = sum(
            row["bytes"] for row in chunks if row.get("direction") == direction
        )
        record_bytes = sum(
            row["record_bytes"]
            for row in records
            if row.get("direction") == direction
        )
        totals[direction] = {
            "chunk_bytes": chunk_bytes,
            "complete_record_bytes": record_bytes,
        }
    application_records = [
        row
        for row in records
        if row.get("direction") == "c2s"
        and row.get("content_type") == TLS_APPLICATION_DATA
    ]
    if not application_records:
        raise ValueError("trace has no client application-data record")
    return {
        "connections": sum(row["event"] == "connect" for row in events),
        "client_bytes": totals["c2s"]["chunk_bytes"],
        "server_bytes": totals["s2c"]["chunk_bytes"],
        "largest_client_application_record": max(
            row["record_bytes"] for row in application_records
        ),
        "complete_tls_records": len(records),
        "complete_accounting": complete,
    }
