"""Exercise real gRPC cardinalities, TLS validation, and cancellation boundaries."""

import concurrent.futures
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path

import grpc

from wallet_privacy_testkit.fault_relay import SendTransactionRelay, SERVER_STREAMING_METHODS
from wallet_privacy_testkit.protocol import SERVICE, SEND_TRANSACTION, RawTransaction, SendResponse


class _Service(grpc.GenericRpcHandler):
    def __init__(self):
        self.cancelled = threading.Event()
        self.deadline = None

    def service(self, details):
        name = details.method.rsplit('/', 1)[-1]
        if name in SERVER_STREAMING_METHODS:
            return grpc.unary_stream_rpc_method_handler(self.stream)
        if name == 'GetTaddressBalanceStream':
            return grpc.stream_unary_rpc_method_handler(lambda requests, _: b''.join(requests))
        return grpc.unary_unary_rpc_method_handler(self.unary)

    def unary(self, request, context):
        if request == b'error':
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, 'upstream validation error')
        if request == b'wait':
            self.deadline = context.time_remaining()
            context.add_callback(self.cancelled.set)
            self.cancelled.wait(5)
        return request

    def stream(self, request, context):
        yield b'first'
        if request == b'wait':
            context.add_callback(self.cancelled.set)
            self.cancelled.wait(5)
            return
        yield request
        if request == b'error':
            context.abort(grpc.StatusCode.DATA_LOSS, 'stream failed after two messages')
        yield b'last'


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.service = _Service()
        self.server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=4))
        self.server.add_generic_rpc_handlers((self.service,))
        port = self.server.add_insecure_port('127.0.0.1:0')
        self.server.start()
        self.addCleanup(lambda: self.server.stop(0).wait())
        self.relay = SendTransactionRelay(f'127.0.0.1:{port}', 'before-once')
        self.addCleanup(self.relay.close)
        self.channel = grpc.insecure_channel(f'127.0.0.1:{self.relay.port}')
        self.addCleanup(self.channel.close)

    def test_opaque_unary_and_upstream_error(self):
        call = self.channel.unary_unary(f'/{SERVICE}/GetLightdInfo')
        self.assertEqual(call(b'\x00\xffopaque', timeout=3), b'\x00\xffopaque')
        with self.assertRaises(grpc.RpcError) as raised:
            call(b'error', timeout=3)
        self.assertEqual(raised.exception.code(), grpc.StatusCode.INVALID_ARGUMENT)
        self.assertEqual(raised.exception.details(), 'upstream validation error')
        self.assertEqual(self.relay.events, [])

    def test_all_known_server_streams_preserve_messages(self):
        for name in sorted(SERVER_STREAMING_METHODS):
            with self.subTest(method=name):
                self.assertEqual(list(self.channel.unary_stream(f'/{SERVICE}/{name}')(b'\x00\xff', timeout=3)),
                                 [b'first', b'\x00\xff', b'last'])

    def test_partial_stream_retains_upstream_failure(self):
        call = self.channel.unary_stream(f'/{SERVICE}/GetBlockRange')(b'error', timeout=3)
        self.assertEqual(next(call), b'first')
        self.assertEqual(next(call), b'error')
        with self.assertRaises(grpc.RpcError) as raised:
            next(call)
        self.assertEqual(raised.exception.code(), grpc.StatusCode.DATA_LOSS)

    def test_client_stream_including_empty_stream(self):
        call = self.channel.stream_unary(f'/{SERVICE}/GetTaddressBalanceStream')
        self.assertEqual(call(iter([b'a', b'\x00', b'bc']), timeout=3), b'a\x00bc')
        self.assertEqual(call(iter([]), timeout=3), b'')

    def test_cancelled_stream_stops_upstream_work(self):
        call = self.channel.unary_stream(f'/{SERVICE}/GetBlockRange')(b'wait', timeout=4)
        self.assertEqual(next(call), b'first')
        call.cancel()
        self.assertTrue(self.service.cancelled.wait(2), 'upstream outlived the cancelled client')

    def test_client_deadline_is_forwarded_upstream(self):
        with self.assertRaises(grpc.RpcError) as raised:
            self.channel.unary_unary(f'/{SERVICE}/GetLightdInfo')(b'wait', timeout=0.5)
        self.assertEqual(raised.exception.code(), grpc.StatusCode.DEADLINE_EXCEEDED)
        self.assertIsNotNone(self.service.deadline)
        self.assertLessEqual(self.service.deadline, 0.6)
        self.assertTrue(self.service.cancelled.wait(2))


def certificate(folder, name, hostname):
    key, cert = folder / f'{name}.key', folder / f'{name}.pem'
    config = folder / f'{name}.cnf'
    config.write_text('[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=ext\n'
                      f'[dn]\nCN={hostname}\n[ext]\nsubjectAltName=DNS:{hostname}\n'
                      'basicConstraints=critical,CA:TRUE\n')
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                    '-days', '1', '-config', str(config), '-keyout', str(key), '-out', str(cert)],
                   check=True, capture_output=True)
    return key, cert


class TLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        folder = Path(cls.temp.name)
        cls.key, cls.cert = certificate(folder, 'trusted', 'localhost')
        _, cls.other_cert = certificate(folder, 'other', 'localhost')

    def setUp(self):
        self.server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=2))
        self.server.add_generic_rpc_handlers((_Service(),))
        credentials = grpc.ssl_server_credentials(((self.key.read_bytes(), self.cert.read_bytes()),))
        self.port = self.server.add_secure_port('127.0.0.1:0', credentials)
        self.server.start()
        self.addCleanup(lambda: self.server.stop(0).wait())

    def test_tls_on_both_relay_legs(self):
        relay = SendTransactionRelay(f'localhost:{self.port}', 'before-once',
                                    upstream_ca=self.cert, certificate=self.cert, private_key=self.key)
        self.addCleanup(relay.close)
        with grpc.secure_channel(f'localhost:{relay.port}', grpc.ssl_channel_credentials(
                root_certificates=self.cert.read_bytes())) as channel:
            result = channel.unary_unary(f'/{SERVICE}/GetLightdInfo')(b'verified TLS', timeout=3)
            self.assertEqual(result, b'verified TLS')
        with grpc.secure_channel(f'localhost:{relay.port}', grpc.ssl_channel_credentials(
                root_certificates=self.other_cert.read_bytes())) as channel:
            with self.assertRaises(grpc.RpcError):
                channel.unary_unary(f'/{SERVICE}/GetLightdInfo')(b'untrusted', timeout=1)

    def test_upstream_wrong_ca_is_rejected(self):
        with self.assertRaises(grpc.FutureTimeoutError):
            SendTransactionRelay(f'localhost:{self.port}', 'before-once',
                                 upstream_ca=self.other_cert, ready_timeout=0.5)

    def test_upstream_hostname_is_verified(self):
        # This certificate contains localhost, but has no 127.0.0.1 IP SAN.
        with self.assertRaises(grpc.FutureTimeoutError):
            SendTransactionRelay(f'127.0.0.1:{self.port}', 'before-once',
                                 upstream_ca=self.cert, ready_timeout=0.5)


class HoldTests(unittest.TestCase):
    def test_accepted_response_is_held_until_client_cancels(self):
        server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=2))
        self.addCleanup(lambda: server.stop(0).wait())
        server.add_generic_rpc_handlers((grpc.method_handlers_generic_handler(SERVICE, {
            'SendTransaction': grpc.unary_unary_rpc_method_handler(
                lambda request, _: SendResponse(errorCode=0, errorMessage='accepted').SerializeToString())
        }),))
        port = server.add_insecure_port('127.0.0.1:0')
        server.start()
        relay = SendTransactionRelay(f'127.0.0.1:{port}', 'after-hold')
        self.addCleanup(relay.close)
        with grpc.insecure_channel(f'127.0.0.1:{relay.port}') as channel:
            call = channel.unary_unary(SEND_TRANSACTION).future(
                RawTransaction(data=b'transaction').SerializeToString(), timeout=5)
            deadline = time.monotonic() + 2
            while not any(e.get('response_held') for e in relay.events) and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(relay.events[0].get('response_held'))
            self.assertEqual(relay.events[0]['upstream_response']['error_code'], 0)
            self.assertFalse(call.done(), 'acknowledgement escaped before cancellation')
            self.assertTrue(call.cancel())
            with self.assertRaises(grpc.FutureCancelledError):
                call.result(timeout=2)


if __name__ == '__main__':
    unittest.main()
