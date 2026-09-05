# Zingolib integration

The retained case study used released Zingolib v5.0.0, lightwalletd, and Zebra 6.2.3 on an isolated NU6.2 regtest chain. The original research environment is intentionally excluded from this package because it contains downloaded source trees, compiled binaries, a TLS private key, and wallet state.

## Attach passive capture

Start the wallet's normal TLS-enabled lightwalletd endpoint. Place `wpt capture` on a new loopback port and configure `zingo-cli --server` to use that port. The wallet must trust the endpoint certificate through its supported test configuration. Do not disable certificate or hostname verification to make the test run.

Start and stop capture around a declared operation window. If the wallet keeps connections open, let the connection close or arrange an explicit capture boundary before requiring complete TLS-record accounting. Record whether synchronization was enabled and whether the channel was reused.

## Attach the semantic relay

Generate a localhost test certificate and configure Zingolib to trust its CA. Start `wpt fault-relay` with the real lightwalletd endpoint as upstream, then pass the relay endpoint to `zingo-cli --server`.

For each mode:

1. create one finalized payment from a funded disposable wallet;
2. run the send through the relay;
3. save the wallet's immediate structured result;
4. query the node's mempool independently;
5. verify every relay attempt has the same transaction hash;
6. mine the accepted transaction;
7. synchronize the wallet and save its final status.

Define the expected result before running the scenario. A timeout after upstream submission is an uncertain outcome, even if an older client labels it failed. The test should assess a declared wallet contract rather than embed one release's wording into this package.

## Upstream placement

Zingolib already has unit tests around resilient transmission and a real node/indexer integration workspace. Ask the maintainers whether they want this scenario in that workspace, Zingo Mobile's Regchest tests, or as an external job. The public testkit should retain the protocol instrument even if the wallet-state assertion moves upstream.
