from datetime import datetime, timezone
import unittest

from fengbiao.metrics import compute_relative_metrics, compute_early_growth_per_hour


class MetricsTests(unittest.TestCase):
    def test_compute_relative_metrics_uses_creator_median_not_absolute_views(self):
        metrics = compute_relative_metrics(play_count=300, creator_recent_play_counts=[100, 200, 400, 800], follower_count=1000)

        self.assertEqual(metrics["baseline_play_count"], 300.0)
        self.assertEqual(metrics["relative_to_baseline"], 1.0)
        self.assertEqual(metrics["views_per_follower"], 0.3)


    def test_compute_relative_metrics_returns_none_when_data_is_insufficient(self):
        metrics = compute_relative_metrics(play_count=None, creator_recent_play_counts=[], follower_count=0)

        self.assertIsNone(metrics["baseline_play_count"])
        self.assertIsNone(metrics["relative_to_baseline"])
        self.assertIsNone(metrics["views_per_follower"])


    def test_compute_early_growth_per_hour_uses_time_window(self):
        first = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
        second = datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc)

        growth = compute_early_growth_per_hour([(first, 100), (second, 250)])

        self.assertEqual(growth, 6.25)
