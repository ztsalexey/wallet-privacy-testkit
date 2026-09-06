# Wallet Privacy Testkit for Zcash

## 0.3.0.dev0 (source development)

The study now uses fresh sender wallets, randomized timing, and three shuffled complete evaluation blocks. Schema 2 analysis checks the seed-derived plan and retained sender/funding/schedule observations, and reports timing adherence and session variation. The detector rule is unchanged, with fresh calibration preceding fresh evaluation. The [complete retained run](../evidence/randomized-study/README.md) confirmed all 63 payments across 21 sessions. The frozen detector missed all independent-wallet send windows under every condition; timing adherence, session variation, and a separately labeled post-hoc overlap diagnostic explain the result. Existing schema 1 reports remain supported. This development work is not included in the published 0.2.0 package.

## 0.2.0

This release makes the verified recovery and continuous-traffic tools available as an installable package. It adds a repeated study with a detector fitted only on calibration sessions and frozen before evaluation under other network conditions and with an independent development wallet. Results include misses and false positives, with per-session observations and explicit limits.

The release includes `after-hold`, `verify-recovery`, `analyze-privacy`, and `analyze-study`, application metadata/trailer forwarding, and the disposable Docker Compose lab. Forty tests cover transport, failure controls, metadata, scoring, frozen-model integrity, and byte-preserving network conditioning. The optional study uses source-pinned zcash-devtool with an opt-in lab trust anchor; it does not represent Zashi or another consumer wallet UI.

The [retained study](../evidence/privacy-study-020/README.md) confirmed all 45 payments. Its frozen cutoff missed every send-active window from the independent wallet, whose largest client records fell three bytes below the cutoff. This is a detector transfer failure, not evidence of wallet privacy.

The package remains a research preview. Privacy results describe local send-window detection, not public-transaction linkage, identity inference, or a wallet ranking. Recompute retained reports or run the [lab](../examples/regtest/README.md) with fresh disposable wallets.

## 0.2.0.dev1 (development history)

Adds independently checkable recovery observations, a live unconfirmed-payment control, indexer restart/outage/switch scenarios, continuous-traffic privacy evaluation, and application metadata forwarding. These additions require a source checkout and are not part of PyPI 0.1.0.

## 0.2.0.dev0 (unreleased)

Development adds a disposable Compose regtest lab, a held-response fault for wallet crash tests, and broader relay transport coverage. See the [regtest instructions](../examples/regtest/README.md) for requirements, assertions, and limits. These additions are not in the published 0.1.0 package.

## 0.1.0

This research-preview release extracts the reusable adversarial layer from a complete Zingolib/Zebra/lightwalletd regtest experiment.

It includes:

- a byte-preserving TLS forwarder that logs record lengths and timing without decryption;
- a lightwalletd-compatible relay that can fail before submission, after one accepted submission, or after every submission response;
- a size-only candidate matcher that divides credit across ties and reports a random reference;
- 14 tests for parsing, byte preservation, invalid traces, CLI validation, failure boundaries, duplicate responses, input validation, and retry byte identity;
- a sanitized Zingolib v5 case study and an explicit comparison with existing Zcash and general-purpose tools.

The release does not claim that encrypted size alone deanonymizes normal wallet traffic. It does not claim a current unfixed Zingolib bug. Its case study used a favorable observer model on an isolated NU6.2 regtest chain. Current development code contains related delivery recovery logic.

The next adoption milestone is one maintainer-acknowledged integration into an existing wallet or ecosystem test suite.

The installed wheel was also exercised against released Zingolib v5.0.0, lightwalletd, and Zebra. A newly constructed transaction was accepted before its response was lost, stayed byte-identical across four attempts, appeared in the real node mempool, and reached three confirmations in node and wallet state.

Version 0.1.0 is available on [PyPI](https://pypi.org/project/wallet-privacy-testkit/0.1.0/). The publishing workflow verified the GitHub release checksums and used Trusted Publishing with package attestations, without a stored PyPI credential. Both published artifact hashes match the reviewed release. A clean PyPI installation passed all 14 tests, CLI checks, and dependency consistency checks.
