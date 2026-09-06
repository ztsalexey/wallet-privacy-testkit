"""Command-line entry point for the privacy testkit."""

import argparse
import json
import time
from pathlib import Path

from . import __version__
from .capture import TLSForwarder, TraceRecorder, summarize_trace
from .fault_relay import FAULT_MODES, SendTransactionRelay
from .matching import evaluate_size_matching
from .recovery import verify_recovery_report
from .privacy import analyze_privacy
from .study import analyze_study


def _port(value, *, allow_zero=False):
    port = int(value)
    minimum = 0 if allow_zero else 1
    if not minimum <= port <= 65_535:
        label = "0..65535" if allow_zero else "1..65535"
        raise argparse.ArgumentTypeError(f"port must be in {label}")
    return port


def _listen_port(value):
    return _port(value, allow_zero=True)


def _write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as destination:
        json.dump(value, destination, indent=2)
        destination.write("\n")


def _capture(args):
    recorder = TraceRecorder(args.output)
    forwarder = TLSForwarder(
        (args.target_host, args.target_port),
        recorder,
        args.listen_host,
        args.listen_port,
    )
    print(
        json.dumps(
            {
                "ready": True,
                "listen_host": forwarder.server_address[0],
                "listen_port": forwarder.server_address[1],
                "trace": str(args.output),
            }
        ),
        flush=True,
    )
    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        forwarder.close()
        recorder.close()


def _summarize(args):
    print(json.dumps(summarize_trace(args.trace, not args.allow_partial), indent=2))


def _match(args):
    samples = json.loads(args.samples.read_text(encoding="utf-8"))
    print(
        json.dumps(
            evaluate_size_matching(samples, training_batch=args.training_batch), indent=2
        )
    )


def _fault_relay(args):
    if args.events.exists():
        raise FileExistsError(f"event output already exists: {args.events}")
    relay = SendTransactionRelay(
        args.upstream,
        args.mode,
        upstream_ca=args.upstream_ca,
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        certificate=args.certificate,
        private_key=args.private_key,
    )
    print(
        json.dumps({"ready": True, "endpoint": relay.endpoint, "mode": args.mode}),
        flush=True,
    )
    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        relay.close()
        _write_new(args.events, relay.events)


def parser():
    root = argparse.ArgumentParser(
        prog="wpt", description="Adversarial network tests for Zcash wallets"
    )
    root.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = root.add_subparsers(dest="command", required=True)

    capture = commands.add_parser("capture", help="record passive TLS metadata")
    capture.add_argument("--target-host", required=True)
    capture.add_argument("--target-port", required=True, type=_port)
    capture.add_argument("--listen-host", default="127.0.0.1")
    capture.add_argument("--listen-port", default=0, type=_listen_port)
    capture.add_argument("--output", required=True, type=Path)
    capture.set_defaults(handler=_capture)

    summarize = commands.add_parser("summarize", help="validate and summarize a trace")
    summarize.add_argument("trace", type=Path)
    summarize.add_argument("--allow-partial", action="store_true")
    summarize.set_defaults(handler=_summarize)

    matching = commands.add_parser("match", help="evaluate size-only candidate matching")
    matching.add_argument("samples", type=Path)
    matching.add_argument("--training-batch", default=0, type=int)
    matching.set_defaults(handler=_match)

    recovery = commands.add_parser('verify-recovery', help='recompute recovery assertions from observations')
    recovery.add_argument('report', type=Path)
    recovery.set_defaults(handler=lambda args: print(json.dumps(
        verify_recovery_report(json.loads(args.report.read_text())), indent=2)))

    privacy = commands.add_parser('analyze-privacy', help='evaluate held-out continuous-traffic send detection')
    privacy.add_argument('manifest', type=Path)
    privacy.set_defaults(handler=lambda args: print(json.dumps(analyze_privacy(args.manifest), indent=2)))

    study = commands.add_parser('analyze-study', help='verify a frozen-detector repeated privacy study')
    study.add_argument('manifest', type=Path)
    study.set_defaults(handler=lambda args: print(json.dumps(analyze_study(args.manifest), indent=2)))

    relay = commands.add_parser(
        "fault-relay", help="inject SendTransaction delivery uncertainty"
    )
    relay.add_argument("--upstream", required=True, help="host:port")
    relay.add_argument("--mode", required=True, choices=sorted(FAULT_MODES))
    relay.add_argument("--upstream-ca", type=Path)
    relay.add_argument("--listen-host", default="127.0.0.1")
    relay.add_argument("--listen-port", default=0, type=_listen_port)
    relay.add_argument("--certificate", type=Path)
    relay.add_argument("--private-key", type=Path)
    relay.add_argument("--events", required=True, type=Path)
    relay.set_defaults(handler=_fault_relay)
    return root


def main():
    args = parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
