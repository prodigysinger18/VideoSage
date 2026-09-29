import unittest

from evaluation.evaluate_events import evaluate_events
from evaluation.evaluate_identity import evaluate_identity


class EventEvaluationTests(unittest.TestCase):
    def test_one_to_one_matching_and_unmatched_events(self):
        truth = [{"person_id": 1, "event": "fall", "start_time": 2, "end_time": 4}]
        predicted = [
            {"person_id": 1, "event": "fall", "start_time": 2.1, "end_time": 4.1},
            {"person_id": 1, "event": "fall", "start_time": 2.2, "end_time": 4.2},
        ]
        report = evaluate_events(truth, predicted)
        self.assertEqual((report["tp"], report["fp"], report["fn"]), (1, 1, 0))
        self.assertAlmostEqual(report["precision"], 0.5)
        self.assertAlmostEqual(report["mean_onset_error_seconds"], 0.1)

    def test_person_identity_is_required_by_default(self):
        truth = [{"person_id": 1, "action": "walking", "start_time": 0, "end_time": 2}]
        predicted = [{"person_id": 2, "action": "walking", "start_time": 0, "end_time": 2}]
        self.assertEqual(evaluate_events(truth, predicted, "action")["tp"], 0)
        self.assertEqual(evaluate_events(truth, predicted, "action", match_person=False)["tp"], 1)

    def test_invalid_intervals_are_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_events([{"person_id": 1, "event": "fall", "start_time": 2, "end_time": 2}], [])


class IdentityEvaluationTests(unittest.TestCase):
    def test_counts_switch_on_same_annotated_person(self):
        truth = [
            {"frame_id": 1, "person_id": "a", "bbox": [0, 0, 10, 10]},
            {"frame_id": 2, "person_id": "a", "bbox": [1, 0, 11, 10]},
        ]
        predicted = [
            {"frame_id": 1, "person_id": 10, "bbox": [0, 0, 10, 10]},
            {"frame_id": 2, "person_id": 11, "bbox": [1, 0, 11, 10]},
        ]
        report = evaluate_identity(truth, predicted)
        self.assertEqual(report["matched_boxes"], 2)
        self.assertEqual(report["identity_switches"], 1)


if __name__ == "__main__":
    unittest.main()
