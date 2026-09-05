# Wallet Privacy Testkit for Zcash 0.1.0

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

The release workflow publishes only checksum-verified GitHub release assets. PyPI authentication uses a short-lived trusted-publisher identity and produces package attestations; it contains no repository token or PyPI password.
