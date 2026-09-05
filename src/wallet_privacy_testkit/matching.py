"""Conservative size-only matching with fractional credit for ties."""

import statistics

REQUIRED_FIELDS = frozenset(("id", "batch", "observed_bytes", "transaction_bytes"))


def evaluate_size_matching(samples, training_batch=0):
    if not isinstance(samples, list) or not samples:
        raise ValueError("samples must be a non-empty JSON array")
    identifiers = set()
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise ValueError(f"sample {index} is not an object")
        missing = REQUIRED_FIELDS.difference(sample)
        if missing:
            raise ValueError(f"sample {index} is missing: {', '.join(sorted(missing))}")
        if not isinstance(sample["id"], str) or not sample["id"]:
            raise ValueError(f"sample {index} has an invalid id")
        if sample["id"] in identifiers:
            raise ValueError(f"duplicate sample id: {sample['id']}")
        identifiers.add(sample["id"])
        if type(sample["batch"]) is not int or sample["batch"] < 0:
            raise ValueError(f"sample {index} has an invalid batch")
        if not all(
            type(sample[field]) is int and sample[field] >= 0
            for field in ("observed_bytes", "transaction_bytes")
        ):
            raise ValueError(f"sample {index} has invalid byte counts")
    training = [sample for sample in samples if sample["batch"] == training_batch]
    if not training:
        raise ValueError("training batch is absent")
    held_out = [sample for sample in samples if sample["batch"] != training_batch]
    if not held_out:
        raise ValueError("held-out samples are absent")
    offset = statistics.median(
        sample["observed_bytes"] - sample["transaction_bytes"]
        for sample in training
    )
    scores = []
    for sample in held_out:
        candidates = [row for row in samples if row["batch"] == sample["batch"]]
        if len(candidates) < 2:
            raise ValueError(f"batch {sample['batch']} has fewer than two candidates")
        distances = [
            abs(sample["observed_bytes"] - (candidate["transaction_bytes"] + offset))
            for candidate in candidates
        ]
        best = min(distances)
        tied = [
            candidate
            for candidate, distance in zip(candidates, distances)
            if distance == best
        ]
        credit = 1 / len(tied) if sample["id"] in {row["id"] for row in tied} else 0
        scores.append(
            {
                "id": sample["id"],
                "batch": sample["batch"],
                "credit": credit,
                "tied_candidates": len(tied),
                "absolute_size_error": abs(
                    sample["observed_bytes"]
                    - sample["transaction_bytes"]
                    - offset
                ),
            }
        )
    batch_sizes = {
        sample["batch"]: sum(row["batch"] == sample["batch"] for row in samples)
        for sample in held_out
    }
    random_reference = statistics.mean(
        1 / batch_sizes[sample["batch"]] for sample in held_out
    )
    return {
        "training_batch": training_batch,
        "training_samples": len(training),
        "held_out_samples": len(held_out),
        "learned_offset_bytes": offset,
        "fractional_top1": statistics.mean(score["credit"] for score in scores),
        "random_reference": random_reference,
        "scores": scores,
    }
