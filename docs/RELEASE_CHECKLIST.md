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

## Required immediately before public publication

- [ ] Reconfirm the package and repository names immediately before creation or upload; prior checks do not reserve them.
- [ ] Create the repository, enable private vulnerability reporting and branch protection, and run the declared GitHub Actions matrix.
- [ ] Configure the PyPI pending trusted publisher for `.github/workflows/publish.yml` and the `pypi` environment.
- [ ] Tag the exact reviewed commit as `v0.1.0` and attach the locally reproduced artifacts plus SHA-256 checksums.
- [ ] Ask the first wallet maintainer which repository should own the adapter before opening any upstream PR.

No public upload, repository creation, issue, or PR is part of the local release preparation.
