import json
import unittest
from unittest.mock import mock_open, patch

from evaluation.aggregate_reports import aggregate_reports


class AggregateReportsTests(unittest.TestCase):
    def test_micro_average_aggregates_counts(self):
        reports = [
            {"tp": 2, "fp": 1, "fn": 2, "mean_onset_error_seconds": 0.1},
            {"tp": 1, "fp": 0, "fn": 1, "mean_onset_error_seconds": 0.3},
        ]
        handles = [mock_open(read_data=json.dumps(report)).return_value for report in reports]
        with patch("builtins.open", side_effect=handles):
            result = aggregate_reports(["one.json", "two.json"])
        self.assertEqual(result["tp"], 3)
        self.assertEqual(result["fp"], 1)
        self.assertEqual(result["fn"], 3)
        self.assertEqual(result["precision"], 0.75)
        self.assertEqual(result["recall"], 0.5)
        self.assertEqual(result["f1"], 0.6)
        self.assertEqual(result["weighted_mean_onset_error_seconds"], 0.1667)


if __name__ == "__main__":
    unittest.main()
