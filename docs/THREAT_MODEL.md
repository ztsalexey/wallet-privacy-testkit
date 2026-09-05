# Threat model

## Passive capture

The observer can see a wallet's TCP/TLS connection to an indexer but cannot decrypt it. The observer may know public blockchain transaction sizes and times. The basic matcher is also given operation boundaries and a candidate batch by the test operator.

The measured signal can show that encrypted record lengths vary with public transaction structure. It cannot by itself show that an observer can find wallet operations in continuous traffic, identify a user, defeat Tor or Nym, link separate network identities, or infer hidden amounts and addresses.

Traffic segmentation is a major assumption. Starting a fresh wallet process around each payment gives the observer unusually clear boundaries. Reports must say when this is done. Background sync, connection reuse, HTTP/2 multiplexing, retransmission, transport padding, mixnet framing, and Internet path behavior can change the observations.

## Semantic fault relay

The relay is a trusted test component between a disposable wallet and a regtest indexer. It terminates TLS, receives serialized transaction bytes in memory, and records their hash and length. The host operating the relay can inspect process memory and is inside this test's trust boundary.

The relay models three delivery boundaries. It does not estimate their frequency in production, reproduce every HTTP/2 or mobile-network failure, prove exactly-once payment semantics, or determine what a user will do after seeing an error.

## Excluded adversaries

Version 0.1.0 does not model:

- malware or a compromised wallet device;
- a malicious proving implementation;
- consensus or cryptographic failures;
- global timing correlation across Tor or Nym;
- active tagging by an indexer;
- DNS, certificate, or software-supply-chain compromise;
- cross-chain flow correlation;
- transparent-address query privacy;
- denial of service or resource exhaustion.

These can become separate test scenarios only with explicit observables and pass criteria.

## Safe test boundary

Use disposable wallet state and valueless regtest funds. Bind relays to loopback unless a test plan names and protects another interface. Keep private keys and certificates out of result directories. Never treat the semantic relay as a production proxy.

