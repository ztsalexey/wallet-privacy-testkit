# Disposable wallet recovery lab

This development example builds released Zingolib v5.0.0 and lightwalletd from checksum-pinned source archives, starts Zebra 6.2.3, creates two fresh wallets, mines and shields regtest funds, and tests two newly constructed payments. It uses Docker Compose without host networking, published ports, existing wallet directories, or OrbStack-specific services.

The first build downloads Rust/Go dependencies and compiles the wallet. Allow several GB of disk space, at least 8 GB available memory, and substantially more time for the first run than for a cached run. Build downloads require Internet access. Runtime services share an internally isolated Docker network.

From the repository root with Python 3.11+ and Docker Compose v2:

```sh
python3 examples/regtest/run.py --output /tmp/wpt-first-run
```

To explicitly choose OrbStack on macOS:

```sh
python3 examples/regtest/run.py --context orbstack --output /tmp/wpt-orbstack-run
```

Every output directory must be new. The wrapper builds the image, uses a unique Compose project, and removes only that project's containers, network, and disposable volume afterward, including after a failed experiment. Wallet seeds, keys, chain data, and raw wallet/indexer logs stay in that volume. The host receives a build log and a sanitized `report.json`. A hard termination of the wrapper can interrupt cleanup; its first output prints the unique project name for targeted cleanup with the same Compose file and `WPT_OUTPUT` setting. Do not use engine-wide prune commands.

`--skip-build` reuses the local `wallet-privacy-testkit-regtest:local` image; use it only when its source is known and unchanged. The default builds the current checkout. No prebuilt lab image is published.

For local diagnosis, `--keep-state-on-failure` retains the uniquely named project only if a step fails. Its volume contains disposable wallet secrets and must not be published. Clean it up afterward with `WPT_OUTPUT=/path/to/output docker compose -p PRINTED_PROJECT -f examples/regtest/compose.yaml down --volumes --remove-orphans`, adding `--context orbstack` after `docker` if used for the run.

## Scenarios and pass criteria

1. **Lost first acknowledgement:** submit one Orchard payment through `after-once`. Observe one accepted transaction in the node mempool, require identical signed bytes across observed attempts, mine three blocks, and require confirmation in the reopened wallet.
2. **Crash before acknowledgement:** submit a different payment through `after-hold`. Wait until the relay records successful upstream acceptance and is holding the response, verify the wallet process is still running, then kill that process. Reopen the same on-disk wallet without resubmitting the payment, mine three blocks, and require eventual wallet confirmation.

Both scenarios start with an empty mempool. The node's serialized transaction hash must match the relay's observed hash. The recipient's confirmed Orchard balance must increase by exactly the intended amount, and the final mempool must be empty. Any failed assertion makes the runner exit nonzero. Reports record source revisions, binary hashes, architecture, attempt counts, process exit codes, and observed recovery states.

The wallet can report a failed or missing transaction before chain synchronization; that initial state is recorded, not required to match a particular UI contract. Successful recovery means the reopened wallet reconciles the confirmed payment. The test does not resubmit a user's payment intent, prove general exactly-once delivery, emulate a power-loss filesystem failure, or establish an unfixed current Zingolib bug. It tests a pinned released wallet, not current development.

## Build and trust boundary

Base images use immutable manifest digests; wallet and indexer archives use revision URLs and SHA-256 verification. Rust and Go use the upstream dependency locks. `patch_trust.py` adds only an explicit extra-CA option to locked `zingo-netutils 5.0.1`, checks its original source hash, and verifies that the resulting Cargo lock differs only by that dependency's local path. Certificate and hostname verification stay enabled. The lab creates a server certificate at runtime with both localhost and 127.0.0.1 SANs. Peer discovery is explicitly disabled. One activation block is mined to a random bootstrap destination before wallets exist; subsequent coinbase rewards fund the fresh sender wallet.

OS packages are installed from the base distribution's repositories, so builds are source-pinned experiments, not byte-for-byte reproducible images. Downloaded dependencies retain their own licenses; the testkit's MIT-or-Apache license does not relicense them.

The recipe targets Docker Engine, OrbStack, and Docker Desktop. Only environments with recorded successful executions should be described as verified. The regular Python CI does not itself establish that the full wallet experiment passed; the separate `regtest` workflow runs it on Linux.
