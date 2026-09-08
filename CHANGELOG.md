# Changelog

## 0.3.0 - 2026-09-07

- Adds `wpt verify-run` to check a complete lab run, separate recovery assertions from privacy evidence consistency, and produce a readable summary, JSON, or JUnit XML with meaningful exit codes.
- Includes a compact real recorded example in the wheel: `wpt verify-run --example` works without Docker, a source checkout, or a wallet run.
- Makes the randomized 21-session study available in the release, with fresh senders, randomized timing, shuffled condition blocks, and calibration-only detector freezing. Historical study evidence remains supported.
- Saves JSON and JUnit verification results automatically from the Compose runner and retains them in the regtest workflow.
- Adds an installation and CI quickstart, and corrects the documented evaluation-session count.
- Requires the publishing workflow's downloaded artifacts to match exactly the reviewed checksum file set, package version, and release tag; rejects additional uploads and changed files.

## 0.3.0.dev0 - Unreleased

- Replaces the source lab's study with 21 sessions: fresh sender state per session, randomized sub-window payment/sync timing, and three shuffled complete evaluation blocks covering both wallets under all three conditions.
- Saves a public scheduling seed and complete plan before any lab activity; wallet keys use their normal random generation independently of that seed.
- Adds study schema 2 validation of the regenerated design, distinct sender/funding/payment observations, funding balances, payment count, and intended scheduling. Schema 1 evidence remains readable.
- Reports actual payment phases and scheduling delays, plus per-session rate means/ranges alongside pooled window counts. The detector feature and fitting rule are unchanged.

## 0.2.0 - 2026-09-06

- Adds a repeated privacy study with a detector frozen before evaluation, emulated network conditions, and an independent zcash-devtool wallet adapter.
- Adds `wpt analyze-study`, which checks the complete declared session plan, trace and model checksums, freeze timing, payment receipts, and calibration-only threshold selection.
- Includes the recovery verifier, live negative control, five recovery scenarios, continuous capture, held-response fault, and metadata forwarding developed since 0.1.0.
- Keeps the toolkit a research preview; a stable version number does not certify wallet privacy or guarantee a stable wallet-adapter interface.

## 0.2.0.dev1 - Development history

- Added schema-v2 recovery observations and an independent offline verifier.
- Added a live no-mining negative control and tampered-evidence regression tests.
- Added indexer restart, bounded outage, and fresh alternate-indexer recovery experiments.
- Added continuous TLS capture around persistent wallets with background sync, fixed-window detection, separate calibration/evaluation sessions, and false-positive reporting.
- Forward application gRPC metadata and trailers, while suppressing acknowledgement metadata for response-loss faults.

## 0.2.0.dev0 - Unreleased

- Added `after-hold` to hold submission responses until client cancellation for process-restart tests.
- Forward client deadlines (capped at 120 seconds) and propagate cancellation to upstream calls.
- Close the upstream channel when relay readiness fails.
- Added TLS trust/hostname, RPC streaming, partial-stream error, cancellation, deadline, and held-response tests.
- Added a Docker Compose lab that builds pinned wallet/indexer sources and generates fresh regtest wallets and TLS keys.
- Added lost-acknowledgement and crash-before-acknowledgement recovery scenarios with node, byte-identity, wallet-history, and recipient-balance checks.

## 0.1.0 - 2026-09-05

- Added a metadata-only TLS record forwarder and trace validator.
- Added three protocol-aware `SendTransaction` delivery fault modes.
- Added conservative size matching with fractional tie credit.
- Added unit and local integration tests for byte preservation, fault boundaries, retry identity, and invalid analyses.
- Validated relay method cardinalities against `lightwallet-protocol` v0.5.0 and tightened CLI and matcher input checks.
- Updated the build tool after an advisory audit and added audited, attested PyPI trusted publishing.
- Added a sanitized, independently verified Zingolib v5 regtest case study.
- Repeated the acknowledgement-loss case with the installed release wheel and a fresh real regtest transaction.
- Documented the threat model, methodology, project overlap, release process, and contribution boundaries.
