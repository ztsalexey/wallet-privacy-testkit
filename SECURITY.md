# Security policy

## Supported version

Version 0.1.x receives security fixes while it remains the current release line.

## Reporting a vulnerability

Do not include wallet seeds, private keys, signed mainnet transactions, or identifying traffic captures in a public report. Prepare a minimal reproduction with synthetic or regtest data and use [GitHub private vulnerability reporting](https://github.com/ztsalexey/wallet-privacy-testkit/security/advisories/new). The repository owner must enable private vulnerability reporting before publication.

## Operational boundary

The fault relay is intended for isolated test environments. It terminates TLS and receives a serialized transaction in memory so it can hash the signed bytes and identify retries. It does not persist those bytes. A compromised host can still inspect process memory, files, or wallet traffic, so the test machine is part of the trust boundary.

The passive capture forwarder does not terminate TLS and logs metadata only. It is not an anonymity system and does not protect the traffic it observes.
