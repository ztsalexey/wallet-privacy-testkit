"""Local TCP stream conditioning, not a packet-level WAN emulator."""
import errno
import random
import socket
import socketserver
import threading
import time


class StreamConditioner(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = False

    def __init__(self, target, *, delay_ms=0, jitter_ms=0, bytes_per_second=0):
        self.target = target
        self.delay_ms, self.jitter_ms, self.bytes_per_second = delay_ms, jitter_ms, bytes_per_second
        self.stopping = threading.Event()
        self.errors = []
        super().__init__(('127.0.0.1', 0), Handler)
        self.worker = threading.Thread(target=self.serve_forever, daemon=True)
        self.worker.start()

    def close(self):
        self.stopping.set()
        self.shutdown()
        self.server_close()
        self.worker.join()


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        server = self.server
        try:
            with socket.create_connection(server.target, timeout=5) as upstream:
                def copy(source, destination, seed):
                    rng = random.Random(seed)
                    source.settimeout(0.2)
                    try:
                        while not server.stopping.is_set():
                            try:
                                data = source.recv(16384)
                            except socket.timeout:
                                continue
                            if not data:
                                try:
                                    destination.shutdown(socket.SHUT_WR)
                                except OSError as error:
                                    if error.errno != errno.ENOTCONN:
                                        raise
                                return
                            delay = max(0, server.delay_ms + rng.uniform(-server.jitter_ms, server.jitter_ms)) / 1000
                            if server.bytes_per_second:
                                delay += len(data) / server.bytes_per_second
                            if server.stopping.wait(delay):
                                return
                            destination.sendall(data)
                    except OSError as error:
                        if not server.stopping.is_set() and not isinstance(error, (BrokenPipeError, ConnectionResetError)):
                            server.errors.append(f'{type(error).__name__}:{error.errno}')
                first = threading.Thread(target=copy, args=(self.request, upstream, 1))
                second = threading.Thread(target=copy, args=(upstream, self.request, 2))
                first.start(); second.start()
                first.join(); second.join()
        except OSError as error:
            if not server.stopping.is_set():
                server.errors.append(type(error).__name__)
