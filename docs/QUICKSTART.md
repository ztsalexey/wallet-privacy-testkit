# Verify a wallet experiment

Start with the real observations bundled in version 0.3.0 to see what the testkit checks, then collect a fresh run when you need to test a wallet or change.

## First result without Docker

With Python 3.11 or newer:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install wallet-privacy-testkit==0.3.0
wpt --version
wpt verify-run --example
```

Installation requires Internet access. Verification reads the packaged local files and needs no wallet, node, Docker engine, or live funds. After installation, `wpt verify-run --example` works from any directory; the wheel includes the compact example. The larger studies and lab remain in the repository and source archive.

The command independently recomputes the evidence instead of trusting a saved success field or computed report. It checks two things:

| Check | What success establishes |
| --- | --- |
| Recovery | All five recorded scenarios satisfy the payment, transaction-identity, and intervention assertions; the deliberately unmined payment is detected as unconfirmed and unpaid. |
| Privacy experiment | The retained traces and observations are consistent, and the send-window detector is recomputed using calibration data before evaluation. |

`--example` verifies an earlier two-session OrbStack run. It is labeled as retained evidence: no new wallet activity takes place. Poor detection is a valid experimental outcome. Verification establishes consistency of supplied observations, not their authenticity, real-world accuracy, or a wallet's privacy.

## Verify the larger randomized study

Keep the virtual environment active and fetch the matching source release with Git:

```sh
git clone --branch v0.3.0 --depth 1 https://github.com/ztsalexey/wallet-privacy-testkit.git
cd wallet-privacy-testkit
wpt verify-run evidence/randomized-study
```

You can also extract the source archive from [GitHub Releases](https://github.com/ztsalexey/wallet-privacy-testkit/releases/tag/v0.3.0). Run the remaining examples from its top-level directory.

This study contains 21 sessions and 63 confirmed payments. Its frozen detector missed every send-active window from the independent development wallet, even though the evidence passes verification. Read the [retained results](../evidence/randomized-study/README.md) for per-condition measurements, the distinction between windows and payments, and sampling limitations. The [methodology](PRIVACY_STUDY.md) explains the fresh senders, randomized schedule, and frozen model.

## Save a report or use CI

The default output is a concise text summary. Export structured JSON for analysis or JUnit XML for an existing CI test-results viewer:

```sh
wpt verify-run evidence/randomized-study --format json --output verification.json
wpt verify-run evidence/randomized-study --format junit --output verification.xml
```

Output files must be new; the command refuses to overwrite an existing report. Omit `--output` to write the selected format to standard output.

| Exit status | Meaning |
| --- | --- |
| `0` | Required observations and recovery assertions are consistent. Detector accuracy is not a pass threshold. |
| `1` | Required evidence is missing, inconsistent, or fails a recovery assertion. |
| `2` | Invalid command usage or an output-file error. |

JUnit records evidence verification checks for your CI viewer. A passing check never certifies wallet privacy. The recorded negative control must fail its underlying recovery assertions in the expected way for verification to succeed.

## Inspect the full results

The specialized commands retain their JSON output for analysis:

```sh
wpt verify-recovery evidence/randomized-study/report.json
wpt analyze-study evidence/randomized-study/study-manifest.json > study-analysis.json
```

The smaller native Linux run uses the two-session privacy format. The same combined command detects it:

```sh
wpt verify-run evidence/randomized-study/linux-regression
```

The Linux run fits its own detector; it is a separate regression, not a cross-platform evaluation of the randomized study's frozen model.

## Collect a fresh run

From the same source checkout, with Docker Engine and Compose v2 available:

```sh
python examples/regtest/run.py --output /tmp/wpt-first-run
wpt verify-run /tmp/wpt-first-run
```

On macOS with OrbStack, select its Docker context explicitly:

```sh
python examples/regtest/run.py --context orbstack --output /tmp/wpt-orbstack-run
wpt verify-run /tmp/wpt-orbstack-run
```

Use a new output directory for every invocation. The first build downloads and compiles the pinned wallet and indexer sources; allow at least 8 GB available memory, several GB of disk, and substantially more time than offline verification. The runner creates and cleans up its own isolated Docker project. The [lab instructions](../examples/regtest/README.md) explain resource requirements, retained files, failure diagnosis, and targeted cleanup.

The runner prints the same readable verification summary and automatically saves `verification.json` and `verification.xml` beside the observations. The repository's regtest workflow retains both files with its run artifacts, so a CI consumer can display JUnit results without parsing console text.

Add `--study` for the full 21-session randomized study. It schedules 63 payments across two wallet implementations and three transport conditions. Recovery checks and the study take roughly an hour after compilation, depending on hardware:

```sh
python examples/regtest/run.py --context orbstack --study --output /tmp/wpt-study
wpt verify-run /tmp/wpt-study
```

## Use your wallet team's environment

The disposable lab demonstrates a complete integration with pinned wallet releases. To attach the reusable tools to an existing wallet test suite, use [passive capture or the transaction-delivery relay](../README.md#transaction-delivery-faults) and the [Zingolib integration guide](../examples/zingolib/README.md). Your harness supplies wallet state, node observations, and recipient balances; the relay alone cannot establish recovery.

Preserve the original observations and metadata traces with a CI run. Treat detector scores as descriptive results unless your team has separately declared and validated an appropriate performance requirement.
