# Disposable wallet recovery and privacy lab

This example builds released Zingolib v5.0.0, the independent zcash-devtool development wallet, and lightwalletd from checksum-pinned source archives, starts Zebra 6.2.3, creates two fresh wallets, mines and shields regtest funds, and runs five recovery scenarios, a live negative control, and two continuous-traffic sessions with six additional payments. It uses Docker Compose without host networking, published ports, existing wallet directories, or OrbStack-specific services.

The first build downloads Rust/Go dependencies and compiles the wallet. Allow several GB of disk space, at least 8 GB available memory, and substantially more time for the first run than for a cached run. Build downloads require Internet access. Runtime services share an internally isolated Docker network.

From the repository root with Python 3.11+ and Docker Compose v2:

```sh
python3 examples/regtest/run.py --output /tmp/wpt-first-run
```

To inspect a completed run first, follow the [quickstart](../../docs/QUICKSTART.md). It verifies retained real observations without building images. Install this source checkout with `python -m pip install .` to use the current CLI alongside the runner.

To explicitly choose OrbStack on macOS:

```sh
python3 examples/regtest/run.py --context orbstack --output /tmp/wpt-orbstack-run
```

Every output directory must be new. The wrapper builds the image, uses a unique Compose project, and removes only that project's containers, network, and disposable volume afterward, including after a failed experiment. Wallet seeds, keys, chain data, and raw wallet/indexer logs stay in that volume. The host receives a build log, a sanitized `report.json`, two metadata-only `*.trace.jsonl` files, `privacy-manifest.json`, and the recomputed `privacy-report.json`. A hard termination of the wrapper can interrupt cleanup; its first output prints the unique project name for targeted cleanup with the same Compose file and `WPT_OUTPUT` setting. Do not use engine-wide prune commands.

`--skip-build` reuses the local `wallet-privacy-testkit-regtest:local` image; use it only when its source is known and unchanged. The default builds the current checkout. No prebuilt lab image is published.

For local diagnosis, `--keep-state-on-failure` retains the uniquely named project only if a step fails. Its volume contains disposable wallet secrets and must not be published. Clean it up afterward with `WPT_OUTPUT=/path/to/output docker compose -p PRINTED_PROJECT -f examples/regtest/compose.yaml down --volumes --remove-orphans`, adding `--context orbstack` after `docker` if used for the run.

## Scenarios and pass criteria

1. **Lost first acknowledgement:** submit one Orchard payment through `after-once`. Observe one accepted transaction in the node mempool, require identical signed bytes across observed attempts, mine three blocks, and require confirmation in the reopened wallet.
2. **Crash before acknowledgement:** submit a different payment through `after-hold`. Wait until the relay records successful upstream acceptance and is holding the response, verify the wallet process is still running, then kill that process. Reopen the same on-disk wallet without resubmitting the payment, mine three blocks, and require eventual wallet confirmation.

3. **Indexer restart:** after losing the first acknowledgement, stop and restart the same indexer before reopening and synchronizing the wallet.
4. **Outage:** after losing the acknowledgement, stop the indexer, observe its endpoint as unavailable, leave it down for at least 12 seconds, then restore it and recover the wallet.
5. **Alternate indexer:** stop the original indexer, start a second instance on another port with fresh indexer state, and recover the wallet through that instance against the same node.

All five scenarios start with an empty mempool. The node's serialized transaction hash must match the relay's observed hash. The recipient's confirmed Orchard balance must increase by exactly the intended amount, and the final mempool must be empty. Any failed assertion makes the runner exit nonzero. Reports record source revisions, binary hashes, architecture, per-attempt observations, process exit codes, actual before/after balances, node transaction confirmations and hashes, mempool snapshots, and wallet recovery states. `wpt verify-recovery report.json` recomputes assertions from these observations, ignoring any claimed verdict. A schema-2 report must contain all five scenarios.

A sixth **no-mining negative control** deliberately leaves its accepted payment unconfirmed. The same verifier must detect missing node and wallet confirmation, no confirmed recipient balance increase, and a nonempty mempool, while the acceptance and transaction-identity checks still pass. The harness then mines and synchronizes that payment before starting the privacy experiment.

These reports permit independent consistency checks; they are not signed node transcripts and cannot prove that an operator supplied authentic observations. Earlier dev0 summaries retain historical value but cannot be verified with the schema-2 command.

The wallet can report a failed or missing transaction before chain synchronization; that initial state is recorded, not required to match a particular UI contract. Successful recovery means the reopened wallet reconciles the confirmed payment. The test does not resubmit a user's payment intent, prove general exactly-once delivery, emulate a power-loss filesystem failure, or establish an unfixed current Zingolib bug. It tests a pinned released wallet, not current development.

## Continuous-traffic privacy experiment

Before capture, a confirmed self-transfer creates eight 60,000-zatoshi sender notes so scheduled payments need not wait for the preceding payment’s change to become spendable. This controlled funding arrangement is recorded in the manifest.

Each of two 72-second measurement sessions keeps the same sender wallet process open, including between sends. A six-second warmup and startup/shutdown remain in the trace outside the measurement interval. The harness mines a block every three seconds and issues a sync command every six seconds, independently of scheduled sends. This released CLI does not continually restart sync by itself. Calibration sends start at seconds 14, 34, and 54; evaluation sends at seconds 10, 38, and 58. Each sends 50,000 zatoshis. The experiment checks all receipts and at least three confirmations before accepting ground truth.

The passive forwarder observes every connection during each session without decrypting traffic. The analyzer validates complete TLS accounting and trace checksums, then divides the measurement interval into 18 fixed four-second windows. Its one feature is the largest client application-data TLS record completed in each window, or zero if none completed. Payment labels never choose window boundaries or features. A window is positive if it overlaps a recorded send-command interval; all other windows are negative, including windows with synchronization traffic.

A threshold is selected only from calibration data by balanced accuracy; ties select the higher cutoff. The evaluation report includes the confusion matrix, recall, false-positive rate, precision, balanced accuracy, and individual window observations. There is no required accuracy score: a poor detector is still a valid experimental result. The runner fails on missing or inconsistent observations, not on an unfavorable privacy result.

```sh
wpt verify-run /tmp/wpt-first-run
wpt verify-recovery /tmp/wpt-first-run/report.json
wpt analyze-privacy /tmp/wpt-first-run/privacy-manifest.json
```

`verify-run` checks recovery and privacy evidence together and prints a concise summary. The individual commands above expose the full JSON results. A verified privacy experiment can contain detector misses or false positives; detection accuracy is not a pass criterion.

The sessions use one wallet, one local transport, a prescribed sync/mining schedule, and three sends per split. Neighboring windows are correlated. Command duration is operator-provided ground truth and may include work beyond network submission. The threshold is not evaluated on different wallets or networks, and these sample counts do not justify population accuracy estimates. Detection of a local send window does not identify a public transaction or a person. This is a reproducible local experiment, not a field study.

## Build and trust boundary

Base images use immutable manifest digests; wallet and indexer archives use revision URLs and SHA-256 verification. Rust and Go use the upstream dependency locks. `patch_trust.py` adds only an explicit extra-CA option to locked `zingo-netutils 5.0.1`, checks its original source hash, and verifies that the resulting Cargo lock differs only by that dependency's local path. Certificate and hostname verification stay enabled. The lab creates a server certificate at runtime with both localhost and 127.0.0.1 SANs. Peer discovery is explicitly disabled. One activation block is mined to a random bootstrap destination before wallets exist; subsequent coinbase rewards fund the fresh sender wallet.

OS packages are installed from the base distribution's repositories, so builds are source-pinned experiments, not byte-for-byte reproducible images. Downloaded dependencies retain their own licenses; the testkit's MIT-or-Apache license does not relicense them.

The recipe targets Docker Engine, OrbStack, and Docker Desktop. Only environments with recorded successful executions should be described as verified. The regular Python CI does not itself establish that the full wallet experiment passed; the separate `regtest` workflow runs it on Linux.


## Repeated two-wallet study

Add `--study` to run the [predeclared repeated study](../../docs/PRIVACY_STUDY.md) after the recovery scenarios. It replaces the two-session privacy example with three calibration sessions and eighteen evaluation sessions using fresh sender wallets, a frozen detector, emulated latency/bandwidth, and a second wallet implementation. The host receives `study-plan.json`, `frozen-detector.json`, `study-manifest.json`, `study-report.json`, and one metadata trace per session.

```sh
python3 examples/regtest/run.py --context orbstack --study --output /tmp/wpt-study
wpt verify-run /tmp/wpt-study
wpt analyze-study /tmp/wpt-study/study-manifest.json
```

Version 0.3.0 uses study schema 2, with fresh senders and shuffled complete blocks. A scheduling seed is generated and the plan saved before lab setup; use `--study-seed` with 64 lowercase hexadecimal characters to reproduce the schedule, never wallet keys. Use the matching 0.3.0 analyzer and source release. The runner saves `verification.json` and `verification.xml` automatically and prints a concise summary; the individual analysis commands remain available for detailed output. See the [study design](../../docs/PRIVACY_STUDY.md).
