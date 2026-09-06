# Repeated privacy study

The optional `--study` experiment tests whether one detector transfers from its calibration sessions to later sessions, different emulated network conditions, and an independent wallet implementation. It is separate from the smaller two-session example and does not rank wallets or estimate population privacy.

## Fixed design

The runner writes `study-plan.json` before collecting measurements. The committed recipe specifies 15 sessions, in this order:

| Split | Wallet implementation | Condition | Sessions |
| --- | --- | --- | ---: |
| Calibration | Zingolib v5.0.0 | Baseline | 3 |
| Evaluation | Zingolib v5.0.0 | Baseline | 3 |
| Evaluation | Zingolib v5.0.0 | Added latency and jitter | 3 |
| Evaluation | Zingolib v5.0.0 | Constrained bandwidth | 3 |
| Evaluation | zcash-devtool | Baseline | 3 |

Each session contains 96 seconds of measurement in 24 fixed four-second windows, after a six-second warmup. There are three scheduled 50,000-zatoshi payments per session: offsets 16/44/72, 20/48/76, and 12/40/68 seconds for repetitions 1/2/3. The harness requests synchronization every six seconds and generates a block every three seconds after the preceding generation completes. Commands may delay subsequent scheduled work; actual timestamps are retained. Funding and settlement occur outside measurement intervals. Eight 60,000-zatoshi outputs fund each session, with ten blocks mined before capture.

The feature and labels match `analyze-privacy`: the largest client outer TLS type-23 record completed in each window, with a positive label when the window overlaps a successful send command. The cutoff maximizes pooled calibration balanced accuracy, preferring the higher cutoff on a tie. `frozen-detector.json` is written and hashed after all calibration sessions and before any evaluation session. It is never refitted during evaluation.

The analyzer rejects incomplete planned session sets, reused traces, checksum mismatches, invalid payment receipts, a model that differs from the calibration-only fit, and a freeze timestamp after evaluation starts. It reports each session and grouped confusion matrices. A low detection score is a valid result, not a test failure. File checks and timestamps establish internal consistency, not authenticity of operator-supplied observations.

## Network conditions

A separate local TCP forwarder conditions each direction independently, downstream of the passive capture point. It preserves bytes. The baseline uses no added delay or pacing. The latency condition adds 25 ms per read with deterministic uniform jitter of ±10 ms. The bandwidth condition adds 5 ms per read plus pacing at 65,536 bytes/s per direction. Reads are capped at 16,384 bytes.

This is stream conditioning, not a packet-level WAN simulation. Timing depends on TCP read boundaries, backpressure, and local scheduling; the configured delay is not a measured RTT, and the rate is not an Internet bandwidth guarantee. The experiment does not cover packet loss, mobile radio behavior, Tor, congestion control in real networks, or adversarial indexers.

## Independent wallet and trust boundary

The second implementation is the official [zcash-devtool](https://github.com/zcash/zcash-devtool), pinned to revision `5a26ee854e634a4e88d1d79dab13f8fbb1eac6b8`. It uses `zcash_client_backend` and `zcash_client_sqlite`. It is a development wallet, not a consumer application and not a proxy for Zashi. The archive hash and build inputs are pinned in the lab Dockerfile.

Its normal local-host transport is plaintext. The small hash-checked lab patch explicitly enables TLS and adds the generated lab certificate as a trust anchor only when `ZCASH_LAB_CA` is set. Certificate and hostname verification remain enabled. Payment, sync, and transaction-construction code is unchanged. The wallet is built with regtest support and explicit upgrade heights matching the lab node.

Zingolib runs in one persistent interactive process per session. zcash-devtool has no equivalent interactive mode, so its sync and payment commands run as separate processes under one continuous capture. This lifecycle difference is part of the observed environment; it prevents interpreting the cross-implementation result as a controlled ranking of wallet privacy.

## Run and interpret

```sh
python3 examples/regtest/run.py --context orbstack --study --output /tmp/wpt-study
wpt analyze-study /tmp/wpt-study/study-manifest.json
```

The first build compiles both wallet implementations. Allow at least 8 GB available memory, several GB of disk, and roughly half an hour for the study after compilation, depending on hardware. All runtime funds and keys are disposable and remain in the isolated project volume. The usual wrapper cleanup and failure-retention options apply.

The 45 scheduled payments produce more than 45 labeled windows because command intervals can overlap multiple windows. Neighboring windows and sessions sharing a wallet state and node are correlated. Grouped rates are descriptive counts; no independent-sample confidence intervals are claimed. The conditions run in a fixed order, so wallet history and elapsed time are potential confounders. The same fresh wallets are reused across repetitions within a run; repetitions are not independent wallet samples. A cross-condition detector does not identify a public transaction or a user.

All scheduled send offsets are multiples of the four-second window width. This nominal alignment favors fitting short operations inside a window; unknown or randomized send phases could produce different recall. The [retained 0.2.0 study](../evidence/privacy-study-020/README.md) reports the complete results, including failure of the frozen cutoff to transfer to the independent wallet.
