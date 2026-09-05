import concurrent.futures
import hashlib
import unittest

import grpc

from wallet_privacy_testkit.fault_relay import SendTransactionRelay
from wallet_privacy_testkit.protocol import RawTransaction, SEND_TRANSACTION, SendResponse


class _Indexer(grpc.GenericRpcHandler):
    def __init__(self):
        self.hashes = []

    def service(self, details):
        if details.method != SEND_TRANSACTION:
            return None

        def submit(request, _context):
            transaction = RawTransaction.FromString(request)
            digest = hashlib.sha256(transaction.data).hexdigest()
            duplicate = digest in self.hashes
            self.hashes.append(digest)
            response = SendResponse(
                errorCode=-1 if duplicate else 0,
                errorMessage="transaction already exists in mempool" if duplicate else digest,
            )
            return response.SerializeToString()

        return grpc.unary_unary_rpc_method_handler(submit)


class FaultRelayTests(unittest.TestCase):
    def setUp(self):
        self.indexer = _Indexer()
        self.server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=4))
        self.server.add_generic_rpc_handlers((self.indexer,))
        self.port = self.server.add_insecure_port("127.0.0.1:0")
        self.server.start()

    def tearDown(self):
        self.server.stop(0).wait()

    @staticmethod
    def _submit(channel, payload=b"signed-transaction"):
        request = RawTransaction(data=payload, height=42).SerializeToString()
        return channel.unary_unary(SEND_TRANSACTION)(request, timeout=5)

    def test_failure_before_forwarding_retries_without_duplicate(self):
        relay = SendTransactionRelay(f"127.0.0.1:{self.port}", "before-once")
        channel = grpc.insecure_channel(f"127.0.0.1:{relay.port}")
        try:
            with self.assertRaises(grpc.RpcError) as raised:
                self._submit(channel)
            self.assertEqual(raised.exception.code(), grpc.StatusCode.UNAVAILABLE)
            response = SendResponse.FromString(self._submit(channel))
            self.assertEqual(response.errorCode, 0)
            self.assertEqual(len(self.indexer.hashes), 1)
            self.assertEqual([row["forwarded"] for row in relay.events], [False, True])
        finally:
            channel.close()
            relay.close()

    def test_lost_first_acknowledgement_exposes_duplicate_response(self):
        relay = SendTransactionRelay(f"127.0.0.1:{self.port}", "after-once")
        channel = grpc.insecure_channel(f"127.0.0.1:{relay.port}")
        try:
            with self.assertRaises(grpc.RpcError) as raised:
                self._submit(channel)
            self.assertEqual(raised.exception.code(), grpc.StatusCode.UNAVAILABLE)
            response = SendResponse.FromString(self._submit(channel))
            self.assertEqual(response.errorCode, -1)
            self.assertEqual(len(set(self.indexer.hashes)), 1)
            self.assertEqual(
                [row["response_lost"] for row in relay.events], [True, False]
            )
        finally:
            channel.close()
            relay.close()

    def test_losing_every_response_keeps_forwarding_identical_bytes(self):
        relay = SendTransactionRelay(f"127.0.0.1:{self.port}", "after-all")
        channel = grpc.insecure_channel(f"127.0.0.1:{relay.port}")
        try:
            for _ in range(3):
                with self.assertRaises(grpc.RpcError) as raised:
                    self._submit(channel)
                self.assertEqual(raised.exception.code(), grpc.StatusCode.UNAVAILABLE)
            self.assertEqual(len(relay.events), 3)
            self.assertEqual(
                len({row["transaction_sha256"] for row in relay.events}), 1
            )
            self.assertTrue(all(row["response_lost"] for row in relay.events))
        finally:
            channel.close()
            relay.close()


if __name__ == "__main__":
    unittest.main()
