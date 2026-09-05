# Changelog

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
