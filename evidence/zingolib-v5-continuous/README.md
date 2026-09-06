# Executed recovery and continuous-traffic evidence

Both datasets below were produced from testkit source `a5d20cd877ba8d18f3a0abc719bdc135b571ae10` (0.2.0.dev1), merged in [PR #4](https://github.com/ztsalexey/wallet-privacy-testkit/pull/4). They use independently generated wallets, an empty chain volume, and the [documented Compose recipe](../../examples/regtest/README.md). Execution finished on September 6, 2026 UTC (September 5 in the local US timezone).

- **OrbStack ARM64:** [recovery observations](orbstack-aarch64/report.json), [privacy manifest](orbstack-aarch64/privacy-manifest.json), and [computed privacy report](orbstack-aarch64/privacy-report.json). Docker Engine 29.4.0 ran Linux ARM64 containers on macOS.
- **Native Linux Docker x86-64:** [recovery observations](linux-x86_64/report.json), [privacy manifest](linux-x86_64/privacy-manifest.json), and [computed privacy report](linux-x86_64/privacy-report.json), from [Actions run 34006560792](https://github.com/ztsalexey/wallet-privacy-testkit/actions/runs/34006560792).

Each dataset also retains its complete calibration and evaluation metadata traces beside the manifest. [Provenance and file checksums](provenance.json) bind the retained files to this evidence set. Docker Desktop has not been separately tested.

## Recovery results

Both platforms passed all five scenarios: lost first acknowledgement, wallet killed before acknowledgement, indexer restart, measured outage, and recovery through a fresh second indexer. Every scenario observed exactly the accepted transaction in the initially empty mempool, identical submitted bytes across attempts, three node confirmations, confirmed wallet history, an exact 100,000-zatoshi increase in the recipient’s confirmed balance, and an empty final mempool.

The live no-mining control was rejected for all four expected reasons: no node confirmation, no wallet confirmation, no confirmed recipient increase, and a transaction still in the mempool. Acceptance, submission identity, and initial mempool checks still passed. The runner settled that payment before the privacy experiment.

Schema-2 observations permit recomputing these assertions; the verifier ignores claimed verdicts. Neither the verifier nor checksums prove the observations are authentic. The [older dev0 reports](../zingolib-v5-compose/README.md) are historical summaries with fewer fields and cannot pass this verifier.

## Continuous-traffic results

Each platform ran one calibration and one evaluation session. Each session contains three confirmed 50,000-zatoshi payments, a persistent wallet process, periodic sync, and background block production. A self-transfer before capture requested eight confirmed 60,000-zatoshi sender notes to remove dependence on preceding payments’ change. Each session has 18 fixed four-second windows. Only calibration labels select the threshold; evaluation labels are used solely for scoring.

Counts below refer to **windows, not payments**. A command may overlap multiple windows. A true positive is a flagged send-active window; a false positive is a flagged window without an active send command.

| Platform / split | Threshold (bytes) | TP | FP | FN | TN | Recall | False-positive rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| OrbStack / calibration | 141 | 4 | 1 | 2 | 11 | 66.7% | 8.3% |
| OrbStack / evaluation | 141 | 3 | 1 | 3 | 11 | 50.0% | 8.3% |
| Linux / calibration | 9,207 | 3 | 0 | 5 | 10 | 37.5% | 0.0% |
| Linux / evaluation | 9,207 | 3 | 0 | 5 | 10 | 37.5% | 0.0% |

All 12 OrbStack evaluation negative windows contained traffic; 8 of 10 Linux evaluation negative windows did. Evaluation balanced accuracy was 70.8% and 68.8%, respectively. An always-negative detector has 50% balanced accuracy with both classes present. The different cutoffs and window counts illustrate sensitivity to the local execution; they are not estimates of population performance. Each platform fits its own cutoff, so this is not cross-platform model transfer.

The feature is the largest client record with outer TLS content type 23 completed in each window. It does not identify the encrypted contents. Command intervals supply ground truth and may include time beyond network submission. Neighboring windows are correlated. These small, prescribed local sessions do not establish transaction linkage, user identification, or field privacy. A missed window does not mean that the payment was lost; all six privacy payments per platform confirmed and their recipient balance increases were checked.

Development trials exposed incomplete sync handling and intermittent scheduled-send failures before the final funding setup. The retained results use the final recipe, with no accuracy-based pass threshold and no adjustment of the detector based on these evaluation results.

## Recompute locally

Install the development checkout, then run from the repository root:

```sh
wpt verify-recovery evidence/zingolib-v5-continuous/orbstack-aarch64/report.json
wpt analyze-privacy evidence/zingolib-v5-continuous/orbstack-aarch64/privacy-manifest.json
wpt verify-recovery evidence/zingolib-v5-continuous/linux-x86_64/report.json
wpt analyze-privacy evidence/zingolib-v5-continuous/linux-x86_64/privacy-manifest.json
```

A clean installed development wheel verified both recovery reports and exactly reproduced both saved privacy reports. All 36 tests passed locally and in Python 3.11–3.13 CI on Linux and macOS, alongside dependency, source, and package audits. The CLI rejected a falsified recipient balance despite a claimed pass. Metadata-forwarding regression tests fail against PyPI 0.1.0 and pass against development.

Only metadata traces, sanitized observations, and checksums are retained here. Wallet state, TLS keys, raw wallet logs, signed transaction bytes, and build logs are excluded. These development commands are not part of PyPI 0.1.0.
