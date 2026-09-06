"""Versioned study design, reproducible from a public seed without wallet secrets."""
import hashlib
import re

WINDOW_NS = 4_000_000_000
DURATION_NS = 96_000_000_000
CONDITIONS = {"baseline": {}, "latency": {"delay_ms": 25, "jitter_ms": 10},
              "bandwidth": {"delay_ms": 5, "bytes_per_second": 65536}}
DEVTOOL_REVISION = "5a26ee854e634a4e88d1d79dab13f8fbb1eac6b8"


def make_plan(seed):
    """Hash-derived scheduling is stable across Python versions; never seeds keys."""
    if not isinstance(seed, str) or not re.fullmatch(r"[0-9a-f]{64}", seed):
        raise ValueError("study seed must be 64 lowercase hexadecimal characters")

    def draw(label):
        return int.from_bytes(hashlib.sha256(f"wpt-study-2:{seed}:{label}".encode()).digest(), "big")

    def session(split, wallet, condition, repeat):
        name = f"{split}-{wallet}-{condition}-{repeat}"
        return {"id": name, "split": split, "wallet": wallet, "condition": condition,
                "repeat": repeat, "sender_state_id": name,
                "payment_offsets_ns": [base * 1_000_000_000 + draw(f"{name}:send:{i}") % 12_000_000_000
                                       for i, base in enumerate((12, 40, 68))],
                "sync_offset_ns": draw(f"{name}:sync") % 6_000_000_000,
                "conditioner_seed": draw(f"{name}:network") % (2 ** 64)}

    sessions = [session("calibration", "zingolib", "baseline", r) for r in range(1, 4)]
    for repeat in range(1, 4):
        block = [session("evaluation", w, c, repeat)
                 for w in ("zingolib", "zcash-devtool") for c in CONDITIONS]
        sessions.extend(sorted(block, key=lambda s: draw(f"order:{s['id']}")))
    return {"schema_version": 2, "seed": seed, "sessions": sessions,
            "window_ns": WINDOW_NS, "duration_ns": DURATION_NS,
            "conditions": {name: dict(options) for name, options in CONDITIONS.items()}, "payment_amount": 50_000,
            "funding_outputs": 8, "funding_amount_per_output": 60_000,
            "sender_state": "new directory and OS-generated wallet keys for every session",
            "shared_state": "node, indexer, funder, recipient; chain grows across sessions",
            "detector": "largest client TLS record; calibration balanced accuracy; higher cutoff breaks ties",
            "conditioner": "independent TCP directions; delay/jitter and pacing per read of at most 16384 bytes; not packet-level emulation",
            "client_lifecycle": {"zingolib": "persistent interactive process", "zcash-devtool": "process per command; continuous capture"},
            "devtool_revision": DEVTOOL_REVISION}
