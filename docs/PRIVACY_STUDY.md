# Repeated privacy study

The optional `--study` experiment tests whether one detector transfers from its calibration sessions to later sessions, different emulated network conditions, and an independent wallet implementation. It is separate from the smaller two-session example and does not rank wallets or estimate population privacy.

## Randomized design (source development, 0.3.0.dev0)

The runner writes `study-plan.json` on the host before building images or creating wallets. A fresh public 256-bit seed determines the schedule; `--study-seed` accepts a saved seed for replay. Hash-derived draws and ordering are stable across Python versions. This seed controls timing and order only: wallet keys come from the wallets' normal random generation and are never reproducible from the plan.

The recipe has 21 sessions and 63 scheduled payments:

| Split | Design | Sessions |
| --- | --- | ---: |
| Calibration | Fresh Zingolib sender, baseline, three repetitions | 3 |
| Evaluation | Three blocks, each containing both wallet implementations under baseline, latency/jitter, and bandwidth conditions | 18 |

Each six-session evaluation block is shuffled independently. This spreads conditions through chain growth and elapsed run time; it does not fully counterbalance all possible orders. Calibration always finishes before evaluation. Every session creates a previously absent sender directory and a new wallet, checks zero initial balance, then receives eight 60,000-zatoshi outputs. Ten funding confirmations and 480,000 spendable Orchard zatoshis are required before capture. A sender address hash and state-creation time are retained, without addresses or keys. The node, indexer, funding wallet, and recipient remain shared.

Each session contains 96 seconds of measurement in 24 fixed four-second windows, after a six-second warmup. Three 50,000-zatoshi sends are scheduled at nanosecond-resolution offsets drawn from [12,24), [40,52), and [68,80) seconds. These spans cover three whole scoring windows each, without snapping to their boundaries. Sync requests occur every six seconds with a separately drawn initial phase. Blocks are requested every three seconds after the preceding generation completes. The report retains scheduled and actual send times, actual phase within the scoring grid, and scheduling delays. Commands can delay later work; randomizing intended time does not guarantee uniform actual time. No sessions are dropped for poor detection or inconvenient delays.

The detector is unchanged from 0.2.0: largest client outer TLS type-23 record completed in each window; positive labels overlap a successful send command. The cutoff maximizes pooled calibration balanced accuracy, preferring the higher cutoff on a tie. Only newly collected calibration sessions fit it. The model is written and hashed before any new evaluation session, with no retuning after evaluation. This is a stronger test of the existing detector, not a new detector tuned to the earlier three-byte transfer failure.

Study schema 2 requires exact regeneration of the plan from its seed, all 21 sessions in order, distinct sender address hashes and funding/payment IDs, observed fresh empty sender state and funding balances, complete intended payment counts, and the declared schedule. It also checks trace/model/plan hashes, complete windows, non-overlap, confirmed receipts, and calibration-only freezing. Supplied observations establish internal consistency, not authenticity or proof of independent randomness.

Reports include each session's confusion matrix, pooled window counts, and the mean/min/max of three session rates for each group. The ranges describe observed variation; they are not confidence intervals. A low detection score is a valid result, not a lab failure. The analyzer continues to reproduce the [historical 0.2.0 schema 1 study](../evidence/privacy-study-020/README.md), which used shared senders, aligned sends, and a fixed condition order.

## Network conditions

A separate local TCP forwarder conditions each direction independently, downstream of the passive capture point. Jitter uses a per-session seed with separate streams for each connection and direction. It preserves bytes. The baseline uses no added delay or pacing. The latency condition adds 25 ms per read with deterministic uniform jitter of ±10 ms. The bandwidth condition adds 5 ms per read plus pacing at 65,536 bytes/s per direction. Reads are capped at 16,384 bytes.

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

The first build compiles both wallet implementations. Allow at least 8 GB available memory, several GB of disk, and roughly an hour for recovery checks and the study after compilation, depending on hardware. All runtime funds and keys are disposable and remain in the isolated project volume. The usual wrapper cleanup and failure-retention options apply.

The 63 scheduled payments may produce more than 63 labeled windows because command intervals can overlap multiple windows. Neighboring windows are correlated. Fresh sender wallets remove sender-history reuse across sessions, but the shared node, indexer, recipient, funding source, growing chain, and wallet lifecycle differences remain confounders. Three observations per wallet/condition are a small local sample, not population evidence or independent-sample confidence intervals. A cross-condition detector does not identify a public transaction or a user.

## Retained run

The [complete randomized study](../evidence/randomized-study/README.md) retains all 21 traces, observations, frozen model, timing adherence, results, and provenance. All 63 payments confirmed. The unchanged cutoff failed to transfer to the independent wallet under every condition. The report labels a later per-payment coverage diagnostic separately from the predeclared window metrics; neither is an estimate of field privacy.
