# Randomized fresh-sender study

All **63 payments across 21 sessions** confirmed on OrbStack ARM64. Each session began with a distinct fresh sender, zero initial balance, and 480,000 spendable Orchard zatoshis after identical funding. Every recipient balance increase was exactly 150,000 zatoshis. The same run passed five recovery scenarios and detected the live unmined-payment control.

The [complete plan](study-plan.json) and collector were [committed before collection](https://github.com/ztsalexey/wallet-privacy-testkit/commit/d450c2432a2a80eabe217d9d0e7190e41dd531a1). The public seed was generated once; it determines scheduling, not wallet keys. Development smoke sessions used a separate seed and separate wallets and are excluded from this dataset.

The [manifest](study-manifest.json), [frozen detector](frozen-detector.json), [computed report](study-report.json), [recovery observations](report.json), all 21 complete metadata traces, and [provenance/checksums](provenance.json) are retained. A clean installed development wheel independently reproduced the report. After collection started, offline checks were strengthened to reject a schema downgrade and prevent mutable plan values from leaking into later generated plans; the collector, serialized plan, and detector rule did not change. A separate local observation recorded the frozen model hash while only the three calibration results existed.

## Results

The unchanged calibration-only fitting rule selected a **9,207-byte cutoff** on the three fresh calibration sessions. It was applied unchanged to all 18 evaluation sessions. Each group contains three sessions, 72 four-second windows, and nine payments. **Window counts are not payment counts.**

| Split / wallet / condition | TP | FP | FN | TN | Pooled recall | Pooled FPR | Session recall mean (range) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| calibration / zingolib / baseline | 9 | 0 | 7 | 56 | 56.2% | 0.0% | 56.7% (50.0%–60.0%) |
| evaluation / zingolib / baseline | 9 | 0 | 4 | 59 | 69.2% | 0.0% | 70.0% (60.0%–75.0%) |
| evaluation / zingolib / latency | 9 | 0 | 6 | 57 | 60.0% | 0.0% | 66.7% (50.0%–100.0%) |
| evaluation / zingolib / bandwidth | 9 | 0 | 8 | 55 | 52.9% | 0.0% | 53.3% (50.0%–60.0%) |
| evaluation / zcash-devtool / baseline | 0 | 0 | 16 | 56 | 0.0% | 0.0% | 0.0% (0.0%–0.0%) |
| evaluation / zcash-devtool / latency | 0 | 0 | 15 | 57 | 0.0% | 0.0% | 0.0% (0.0%–0.0%) |
| evaluation / zcash-devtool / bandwidth | 0 | 0 | 16 | 56 | 0.0% | 0.0% | 0.0% (0.0%–0.0%) |

The independent-wallet evaluation produced no flagged window under any condition, despite all 27 of its payments confirming. Its largest client record in every session was 9,204 bytes, three bytes below the frozen cutoff. The transfer failure persisted in this fresh-sender experiment. There were no false positives in 340 negative evaluation windows; this small correlated sample does not establish a zero false-positive rate outside the lab.

### Post-hoc interpretation: windows versus payments

A [separately labeled diagnostic](coverage-diagnostic.json), added after seeing the full results, checks whether each payment overlaps at least one flagged window. All 27 Zingolib evaluation payments did; none of the 27 independent-wallet payments did. Thus, missing some send-active windows is not equivalent to missing an entire payment operation. Commands can span multiple scoring windows. This diagnostic ignores false alarms outside commands and does not replace the predeclared window confusion matrices or establish transaction linkage.

Recompute this secondary check with `python scripts/study_diagnostic.py evidence/randomized-study/study-manifest.json`. The [script](../../scripts/study_diagnostic.py) first independently verifies and recomputes the primary study report.

## Timing adherence

Payment offsets were drawn inside three twelve-second spans without snapping to the four-second scoring grid. Sync used a separately drawn phase. These counts compare planned and actual send starts by phase within that grid:

| Phase in four-second window | Planned starts | Actual starts |
| --- | ---: | ---: |
| [0, 1) seconds | 14 | 13 |
| [1, 2) seconds | 12 | 13 |
| [2, 3) seconds | 24 | 22 |
| [3, 4) seconds | 13 | 15 |

Scheduling delay: median **0.003 s**, nearest-rank 95th percentile **0.021 s**, maximum **0.585 s**. Actual command intervals, phases, and delays are retained for every payment. Delays were not removed or corrected after collection.

## Interpretation limits

Fresh senders remove sender-history reuse; shuffled complete blocks distribute conditions through run time. The node, indexer, recipient, funding wallet, growing chain, hardware, and process lifecycle remain shared or different across implementations. zcash-devtool is a development wallet, not a consumer UI. Stream conditioning operates on TCP reads, not WAN packets. The public seed reproduces the plan, not wallet keys, traffic, or operating-system scheduling.

Three sessions per group remain a small local sample. Neighboring windows are correlated; pooled rates weight sessions by their positive/negative window counts. Session means and observed ranges are descriptive, not confidence intervals. No detection accuracy threshold determines success, and the result does not rank wallet privacy or establish transaction linkage or identity inference. The verifier checks supplied observations, not their authenticity.

The [0.2.0 study](../privacy-study-020/README.md) used aligned sends and reused sender state. Several design factors changed together here, so differences between runs cannot be attributed solely to randomized timing or fresh state. No detector was retuned against either evaluation set.

## Recompute

Use the source development version (0.3.0.dev0); published PyPI 0.2.0 does not understand schema 2:

```sh
python -m pip install .
wpt analyze-study evidence/randomized-study/study-manifest.json
wpt verify-recovery evidence/randomized-study/report.json
```

The separate [native Linux regression](https://github.com/ztsalexey/wallet-privacy-testkit/actions/runs/34015912957) passed on the collector source. Its [recovery report](linux-regression/report.json), [privacy manifest](linux-regression/privacy-manifest.json), [computed report](linux-regression/privacy-report.json), and two traces are retained and independently verified. It fits its own cutoff on the smaller two-session design; it is not cross-platform evaluation of this frozen study model.

The [methodology](../../docs/PRIVACY_STUDY.md) describes funding, the plan, wallets, network conditions, and remaining confounders. Raw wallet logs, keys, addresses, wallet seed phrases, and signed transaction bytes are excluded. The disposable full-study project is cleaned by the runner after success.

Validation: all 47 tests passed on Python 3.11–3.13 across Linux and macOS and against a clean development wheel installation. The [final native Linux workflow](https://github.com/ztsalexey/wallet-privacy-testkit/actions/runs/34017199858) also passed.
