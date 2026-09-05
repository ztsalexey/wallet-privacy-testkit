# Release checklist

## Completed for 0.1.0

- [x] The project has a narrow name and description.
- [x] Runtime modules are separated from the original research archive.
- [x] No wallet state, seeds, TLS keys, compiled binaries, downloaded repositories, or raw signed transactions are included.
- [x] The passive capture and semantic relay have separate threat models.
- [x] The matcher preserves ties and rejects singleton candidate batches.
- [x] Fault modes have local integration tests against a real gRPC server implementation.
- [x] The retained case study is sanitized and labels its observer advantages and limits.
- [x] Runtime and development dependencies are declared, with an exact development lock list.
- [x] MIT and Apache-2.0 license texts are included.
- [x] Security and contribution policies are present.
- [x] The source distribution and wheel are built and audited locally.
- [x] Local links, version declarations, forbidden artifacts, and private-key markers are checked by `scripts/release_audit.py`.
- [x] The existing full Zingolib regtest evidence was independently reverified after packaging.
- [x] Direct, adjacent, and general-purpose alternatives were reviewed using current primary project documentation.
- [x] The independent name and “for Zcash” descriptor were checked against the current Zcash Foundation trademark policy.
- [x] Exact-name GitHub and PyPI checks found no existing project on September 5, 2026; this does not reserve the name.
- [x] The repository owner, source URL, issue URL, citation URL, and private security-reporting route target `ztsalexey/wallet-privacy-testkit`.
- [x] Pinned development dependencies pass `pip-audit`, and CI repeats the advisory check.
- [x] The PyPI workflow verifies release-asset checksums and uses Trusted Publishing with attestations.

## GitHub publication

- [x] Reconfirmed the repository name before creation and the package name on September 5, 2026. PyPI availability does not reserve the name.
- [x] Created the public repository and enabled private vulnerability reporting, dependency alerts, and secret scanning with push protection.
- [x] Passed all six declared GitHub Actions jobs: Python 3.11–3.13 on Linux and macOS, including tests, dependency audit, source audit, and package builds.

The [release page](https://github.com/ztsalexey/wallet-privacy-testkit/releases/tag/v0.1.0) identifies the tagged commit and downloadable wheel, source archive, and SHA-256 checksums. The [CI history](https://github.com/ztsalexey/wallet-privacy-testkit/actions/workflows/ci.yml) records the checks for each pushed commit. Main-branch protection requires all six CI checks and blocks branch deletion and force pushes.

## PyPI publication

- [x] Configured the PyPI trusted publisher: project `wallet-privacy-testkit`, owner `ztsalexey`, repository `wallet-privacy-testkit`, workflow filename `publish.yml`, environment `pypi`.
- [x] Published version 0.1.0 from the reviewed release tag through [GitHub Actions](https://github.com/ztsalexey/wallet-privacy-testkit/actions/runs/33990073305).
- [x] Verified that both PyPI artifact hashes match the tagged release checksums and that PyPI exposes publication attestations for both files.
- [x] Installed version 0.1.0 directly from PyPI in a clean virtual environment, passed all 14 tests against that installation, exercised the CLI and example matcher, and passed `pip check`.

The package is available on [PyPI](https://pypi.org/project/wallet-privacy-testkit/0.1.0/). GitHub release files can also be installed independently.

## After publication

- [ ] Ask the first wallet maintainer which repository should own the adapter before opening any upstream PR. This is an adoption step, not a release prerequisite.

PyPI publishing is gated by the repository variable `PYPI_PUBLISH_ENABLED=true`. Once the pending trusted publisher is configured, a published GitHub release triggers the workflow. To publish an existing release later, dispatch `publish.yml` using its release tag as the workflow ref. The workflow verifies the downloaded artifacts against the checksum file committed in that tag.
