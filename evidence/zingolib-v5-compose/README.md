# Fresh-state Compose recovery evidence

The [OrbStack ARM64 report](orbstack-aarch64.json) was produced on September 5, 2026 by the [Compose lab](../../examples/regtest/README.md), using new wallet seeds, a new TLS certificate, and an empty chain volume. The tested lab and runtime source correspond to commit `0e9f59f615fe4d53d7e8e03f3a4c9ef7c34cbf8f`. This is an executed Linux container experiment on OrbStack, not a replay of the older retained Mac wallet state.

The same source passed on native Linux Docker in [GitHub Actions run 33991854350](https://github.com/ztsalexey/wallet-privacy-testkit/actions/runs/33991854350), producing the [Linux x86-64 report](linux-x86_64.json). Both executions observed the same recovery states and balance deltas below, with independently generated wallets and transaction IDs. Docker Desktop has not been separately tested.

| Scenario | Observed attempts | State after reopening, before mining | State after synchronization | Recipient increase |
| --- | ---: | --- | --- | ---: |
| First acknowledgement lost | 4, identical signed bytes | failed | confirmed, 3 confirmations | 100,000 zatoshis |
| Wallet killed while acknowledgement held | 1, then process exit -9 | calculated | confirmed, 3 confirmations | 100,000 zatoshis |

For each scenario the live runner checked that only the accepted transaction was in the node mempool, its serialized-byte hash matched the relay, the reopened sender reported confirmation, the recipient balance increased by exactly the intended amount, and the final mempool was empty. The generated wallet state and TLS keys were removed after the run; the report contains only sanitized observations and binary hashes.

These results establish recovery after the tested process interruption and subsequent chain synchronization. They do not establish automatic resubmission of a payment intent, power-loss durability, general exactly-once payment semantics, or current-development behavior. The report summarizes assertions performed against the live node and wallets; it is not a complete raw transcript from which every assertion can be independently recomputed offline. Re-run the lab to verify the observations independently.

Transport validation is separate: 24 tests cover the testkit itself. The new deadline and cancelled-stream tests both fail against installed 0.1.0 and pass against the development source, demonstrating the regression they detect.
