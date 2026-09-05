import unittest

from wallet_privacy_testkit.matching import evaluate_size_matching


class MatchingTests(unittest.TestCase):
    @staticmethod
    def sample(identifier, batch, observed, transaction):
        return {
            "id": identifier,
            "batch": batch,
            "observed_bytes": observed,
            "transaction_bytes": transaction,
        }

    def test_distinct_sizes_match_and_equal_sizes_tie(self):
        rows = [
            self.sample("train-a", 0, 141, 100),
            self.sample("train-b", 0, 241, 200),
            self.sample("distinct-a", 1, 141, 100),
            self.sample("distinct-b", 1, 241, 200),
            self.sample("equal-a", 2, 141, 100),
            self.sample("equal-b", 2, 141, 100),
        ]
        report = evaluate_size_matching(rows)
        self.assertEqual(report["learned_offset_bytes"], 41)
        self.assertEqual(report["fractional_top1"], 0.75)
        self.assertEqual(report["random_reference"], 0.5)
        self.assertEqual(
            [score["credit"] for score in report["scores"]], [1, 1, 0.5, 0.5]
        )

    def test_invalid_input_does_not_produce_a_score(self):
        with self.assertRaisesRegex(ValueError, "duplicate sample"):
            evaluate_size_matching(
                [
                    self.sample("same", 0, 100, 90),
                    self.sample("same", 1, 100, 90),
                ]
            )
        with self.assertRaisesRegex(ValueError, "held-out"):
            evaluate_size_matching([self.sample("only", 0, 100, 90)])

    def test_types_cannot_smuggle_ambiguous_samples(self):
        valid = [
            self.sample("train", 0, 10, 8),
            self.sample("a", 1, 10, 8),
            self.sample("b", 1, 10, 8),
        ]
        for field, value in (("id", ""), ("batch", "1"), ("observed_bytes", True)):
            samples = [dict(row) for row in valid]
            samples[1][field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "invalid"):
                    evaluate_size_matching(samples)


if __name__ == "__main__":
    unittest.main()
