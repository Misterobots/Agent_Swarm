import unittest
from utils.inference_metrics import design_token_metrics


class DesignTokenMetricsTests(unittest.TestCase):
    def test_uses_provider_tokens_and_nanoseconds_not_wall_clock(self):
        event = design_token_metrics({"eval_count": 120, "eval_duration": 2_000_000_000, "total_duration": 30_000_000_000}, "test-model")
        self.assertIn("60.0 tokens/s", event["content"])
        self.assertEqual(event["metrics"]["output_tokens"], 120)
        self.assertEqual(event["metrics"]["evaluation_seconds"], 2)

    def test_no_estimated_count_when_provider_does_not_supply_one(self):
        for count in (None, -1, "100", True):
            event = design_token_metrics({"eval_count": count, "eval_duration": 1e9}, "test")
            self.assertNotIn("output_tokens", event["metrics"])
            self.assertNotIn("tokens/s", event["content"])

    def test_zero_or_invalid_duration_never_fabricates_throughput(self):
        for duration in (None, 0, -1, float("nan"), float("inf"), True):
            event = design_token_metrics({"eval_count": 5, "eval_duration": duration}, "test")
            self.assertEqual(event["metrics"]["output_tokens"], 5)
            self.assertNotIn("output_tokens_per_second", event["metrics"])


if __name__ == "__main__":
    unittest.main()
