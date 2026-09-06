import concurrent.futures
import unittest

import grpc

from wallet_privacy_testkit.fault_relay import SendTransactionRelay
from wallet_privacy_testkit.protocol import SERVICE, SEND_TRANSACTION, RawTransaction, SendResponse

REQUEST = (('authorization', 'test-credential'), ('x-repeat', 'one'), ('x-repeat', 'two'),
           ('x-request-bin', b'\x00\xff'))
HEADERS = (('x-header', 'first'), ('x-header', 'second'), ('x-header-bin', b'\x00\xfe'))
TRAILERS = (('x-trailer', 'done'), ('grpc-status-details-bin', b'\x01\xff'))


class _MetadataService(grpc.GenericRpcHandler):
    def __init__(self):
        self.requests = []

    def prepare(self, context):
        self.requests.append(tuple((k, v) for k, v in context.invocation_metadata() if k != 'user-agent'))
        context.send_initial_metadata(HEADERS)
        context.set_trailing_metadata(TRAILERS)

    def unary(self, request, context):
        self.prepare(context)
        if request == b'error':
            context.abort(grpc.StatusCode.PERMISSION_DENIED, 'controlled denial')
        return request

    def stream(self, request, context):
        self.prepare(context)
        yield b'first'
        if request == b'error':
            context.abort(grpc.StatusCode.DATA_LOSS, 'controlled partial-stream failure')
        yield request

    def submit(self, request, context):
        self.prepare(context)
        return SendResponse(errorCode=0, errorMessage='accepted').SerializeToString()

    def service(self, details):
        if details.method == SEND_TRANSACTION:
            return grpc.unary_unary_rpc_method_handler(self.submit)
        if details.method.endswith('/GetBlockRange'):
            return grpc.unary_stream_rpc_method_handler(self.stream)
        if details.method.endswith('/GetTaddressBalanceStream'):
            return grpc.stream_unary_rpc_method_handler(lambda requests, ctx: self.unary(b''.join(requests), ctx))
        return grpc.unary_unary_rpc_method_handler(self.unary)


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.service = _MetadataService()
        server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=4))
        server.add_generic_rpc_handlers((self.service,))
        port = server.add_insecure_port('127.0.0.1:0')
        server.start()
        self.addCleanup(lambda: server.stop(0).wait())
        self.relay = SendTransactionRelay(f'127.0.0.1:{port}', 'after-once')
        self.addCleanup(self.relay.close)
        self.channel = grpc.insecure_channel(f'127.0.0.1:{self.relay.port}')
        self.addCleanup(self.channel.close)

    def call(self, kind, data):
        if kind == 'server-stream':
            call = self.channel.unary_stream(f'/{SERVICE}/GetBlockRange')(data, metadata=REQUEST, timeout=3)
            return call, lambda: list(call)
        if kind == 'client-stream':
            call = self.channel.stream_unary(f'/{SERVICE}/GetTaddressBalanceStream').future(
                iter([data]), metadata=REQUEST, timeout=3)
        else:
            call = self.channel.unary_unary(f'/{SERVICE}/GetLightdInfo').future(data, metadata=REQUEST, timeout=3)
        return call, call.result

    def test_application_metadata_survives_all_cardinalities(self):
        for kind in ('unary', 'server-stream', 'client-stream'):
            with self.subTest(kind=kind):
                call, result = self.call(kind, b'payload')
                result()
                self.assertEqual(tuple(call.initial_metadata()), HEADERS)
                self.assertEqual(tuple(call.trailing_metadata()), TRAILERS)
                self.assertEqual(self.service.requests[-1], REQUEST)

    def test_error_headers_and_trailers_survive_all_cardinalities(self):
        for kind in ('unary', 'server-stream', 'client-stream'):
            with self.subTest(kind=kind):
                call, result = self.call(kind, b'error')
                with self.assertRaises(grpc.RpcError):
                    result()
                self.assertEqual(tuple(call.initial_metadata()), HEADERS)
                self.assertEqual(tuple(call.trailing_metadata()), TRAILERS)
                self.assertEqual(self.service.requests[-1], REQUEST)

    def test_lost_acknowledgement_does_not_leak_response_metadata(self):
        method = self.channel.unary_unary(SEND_TRANSACTION)
        payload = RawTransaction(data=b'finalized bytes').SerializeToString()
        call = method.future(payload, metadata=REQUEST, timeout=3)
        with self.assertRaises(grpc.RpcError):
            call.result()
        self.assertEqual(call.code(), grpc.StatusCode.UNAVAILABLE)
        self.assertEqual(tuple(call.initial_metadata()), ())
        self.assertEqual(tuple(call.trailing_metadata()), ())
        response, call = method.with_call(payload, metadata=REQUEST, timeout=3)
        self.assertEqual(SendResponse.FromString(response).errorCode, 0)
        self.assertEqual(tuple(call.initial_metadata()), HEADERS)
        self.assertEqual(tuple(call.trailing_metadata()), TRAILERS)
        self.assertNotIn('test-credential', repr(self.relay.events))
