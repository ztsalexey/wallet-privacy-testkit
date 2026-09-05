"""A protocol-aware relay for uncertain SendTransaction delivery tests."""

import concurrent.futures
import hashlib
import threading
import time
from pathlib import Path

import grpc

from .protocol import RawTransaction, SEND_TRANSACTION, SendResponse

FAULT_MODES = frozenset(("before-once", "after-once", "after-all", "after-hold"))
LIGHTWALLET_PROTOCOL_VERSION = "v0.5.0"
SERVER_STREAMING_METHODS = frozenset(
    (
        "GetBlockRange",
        "GetBlockRangeNullifiers",
        "GetTaddressTxids",
        "GetTaddressTransactions",
        "GetMempoolTx",
        "GetMempoolStream",
        "GetSubtreeRoots",
        "GetAddressUtxosStream",
    )
)
CLIENT_STREAMING_METHOD = "GetTaddressBalanceStream"


class SendTransactionRelay(grpc.GenericRpcHandler):
    """Forward the service and fail acknowledgements at declared boundaries."""

    def __init__(
        self,
        upstream,
        mode,
        *,
        upstream_ca=None,
        listen_host="127.0.0.1",
        listen_port=0,
        certificate=None,
        private_key=None,
        ready_timeout=15,
    ):
        if mode not in FAULT_MODES:
            raise ValueError(f"unknown fault mode: {mode}")
        if (certificate is None) != (private_key is None):
            raise ValueError("certificate and private key must be supplied together")
        self.mode = mode
        self.events = []
        self.lock = threading.Lock()
        if upstream_ca is None:
            self.channel = grpc.insecure_channel(upstream)
        else:
            roots = Path(upstream_ca).read_bytes()
            self.channel = grpc.secure_channel(
                upstream, grpc.ssl_channel_credentials(root_certificates=roots)
            )
        try:
            grpc.channel_ready_future(self.channel).result(timeout=ready_timeout)
        except BaseException:
            self.channel.close()
            raise
        self.server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=16))
        self.server.add_generic_rpc_handlers((self,))
        address = f"{listen_host}:{listen_port}"
        if certificate is None:
            self.port = self.server.add_insecure_port(address)
            self.scheme = "http"
        else:
            credentials = grpc.ssl_server_credentials(
                ((Path(private_key).read_bytes(), Path(certificate).read_bytes()),)
            )
            self.port = self.server.add_secure_port(address, credentials)
            self.scheme = "https"
        if not self.port:
            self.channel.close()
            raise RuntimeError(f"could not bind relay to {address}")
        self.server.start()

    @property
    def endpoint(self):
        return f"{self.scheme}://127.0.0.1:{self.port}"

    def service(self, details):
        method = details.method
        name = method.rsplit("/", 1)[-1]
        if name in SERVER_STREAMING_METHODS:
            return grpc.unary_stream_rpc_method_handler(
                lambda request, context: self._forward_stream(method, request, context)
            )
        if name == CLIENT_STREAMING_METHOD:
            return grpc.stream_unary_rpc_method_handler(
                lambda requests, context: self._forward_client_stream(
                    method, requests, context
                )
            )
        return grpc.unary_unary_rpc_method_handler(
            lambda request, context: self._forward_unary(method, request, context)
        )

    def _forward_stream(self, method, request, context):
        call = self.channel.unary_stream(method)(request, timeout=self._timeout(context))
        self._cancel_with_context(call, context)
        try:
            yield from call
        except grpc.RpcError as error:
            context.abort(error.code(), error.details())
        finally:
            call.cancel()

    @staticmethod
    def _timeout(context):
        remaining = context.time_remaining()
        return 120 if remaining is None else max(0, min(120, remaining))

    @staticmethod
    def _cancel_with_context(call, context):
        if not context.add_callback(call.cancel):
            call.cancel()

    def _forward_client_stream(self, method, requests, context):
        call = self.channel.stream_unary(method).future(requests, timeout=self._timeout(context))
        self._cancel_with_context(call, context)
        try:
            return call.result()
        except grpc.FutureCancelledError:
            context.abort(grpc.StatusCode.CANCELLED, "downstream call cancelled")
        except grpc.RpcError as error:
            context.abort(error.code(), error.details())

    def _forward_unary(self, method, request, context):
        event = None
        if method == SEND_TRANSACTION:
            transaction = RawTransaction.FromString(request)
            with self.lock:
                event = {
                    "attempt": len(self.events) + 1,
                    "time_ns": time.monotonic_ns(),
                    "transaction_sha256": hashlib.sha256(transaction.data).hexdigest(),
                    "transaction_bytes": len(transaction.data),
                    "height": transaction.height,
                }
                self.events.append(event)
            if self.mode == "before-once" and event["attempt"] == 1:
                event["forwarded"] = False
                context.abort(
                    grpc.StatusCode.UNAVAILABLE,
                    "privacy-testkit: connection lost before upstream submission",
                )
            event["forwarded"] = True
        try:
            call = self.channel.unary_unary(method).future(request, timeout=self._timeout(context))
            self._cancel_with_context(call, context)
            response = call.result()
        except grpc.FutureCancelledError:
            context.abort(grpc.StatusCode.CANCELLED, "downstream call cancelled")
        except grpc.RpcError as error:
            if event is not None:
                event["upstream_grpc_error"] = error.code().name
            context.abort(error.code(), error.details())
        if event is not None:
            decoded = SendResponse.FromString(response)
            event["upstream_response"] = {
                "error_code": decoded.errorCode,
                "message": decoded.errorMessage,
            }
            if self.mode == "after-hold":
                # Let an external test kill the wallet after node acceptance,
                # while its RPC is still waiting for an acknowledgement.
                finished = threading.Event()
                if not context.add_callback(finished.set):
                    finished.set()
                event["response_held"] = True
                event["response_lost"] = True
                finished.wait()
                context.abort(grpc.StatusCode.CANCELLED, "privacy-testkit: held response cancelled")
            lose_response = self.mode == "after-all" or (
                self.mode == "after-once" and event["attempt"] == 1
            )
            event["response_lost"] = lose_response
            if lose_response:
                context.abort(
                    grpc.StatusCode.UNAVAILABLE,
                    "privacy-testkit: response lost after upstream submission",
                )
        return response

    def close(self, grace=0):
        self.server.stop(grace).wait()
        self.channel.close()
