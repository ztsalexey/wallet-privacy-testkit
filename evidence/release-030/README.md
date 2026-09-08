# 0.3.0 live release regressions

These are fresh two-session regression runs for the 0.3.0 release. Each run checks five payment-recovery scenarios and the live no-mining control, then confirms six payments during continuous TLS capture. The 21-session randomized study remains a separate retained experiment; its frozen detector and historical results are unchanged.

## Recompute

With Wallet Privacy Testkit 0.3.0 installed, from a source checkout or extracted source archive:

```sh
wpt verify-run evidence/release-030/orbstack-aarch64
wpt verify-run evidence/release-030/linux-x86_64
```

The combined command recomputes the recovery assertions and privacy analysis from observations and trace hashes. It does not trust saved verdicts. Use `--format junit --output verification.xml` to create a new CI report.

## Provenance and limits

Each platform directory contains sanitized observations, two metadata-only traces, the privacy manifest and recomputed report, a compact verification report, and a provenance file with SHA-256 hashes. The provenance identifies the source used for collection and verification. No wallet database, seed, TLS key, raw transaction, raw runtime log, or chain state is retained.

The OrbStack collector was built from the working tree before the version bump and reports 0.3.0.dev0. It includes the corrected half-close handling and per-connection trace validation. Its eight recorded collector source hashes match the 0.3.0 verification commit. The native Linux workflow exercises the committed 0.3.0 source and the runner's automatic JSON/JUnit exports. Each run's Docker project is disposable and cleaned after completion.

Each run fits its own cutoff from its calibration session. Differences between these small runs are not a cross-platform evaluation of a shared model. TP/FP/FN/TN count four-second windows, not transactions. Each split contains three payments; neighboring windows are correlated, and send-command duration is operator-provided ground truth. A verified report establishes consistency of supplied observations, not authenticity or wallet privacy. There is no required detector accuracy threshold.

## Recorded results

| Run | Calibration cutoff (bytes) | Evaluation TP / FP / FN / TN | Recall | False-positive rate |
| --- | ---: | --- | ---: | ---: |
| orbstack-aarch64 | 98 | 3 / 2 / 3 / 10 | 50.0% | 16.7% |
| linux-x86_64 | 9207 | 3 / 0 / 6 / 9 | 33.3% | 0.0% |

Both runs pass recovery and evidence consistency verification. The [native Linux workflow](https://github.com/ztsalexey/wallet-privacy-testkit/actions/runs/34172732719) also verifies the runner’s automatic JSON and JUnit report exports.
