# Next step: preserve the broadcast route during recovery

September 7, 2026. This is a proposed engineering and adoption experiment. It has not been implemented, run, requested by an external team, or accepted upstream.

The next product increment should answer one concrete question: **when a payment's outcome is unknown, does the wallet recover without changing either the signed transaction or its chosen broadcast endpoints?** A retry through the wallet's synchronization server can violate a deliberate endpoint separation even when the payment eventually confirms.

## Why this check

The [Swift SDK's documented Broadcaster contract](https://github.com/zcash/zcash-swift-wallet-sdk/blob/main/MIGRATING.md#broadcaster-redesign-multi-server-submission) persists the selected endpoints before attempting submission. A timeout or cancellation leaves an unknown outcome, and later retries retain that plan. If the plan store cannot be read, affected transactions are skipped rather than sent through the synchronization endpoint. These are documented protections to preserve; we have not demonstrated a defect in them.

The broader direction also fits [ZIP 318](https://zips.z.cash/zip-0318), which remains Draft: migration broadcasts use the selected private network, sync and migration broadcast occupy separate background sessions, and transient failures preserve stored transactions. Testing those additional requirements would need a separately scoped migration adapter and a pinned specification revision.

The [randomized study](../evidence/randomized-study/README.md) demonstrates why a better size cutoff alone is an insufficient product direction. A frozen detector failed to transfer between the two tested implementations. That result describes the detector under the measured conditions; it does not rank wallet privacy. Delivery and route-policy assertions offer a more directly actionable release check while privacy research continues.

## Smallest useful experiment

Use one pinned Swift SDK revision in a minimal disposable regtest client, one node/indexer deployment, and three monitored local endpoints:

| Endpoint | Role | Allowed behavior |
| --- | --- | --- |
| A | First selected broadcast endpoint, behind the fault relay | May receive `SendTransaction` and lose its acknowledgement |
| B | Second selected broadcast endpoint | May receive retries using the original signed transaction |
| C | Wallet synchronization endpoint | May receive sync RPCs; must receive no `SendTransaction` for this test payment |

The endpoints may share the same isolated indexer for this experiment. They represent distinct destinations for observing routing policy, not independent operators or an anonymity network. Capture all allowed egress paths so a bypass cannot escape observation. Record RPC method counts at C: blocking synchronization altogether would hide the behavior being tested.

Run this sequence with fresh disposable wallet state for each scenario:

1. Construct a payment and submit it through A with A/B as the persisted retry plan.
2. Forward the submission, independently observe node acceptance, and suppress the acknowledgement. A relay event alone is insufficient evidence of acceptance.
3. Terminate the client after the loss is established, then restart it with the same wallet state and normal retry/reconciliation behavior.
4. Restore endpoint availability, mine, and synchronize the recipient and sender.
5. Recompute assertions from retained observations: any retry preserves the signed-transaction hash and uses only A/B; C received no submission for the payment; the wallet and node agree on confirmation; the recipient received the exact expected amount once.

Do not require a retry when the wallet can reconcile the already-mined transaction without resubmitting. The invariant governs retries that occur. Distinguish an acknowledgement, node acceptance, and confirmation in the report.

Start with two failure scenarios: a lost response followed by process restart, and a held response that reaches the client's deadline. Add three controls:

- A normal acknowledged payment establishes that the client and instrumentation work.
- A deliberately unmined payment must fail the confirmation assertions.
- A deliberately misrouted test client sends the submission to C and must fail the route assertion.

The misrouted control is an intentional defect in the disposable test client, not an allegation about the SDK. Do not extend the first experiment to plan-store corruption, migration scheduling, Tor/Nym infrastructure, or mobile background execution. Those require separate fixtures and agreed expectations.

## Deliverable and decision

Produce one repeatable command, exact source pins, a short human report, machine-readable observations, and a JUnit result suitable for an existing wallet CI job. Retain metadata and transaction hashes, not signed transaction bytes, addresses, seeds, or wallet databases. The adapter must use the SDK's ordinary submission and recovery path; replacing its retry logic would test the adapter instead of the wallet.

| Decision | Evidence required |
| --- | --- |
| Technical success | Another engineer can reproduce the normal and fault scenarios, and both deliberately failing controls are detected. Report generation succeeds independently of whether the wallet passes. |
| Adoption success | A wallet team chooses a check it needs, reviews the intended behavior, and retains the regression in its release workflow. A request to reuse it on another release is a stronger signal. |
| Commercial evidence | A team explicitly commits resources or payment to a defined deliverable. A grant elsewhere, a repository star, or a polite response is insufficient. No such commitment is established here. |
| Stop or narrow | The target already covers the same behavior, the harness changes the behavior it claims to test, or integration work outweighs the accepted check. Retain a reproduction or upstream fixture rather than building a platform. |

Build on existing infrastructure where it fits. [Z3](https://github.com/ZcashFoundation/z3#building-and-testing-against-z3) publishes attachment contracts, and [Zcash Integration Tests](https://github.com/zcash/integration-tests) already supplies functional test and cross-repository CI infrastructure. Integration with either is a candidate, not a currently verified feature. Follow each target's contribution policy before proposing an upstream change.

The [competitive review](COMPETITIVE_LANDSCAPE.md) records the substantial overlap with existing tools. The next decision depends on a useful, reproducible check and voluntary adoption. No outreach, external issue, or maintainer commitment is implied by this plan.

## What a passing result would mean

A pass establishes recovery and endpoint-policy behavior for the tested version and scenarios. It does not prove Tor/Nym routing, absence of traffic correlation, protection from colluding servers, correct mobile scheduling, or general wallet privacy. Neither testkit success nor a local report authenticates observations supplied by an untrusted party.
