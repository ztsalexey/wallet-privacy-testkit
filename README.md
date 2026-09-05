# Wallet Privacy Testkit for Zcash

Wallet Privacy Testkit is an adversarial test layer for Zcash wallet-to-indexer traffic. It records the lengths and timing visible outside TLS, injects uncertainty around `SendTransaction`, and evaluates size-only transaction matching without awarding full credit to ties.

This is an independent project maintained at [ztsalexey/wallet-privacy-testkit](https://github.com/ztsalexey/wallet-privacy-testkit). It is not affiliated with or endorsed by the Zcash Foundation, Electric Coin Company, or any wallet or indexer maintainer.

Version 0.1.0 is a research preview. It supplies reusable test components and a verified Zingolib case study. It does not certify a wallet, assign a privacy score, inspect mainnet funds, or replace a wallet's existing integration tests.

## Why this exists

A shielded transaction can hide its participants and value on-chain while its network behavior still leaks information. A second failure mode appears when a node accepts a payment but the wallet loses the response. The wallet must distinguish rejection from an unknown outcome and recover without creating another payment.

Existing projects already provision Zcash regtest networks and test wallet behavior. This testkit attaches to those environments and contributes two narrower capabilities:

- passive ciphertext metadata capture, without TLS keys or payload logging;
- protocol-aware failure injection before or after transaction submission.

The [methodology](docs/METHODOLOGY.md) defines what each result means. The [threat model](docs/THREAT_MODEL.md) states what it does not establish.

## Install

Python 3.11 or newer is required.

Version 0.1.0 is available on [PyPI](https://pypi.org/project/wallet-privacy-testkit/0.1.0/):

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install wallet-privacy-testkit==0.1.0
wpt --help
```

## Develop from a source checkout

```sh
python3 -m venv .venv
source .venv/bin/activate
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m unittest discover -s tests -v
```

The release was developed with Python 3.12.9, gRPC 1.83.1, and protobuf 7.36.1. CI tests the pinned development environment on Python 3.11–3.13 on Linux and macOS. The broader runtime dependency ranges are not exhaustively tested.

Packaged wheels and source archives are available from [GitHub Releases](https://github.com/ztsalexey/wallet-privacy-testkit/releases). After activating a virtual environment, install a downloaded wheel with `python -m pip install ./wallet_privacy_testkit-0.1.0-py3-none-any.whl`.

## Passive TLS metadata capture

Point a wallet at the printed local port while the target indexer remains at `localhost:9067`:

```sh
wpt capture \
  --target-host localhost \
  --target-port 9067 \
  --listen-port 7443 \
  --output trace.jsonl
```

Stop the capture with Ctrl-C, then validate that every captured TCP byte belongs to a complete TLS record:

```sh
wpt summarize trace.jsonl
```

The forwarder copies bytes unchanged. Its trace contains connection numbers, monotonic timestamps, directions, byte counts, TLS content types, and TLS record lengths. It does not terminate TLS, store addresses, or record packet contents. A process boundary supplied by the test operator is still side information and must be disclosed in a report.

## Transaction delivery faults

The semantic relay terminates a test TLS connection and forwards the real gRPC service. It understands only enough of the lightwalletd protocol to identify and hash `RawTransaction.data`; it never writes signed transaction bytes. All other known RPCs are forwarded as opaque bytes using their required streaming cardinality.

The forwarding table was checked against canonical `lightwallet-protocol` v0.5.0. A later protocol version that adds a streaming RPC requires a testkit update before that RPC can pass through correctly.

For a TLS upstream and TLS-facing wallet:

```sh
wpt fault-relay \
  --upstream localhost:9067 \
  --upstream-ca test-ca.pem \
  --certificate localhost.pem \
  --private-key localhost.key \
  --mode after-once \
  --events events.json
```

The supported modes are:

| Mode | Behavior |
| --- | --- |
| `before-once` | Fail the first submission without forwarding it, then forward normally |
| `after-once` | Forward the first submission and discard its response, then forward normally |
| `after-all` | Forward every submission and discard every response |

Use the relay only with disposable wallets and isolated regtest funds. The tool deliberately changes transaction-delivery behavior. The test operator remains responsible for checking the node's mempool or chain and the wallet's eventual state.

An insecure local upstream or client can omit the certificate options. The relay binds to `127.0.0.1` by default. Supplying only one of `--certificate` and `--private-key` is rejected.

The printed endpoint uses `127.0.0.1`. When the wallet-facing side uses TLS, the server certificate must therefore contain the IP address `127.0.0.1` in its Subject Alternative Name. The upstream CA file is required for a TLS upstream; omitting it selects an insecure upstream channel.

## Size-only matching

`wpt match samples.json` accepts a JSON array. Each row must contain a unique `id`, a `batch`, `observed_bytes`, and the corresponding public `transaction_bytes`. Batch 0 calibrates a single median byte offset by default. Every other observation is compared only with candidates in its own batch.

```json
[
  {"id":"train-a","batch":0,"observed_bytes":9207,"transaction_bytes":9165},
  {"id":"train-b","batch":0,"observed_bytes":12363,"transaction_bytes":12321},
  {"id":"test-a","batch":1,"observed_bytes":9207,"transaction_bytes":9165},
  {"id":"test-b","batch":1,"observed_bytes":12363,"transaction_bytes":12321}
]
```

Nearest candidates share credit when their distance ties. A batch with fewer than two candidates is rejected because singleton identification says nothing about the matcher. The tool reports a random reference computed from each held-out batch's candidate count.

## Verified case study

The included [Zingolib v5 regtest report](evidence/zingolib-v5-regtest/REPORT.md) records 18 newly constructed shielded payments and three delivery-fault transactions in the complete run. The wallet reported a payment as failed after its acknowledgement was lost even though Zebra had accepted it. Mining and synchronization corrected the status to confirmed. Current Zingolib development code already includes related duplicate and delivery-check handling, so this is regression evidence rather than a claim of an unresolved current bug.

The case study also found that encrypted lengths distinguished 1-, 2-, and 4-recipient transaction structures in a favorable observer model. Equal-structure payments tied at chance. The result does not estimate deanonymization in normal wallet traffic.

## Project status

The release boundary is intentionally small. Z3, Zcash Integration Tests, Regchest, and wallet-specific suites already cover network provisioning and broad functional behavior. The testkit is designed to complement them. See the [competitive and overlap review](docs/COMPETITIVE_LANDSCAPE.md) and [release checklist](docs/RELEASE_CHECKLIST.md).

Upstream contributions should begin with a maintainer-acknowledged issue and a narrowly scoped regression, following the target repository's contribution policy.

## License

Licensed under either the MIT License or Apache License 2.0, at your option.
