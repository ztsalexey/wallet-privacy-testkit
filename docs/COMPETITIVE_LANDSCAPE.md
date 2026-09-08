# Competitive and overlap review

Reviewed September 7, 2026. This is a product-positioning review of selected primary repositories, documentation, and grant records. It is not an audit or an exhaustive search. Described behavior belongs to the cited source and revision; a development document does not establish that every released wallet implements it.

**The useful product boundary is an additional wallet CI check:** inject uncertainty around a real transaction submission, retain observations, and check the eventual wallet and chain outcome. Passive TLS measurements support specific privacy experiments. The value depends on another team finding these checks useful in its existing release workflow.

Wallet Privacy Testkit is independently published at [ztsalexey/wallet-privacy-testkit](https://github.com/ztsalexey/wallet-privacy-testkit) and on [PyPI](https://pypi.org/project/wallet-privacy-testkit/). Earlier name-availability checks were pre-publication history and do not describe its current status.

## Zcash testing infrastructure

| Project | What it already provides | Relationship to this testkit |
| --- | --- | --- |
| [Z3](https://github.com/ZcashFoundation/z3#building-and-testing-against-z3) | Docker Compose deployments of Zebra and Zallet, optional Zaino, regtest, and documented attachment contracts | A candidate environment provider. Its documented Zaino gRPC endpoint is plaintext; passive TLS experiments need an explicit TLS boundary. An adapter has not been validated here. |
| [Zcash Integration Tests](https://github.com/zcash/integration-tests) | Python functional tests and cross-repository CI for Zebra, Zaino, and Zallet, primarily through JSON-RPC | A candidate home for agreed ecosystem regressions. Its [agent contribution policy](https://github.com/zcash/integration-tests/blob/main/AGENTS.md) requires prior maintainer acknowledgment for outside contributors. |
| [Zaino stability, performance, and testing work](https://github.com/ZcashCommunityGrants/zcashcommunitygrants/issues/328) | A grant covering indexer correctness, concurrent access and reorg tests, and described protocol-comparison tools; its record is labeled approved and complete, with completion and payout confirmed August 27 | Material overlap with broad indexer testing. The record establishes funded work, not that every proposed tool has merged upstream or that its authors want this testkit. |
| [Swift SDK Broadcaster](https://github.com/zcash/zcash-swift-wallet-sdk/blob/main/MIGRATING.md#broadcaster-redesign-multi-server-submission) | Documented persistent retry-endpoint plans, explicit unknown outcomes for timed-out or cancelled submissions, and recovery of already-accepted transactions | An implementation to test, rather than delivery logic to replace. Preserving selected broadcast endpoints across a lost acknowledgement and restart is a concrete candidate regression. The documentation is not evidence of an unresolved bug. |

## Privacy infrastructure

| Project | Current overlap | Remaining distinction |
| --- | --- | --- |
| [Zingolib network privacy work](https://github.com/zingolabs/zingolib/issues/2508) | A public tracking issue for Nym transport, destination policy, mobile integration, and failure behavior | This testkit could check behavior around that transport. The issue was last updated July 24 at this review; its checklist is not proof of current shipping status. |
| [Zero-indexer review agenda](https://github.com/ShieldedLabs/zero/blob/main/zeronym/OPEN-QUESTIONS.md) | Attested shim/hub and batching work; acknowledged residual questions include TLS transaction-size correlation, active tagging, and low-volume batches | A potential system under test. Deployment and attestation claims require their own verification. A batch of one does not establish batching anonymity. |
| [ZIP 318](https://zips.z.cash/zip-0318) | Draft wallet guidance for Orchard-to-Ironwood migration, including selected private-network routing, separation of sync and broadcast sessions, and recovery after transient failure | A source for narrowly scoped checks with a pinned specification revision. Neither this draft nor a passing subset of tests certifies a wallet's privacy. |

## General-purpose substitutes

| Tool | Strength | Why the testkit still differs |
| --- | --- | --- |
| [Toxiproxy](https://github.com/Shopify/toxiproxy) | Configurable TCP latency, timeouts, bandwidth limits, and other connection faults for CI | Its TCP controls do not by themselves identify a particular gRPC submission and establish its wallet/chain outcome. Prefer existing generic fault tools where they fit. |
| [mitmproxy](https://docs.mitmproxy.org/stable/) | TLS/HTTP interception, modification, capture, and replay | Custom scripts can reproduce parts of a semantic relay. Its use still needs a wallet-specific scenario, data-retention policy, and outcome assertions. |
| Wireshark/tcpdump | Packet capture and protocol analysis | Capture is a substitute for part of the measurement pipeline, not the wallet-state assertions or reproducible scenario. |

## What the evidence supports

There are strong substitutes for provisioning, generic faults, TLS inspection, wallet integration, and privacy transport. We have not established that their combination is unique, or that combining them is itself valuable to a maintainer. On-chain analytics and professional audits are adjacent categories; their existence does not validate demand for this package.

The funded Zaino work is evidence that the ecosystem allocates resources to testing. The Swift SDK documentation supplies a concrete behavior worth preserving. Neither establishes an adopting team, a customer, or a market price for Wallet Privacy Testkit.

The next useful test joins delivery and privacy policy: after an accepted payment loses its acknowledgement and the wallet restarts, do retries preserve the signed transaction and its selected broadcast endpoints? The [next-step experiment](NEXT_STEPS.md) defines the observations, controls, and adoption criteria. This is a candidate regression against documented behavior, not a newly discovered vulnerability or a promised upstream integration.
