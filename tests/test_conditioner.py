import importlib.util
import socket
import socketserver
import threading
import time
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('lab_network', Path(__file__).resolve().parents[1] / 'examples/regtest/network.py')
network = importlib.util.module_from_spec(spec); spec.loader.exec_module(network)


class Echo(socketserver.BaseRequestHandler):
    def handle(self):
        while data := self.request.recv(8192): self.request.sendall(data)


class ConditionerTests(unittest.TestCase):
    def test_delayed_paced_stream_preserves_bytes_and_half_close(self):
        server=socketserver.ThreadingTCPServer(('127.0.0.1',0),Echo)
        worker=threading.Thread(target=server.serve_forever); worker.start()
        conditioner=network.StreamConditioner(server.server_address,delay_ms=10,jitter_ms=2,bytes_per_second=10000)
        try:
            payload=bytes(range(256))*4
            started=time.monotonic()
            with socket.create_connection(conditioner.server_address,timeout=5) as client:
                client.sendall(payload); client.shutdown(socket.SHUT_WR)
                result=bytearray()
                while chunk:=client.recv(8192): result.extend(chunk)
            self.assertEqual(result,payload)
            self.assertGreaterEqual(time.monotonic()-started,2*len(payload)/10000)
            self.assertEqual(conditioner.errors,[])
        finally:
            conditioner.close(); server.shutdown(); server.server_close(); worker.join()
