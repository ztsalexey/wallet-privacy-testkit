# Zingolib v5 regtest case study

Measured September 4, 2026. The complete run used released [Zingolib v5.0.0](https://github.com/zingolabs/zingolib/releases/tag/zingolib_v5.0.0), lightwalletd at revision `d79cd1100575ff909d70e00d5514a4092df94934`, and Zebra 6.2.3 at a pinned image digest. Three independent wallets constructed and proved Orchard transactions. Zebra validated and mined them on an isolated NU6.2 regtest chain.

The only client dependency modification added an explicitly configured localhost certificate to its normal trust roots. Certificate and hostname verification remained active. Transaction construction, proof generation, fee selection, retry logic, and synchronization were unchanged. [Machine-readable provenance](provenance.json).

## Passive size result

The run created 18 shielded payments in six blocks of three eligible candidates. The first block trained a median record-to-transaction offset. Fifteen payments were held out. Each operation ran in a fresh CLI process with synchronization disabled during sending, giving the observer clear operation boundaries.

| Recipient entries | Samples | Raw transaction bytes | Largest client TLS record bytes |
| --- | ---: | ---: | ---: |
| 1 | 9 | 9,165 | 9,207 |
| 2 | 6 | 12,321 | 12,363 |
| 4 | 3 | 18,633 | 16,406 |

The four-recipient transaction spanned TLS records, so the largest-record feature did not preserve a constant offset for it.

When a held-out block contained one transaction of each structure, size-only matching was 100%, against a 33.3% random reference. When all three transactions had the same structure, every observation tied and fractional accuracy was 33.3%. The designed combined sample was 60%. That aggregate depends on the deliberately selected mixture and is not an estimate for wallet users.

## Delivery result

Three additional transactions exercised declared response failures:

| Boundary | Attempts | Wallet state before mining | Node state | Wallet state after mining and sync |
| --- | ---: | --- | --- | --- |
| First attempt failed before forwarding | 2 | Transmitted | Accepted once | Confirmed |
| First response lost after upstream acceptance | 4 | Failed | In mempool | Confirmed |
| Every response lost after upstream submission | 4 | Failed | In mempool | Confirmed |

Every retry reused the same signed transaction bytes, and their hash matched the transaction fetched from Zebra. No second payment was created. In the single-lost-response case, later submissions received `transaction already exists in mempool`, but the tested release still returned a send error and marked the transaction failed until chain scanning corrected it.

Current Zingolib development source contains related duplicate handling and a final server delivery check after retry exhaustion. This report therefore documents behavior in the named release and a reusable regression scenario. It does not claim that the current development branch retains the issue.

## Release artifact verification

On September 5, the installed 0.1.0 wheel's relay was substituted for the research relay and the `after-once` scenario was repeated with a newly constructed Orchard transaction. Zebra accepted the 9,165-byte transaction before the relay discarded the response. Zingolib made four submissions with the same signed-byte hash, the node mempool contained the accepted transaction, and the same transaction reached three confirmations and appeared as confirmed in wallet history. This confirms that the packaged relay preserves the behavior used by the case study rather than only passing a mock service test.

## Limits

The test did not run a mobile application, public network, Tor, Nym, Zero-indexer, Ironwood transaction, continuous background sync, or full-wallet padding intervention. Regtest validates transactions but does not reproduce mainnet proof-of-work or network conditions. The test operator supplied operation windows and candidate blocks. Timing and identity correlation remain unmeasured.

The [verified output](verified.json) is sanitized. Raw traces remain in the research workspace and are not distributed with this package because the retained environment also contains disposable wallet state and a TLS private key.
