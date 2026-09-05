# Contributing

Open an issue before implementing a new wallet adapter, protocol method, or privacy claim. Describe the observer, the information available to it, the candidate set, the expected wallet state, and how the result will be falsified.

Contributions must:

- use disposable wallets and regtest or another isolated network;
- avoid committing seeds, private keys, raw signed transactions, or identifying captures;
- preserve ties and failed observations in analysis;
- distinguish a controlled fault from an observed production failure;
- add tests for any new fault boundary or metric;
- update the threat model when assumptions change.

Run the checks from the repository root:

```sh
python -m unittest discover -s tests -v
python scripts/release_audit.py
python -m build
```

Use the style already present in the package. Keep the core independent of a particular wallet's state format and place integration-specific instructions under `examples/`.

Before proposing a change to another repository, follow that repository's issue and contribution process. Do not send a stream of unsolicited wallet PRs from this project.

