# Repeated two-wallet privacy study (0.2.0)

The complete [predeclared plan](study-plan.json) ran on September 6, 2026 UTC in Linux ARM64 containers on OrbStack. All 45 payments across 15 sessions confirmed, and every session’s confirmed recipient balance increased by exactly 150,000 zatoshis. The same fresh lab also passed all five recovery scenarios and detected the live unmined-payment control; see its [recovery observations](report.json).

The [manifest](study-manifest.json), [frozen detector](frozen-detector.json), [full computed report](study-report.json), and all 15 complete metadata traces are retained here. [Provenance and checksums](provenance.json) record the collector and verifier revisions. Collection used commit `28c6bd5ec6dc43a58552993942c27c16150ec9b2`; subsequent changes only strengthened offline duration/overlap validation and its tests. The final verifier exactly reproduces the original report.

## Result

The 9,207-byte cutoff was fitted to three Zingolib calibration sessions, written and hashed before evaluation, then applied unchanged to twelve evaluation sessions. It detected send-active windows in repeated Zingolib sessions and under the emulated network conditions. It flagged no window in any of the three zcash-devtool sessions, despite all nine of that wallet’s payments confirming.

These are **window counts, not payment counts**. Each group has three sessions and 72 four-second windows.

| Split / wallet / condition | TP | FP | FN | TN | Recall | False-positive rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| calibration / zingolib / baseline | 9 | 0 | 1 | 62 | 90.0% | 0.0% |
| evaluation / zingolib / baseline | 9 | 0 | 2 | 61 | 81.8% | 0.0% |
| evaluation / zingolib / latency | 9 | 0 | 0 | 63 | 100.0% | 0.0% |
| evaluation / zingolib / bandwidth | 9 | 0 | 0 | 63 | 100.0% | 0.0% |
| evaluation / zcash-devtool / baseline | 0 | 0 | 11 | 61 | 0.0% | 0.0% |

The largest client record feature in each independent-wallet evaluation session was 9,204 bytes, three bytes below the frozen cutoff. This explains why this threshold never fired there. We did not refit it to that wallet. The finding demonstrates fragility of this size cutoff across implementations; it does not establish that either wallet protects or exposes a user’s identity.

No false positives were observed in the 248 negative evaluation windows. That small, correlated sample does not establish a zero false-positive rate in normal use. The baseline missed two send-active windows; all baseline payments still confirmed. Different command durations affect how many windows receive a positive label.

## Interpretation limits

The [methodology](../../docs/PRIVACY_STUDY.md) specifies funding, timing, stream conditioning, wallet lifecycle, and the observer. All scheduled send offsets are multiples of the four-second window width. That nominal alignment favors fitting short operations inside a window; unknown or randomized send phases could produce different recall. High scores here are not field-performance estimates.

The same wallet state and node are reused across repetitions, conditions run in a fixed order, and windows are correlated. The independent implementation is the official zcash-devtool development wallet, not a consumer UI. Zingolib uses a persistent interactive process; devtool uses one process per command under continuous capture. Network conditioning delays/paces TCP reads, not real WAN packets. The jitter generator uses fixed direction seeds reset for each connection. There is no anonymity set, public-transaction candidate matching, or identity inference in this study.

The evidence verifies supplied observations’ consistency, not their authenticity. No accuracy threshold determines whether the lab passes: incomplete or inconsistent data fail; poor detection remains a valid result. Development smoke tests verified the independent wallet and exposed an already-closed-socket cleanup issue, corrected before this recorded run.

## Recompute

From an installed 0.2.0 environment and this source checkout/archive:

```sh
wpt analyze-study evidence/privacy-study-020/study-manifest.json
wpt verify-recovery evidence/privacy-study-020/report.json
```

A separate native Linux Docker run of the collection source passed the regular five recovery scenarios, live negative control, and two-session privacy regression: [Actions run 34008979902](https://github.com/ztsalexey/wallet-privacy-testkit/actions/runs/34008979902). Its [recovery report](linux-regression/report.json), [privacy manifest](linux-regression/privacy-manifest.json), [computed privacy report](linux-regression/privacy-report.json), and both metadata traces are also retained. That regression fits its own calibration cutoff; it is not a cross-platform evaluation of the frozen study detector.

The test suite includes 40 tests, including altered-model rejection, evaluation-label independence, byte-preserving conditioning, and rejection of a trimmed negative observation window. Release package/source audits also scan the retained traces. Wallet keys, seed phrases, TLS keys, raw signed transactions, and raw wallet logs are excluded. The disposable study volume was removed after successful completion.
