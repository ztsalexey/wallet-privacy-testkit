# Competitive and overlap review

Reviewed September 5, 2026. This is a product-positioning review, not an audit of the listed projects. Public repositories and documentation can change after this date.

The project uses the independent product name **Wallet Privacy Testkit** and describes its relationship as “for Zcash.” This follows the [Zcash Foundation trademark policy](https://zfnd.org/trademark-policy/), which permits truthful “for Zcash” descriptions while disallowing the mark as part of a third-party product name. Exact-name searches found no indexed GitHub repository, and the PyPI JSON endpoint returned 404 on the review date. Neither check reserves the name or substitutes for a publication-time check.

## Zcash testing infrastructure

| Project | What it already provides | Relationship to this testkit |
| --- | --- | --- |
| [Z3](https://github.com/ZcashFoundation/z3) | Docker Compose deployments of Zebra, Zallet, the RPC router, and optional Zaino; an isolated regtest environment | Preferred future environment provider. Reimplementing this stack would duplicate maintained infrastructure. |
| [Zcash Integration Tests](https://github.com/zcash/integration-tests) | Python functional tests and cross-repository CI for Zebra, Zaino, and Zallet | Natural home for accepted ecosystem-wide scenarios. It currently focuses on RPC behavior rather than an external TLS observer. Maintainer acknowledgment is required before a PR. |
| [Zingo Regchest](https://github.com/zingolabs/zingo-regchest) and [Zingo Mobile tests](https://github.com/zingolabs/zingo-mobile) | A containerized regtest network plus Android and iOS wallet integration suites | Natural host for a Zingo adapter. The testkit should supply faults and measurements rather than another chain fixture. |
| Zingolib darkside and lib-to-node tests | Controlled wallet sync scenarios and real node/indexer integration inside Zingolib | Existing framework for wallet-state assertions. Protocol-aware acknowledgement loss may fit here after maintainer alignment. |

## Privacy infrastructure

| Project | Current overlap | Remaining distinction |
| --- | --- | --- |
| [Zingolib network privacy work](https://github.com/zingolabs/zingolib/issues/2508) | Nym transport, broadcast destinations, retry policy, and wallet integration | This testkit measures or injects behavior around those transports. It does not implement an anonymity network. |
| [Zero-indexer](https://forum.zcashcommunity.com/t/zero-indexer-protecting-network-privacy-for-zcash-users/57113) | Attested indexer shim/hub, delayed batch broadcast, wallet and operator integrations | A candidate system under test. Its own protection depends on deployment and batch activity; the testkit cannot replace its attestation or relay. |
| [ZIP 307](https://zips.z.cash/zip-0307) and [ZIP 318](https://zips.z.cash/zip-0318) | Privacy requirements and design guidance for light clients and pool migration | Sources for test requirements. Specifications are not test runners. |

## General-purpose substitutes

| Tool | Strength | Why the testkit still differs |
| --- | --- | --- |
| [Toxiproxy](https://github.com/Shopify/toxiproxy) | Mature TCP latency, timeout, bandwidth, and connection fault injection | It cannot identify the point after a specific gRPC transaction has been accepted upstream. It is a better dependency for generic network conditions. |
| [mitmproxy](https://docs.mitmproxy.org/stable/) | Mature TLS/HTTP interception, modification, capture, and replay | It records far more content and is not a Zcash result model. Custom scripts could reproduce parts of the relay. |
| Wireshark/tcpdump | Established packet capture and protocol analysis | They provide raw observations rather than candidate-set accounting, wallet-state assertions, or a transaction-aware failure boundary. |

## Privacy analyzers and audit services

[Stealth](https://github.com/stealth-bitcoin/stealth) and [Am I Exposed?](https://github.com/Copexit/am-i-exposed) analyze Bitcoin on-chain wallet behavior. CipherScan supplies Zcash and cross-chain privacy analytics. These validate interest in privacy analysis but address public transaction patterns rather than wallet-to-indexer encrypted traffic.

Wallet security firms offer code, mobile, key-management, and privacy audits. [Hacken](https://hacken.io/services/wallet-audit/) advertises wallet audits, while [Chainscore Labs](https://chainscorelabs.com/services/wallet-infrastructure/wallet-security-audits/privacy-preserving-wallet-security-audit) advertises privacy-preserving wallet audits including metadata analysis. These are service competitors at the budget level. Their public materials do not establish an open, Zcash-specific regression runner with this testkit's exact fault boundary.

## Conclusion

The reviewed set contains strong substitutes for chain provisioning, generic faults, TLS inspection, wallet integration, privacy transport, and professional audits. We found no maintained open-source project in this review that combines all three of the testkit's narrow behaviors:

1. passive TLS-record measurement without decryption;
2. a failure injected after actual `SendTransaction` submission;
3. conservative linkage scoring tied to the wallet's eventual chain state.

That finding is bounded by the reviewed sources and date. It is not proof that no equivalent private or unpublished tool exists.

The project remains relevant only as a complement to existing wallet CI. A standalone replacement for Z3, Regchest, Toxiproxy, mitmproxy, Zingolib transport code, or Zero-indexer would have weak differentiation. The strongest route is an open test core plus one maintainer-requested adapter and upstream regression.
