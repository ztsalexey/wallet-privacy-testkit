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


## Development 0.2.0.dev1

- [x] Added schema-2 recovery verification, a live negative control, three indexer recovery scenarios, held-out continuous-traffic analysis, and application metadata forwarding.
- [x] Passed all 36 tests in the six-version/platform CI matrix and in a clean wheel installation.
- [x] Completed the fresh Compose recipe on OrbStack ARM64 and native Linux Docker x86-64.
- [x] Independently recomputed both recovery and privacy reports with the installed CLI.
- [x] Retained [observations, metadata traces, provenance, results, and limitations](../evidence/zingolib-v5-continuous/README.md).

These development additions are included in version 0.2.0.


## 0.2.0 validation

- [x] Forty tests pass on Python 3.11–3.13 across Linux and macOS.
- [x] The complete OrbStack study confirmed all 45 payments across 15 sessions, using a detector frozen before evaluation.
- [x] Retained metadata, frozen model, observations, and checksums allow independent recomputation of the [study](../evidence/privacy-study-020/README.md).
- [x] The frozen cutoff failed to transfer to the independent development wallet; results and timing, lifecycle, and sampling limitations are explicit.
- [x] Native Linux Docker passed the five recovery scenarios, live negative control, and continuous-traffic regression.

Publication requires auditing the final wheel and source archive, testing a clean wheel installation, committing their exact SHA-256 checksums, and publishing through Trusted Publishing. After publication, verify PyPI file hashes and attestations and test a fresh PyPI installation. The tagged [release page](https://github.com/ztsalexey/wallet-privacy-testkit/releases/tag/v0.2.0) and publishing workflow record the publication outcome.


## Development 0.3.0.dev0

- [x] Forty-seven tests pass across Python 3.11–3.13 on Linux/macOS and against a clean development wheel.
- [x] Source and built wheel/source-archive audits pass; historical schema 1 evidence still reproduces exactly.
- [x] The plan was committed before full collection; a separate local check recorded the frozen model hash before evaluation results.
- [x] The complete OrbStack study confirmed 63 payments with 21 distinct fresh senders, identical funding, randomized phases, and shuffled condition blocks.
- [x] Native Linux Docker passed the recovery scenarios, live negative control, and smaller continuous-traffic regression.
- [x] Retained [traces, observations, provenance, results, and limitations](../evidence/randomized-study/README.md) reproduce with the installed analyzer.
- [x] A post-hoc per-payment overlap diagnostic is explicitly separate from the predeclared window scores.

This development work is included in 0.3.0. The older 0.2.0 package does not read study schema 2.


## 0.3.0 validation

- [x] Sixty-two tests pass in the Python 3.11–3.13 Linux/macOS matrix and against a clean wheel installation.
- [x] The installed wheel verifies its packaged real example without a source checkout or Docker.
- [x] Recovery failures, corrupt or missing privacy evidence, and malformed study plans produce failed verification reports; the negative control remains required.
- [x] A real socket regression confirms that a TCP half-close preserves the peer's remaining response. Trace validation now checks connection lifecycle and byte accounting per connection.
- [x] Every retained valid privacy and study report still recomputes unchanged.
- [x] A fresh OrbStack run passes five recovery scenarios, the live negative control, and six confirmed privacy payments; its disposable state is removed.
- [x] A fresh native Linux Docker run passes the same regression using the release implementation.
- [x] Package metadata, source contents, both built artifacts, and current dependency advisories pass their audits.
- [x] Publication verifies the exact two artifact names, tag/version agreement, and committed SHA-256 hashes; extra uploads cannot enter the publish set.

The [fresh release regressions](../evidence/release-030/README.md) retain both platforms’ observations, metadata traces, results, and collection/verification provenance.

The GitHub [0.3.0 release](https://github.com/ztsalexey/wallet-privacy-testkit/releases/tag/v0.3.0), committed checksum file, and [publishing workflow](https://github.com/ztsalexey/wallet-privacy-testkit/actions/workflows/publish.yml) record publication. Before finishing publication, compare both PyPI artifact hashes with the reviewed files, check their attestations, and exercise a fresh PyPI installation. Repository CI also installs each built wheel in an isolated environment and runs its packaged example outside the checkout.
