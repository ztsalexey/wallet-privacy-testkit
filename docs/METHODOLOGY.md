# Methodology

## Two separate instruments

The passive forwarder and the semantic fault relay answer different questions and must not be combined into one privacy claim.

The passive forwarder sits outside TLS. It records the information available to an on-path observer: connection boundaries, direction, time, TCP read length, TLS content type, and TLS record length. TCP reads are not packets and may split or combine TLS records. The parser therefore reassembles record headers before reporting record lengths. A complete trace requires the sum of TCP bytes to equal the sum of complete TLS records in each direction.

The semantic relay terminates a test TLS connection. It can identify a `SendTransaction` call, hash the signed transaction bytes, submit the exact request upstream, and discard a response after submission. This instrument has more information than an external observer. Its purpose is transaction-delivery testing, not passive privacy measurement.

Version 0.1.0's RPC cardinality table targets canonical `lightwallet-protocol` v0.5.0. Compatibility must be rechecked when that protocol adds or changes methods.

## Size matching

The supplied matcher uses one numeric observation per wallet operation and a public transaction size for every candidate in the same batch. A separate training batch determines a median byte offset:

```text
offset = median(observed bytes - public transaction bytes)
```

For each held-out observation, the matcher ranks candidates from that observation's batch by absolute distance after applying the offset. Candidates at the same minimum distance divide one point equally. A correct three-way tie therefore earns one third, not one full success.

The random reference is the mean inverse candidate-set size across held-out observations. Batches with fewer than two candidates are rejected. Unknown candidates, continuous traffic segmentation, and timing models require separate experimental designs.

## Required report fields

A privacy report should identify:

- the wallet and indexer versions or source revisions;
- the network and consensus upgrade configuration;
- the observer's location and available information;
- how operation windows were delimited;
- whether synchronization or other traffic ran concurrently;
- how candidates became eligible and whether any were excluded;
- the training, calibration, and held-out split;
- ties, failed operations, incomplete records, and oversized messages;
- sample counts and the random reference;
- the intervention and its byte, time, and reliability costs.

An aggregate percentage without these fields is not a reusable privacy result.

## Delivery fault assertions

For each fault, record the wallet's immediate result, each attempt's transaction hash, the upstream response, the node's mempool or chain state, and the wallet's state after synchronization. The test passes only against a declared product requirement. Examples include:

- a pre-submission failure may be reported as failed if no attempt reached the node;
- a timeout after submission must be represented as an unknown or pending outcome unless delivery is independently disproved;
- retries must reuse the same finalized transaction unless the wallet explicitly performs a replacement protocol;
- eventual chain observation must reconcile the wallet's transaction state.

The testkit does not prescribe user-facing terminology. The wallet team defines its intended states before the run.

## Reproducibility levels

1. Unit: the parser, relay boundary, and matcher pass with synthetic local services.
2. Local integration: a real wallet, indexer, and consensus-valid regtest node complete the scenario.
3. Release regression: the same scenario runs from a wallet repository's pinned CI environment.
4. Field study: real transports and realistic background traffic are measured under an approved research protocol.

Version 0.1.0 provides level 1 in its test suite and one retained level-2 Zingolib case study. It has not reached levels 3 or 4.
