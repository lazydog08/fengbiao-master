import unittest
from math import nan

from fengbiao.analysis import analyze_sample


class SampleAnalysisTests(unittest.TestCase):
    def test_title_features_and_cover_shape_are_structured(self):
        analysis = analyze_sample(
            title="智能眼镜 VS 手机？我戴了7天后发现真相",
            cover_dimensions=(1280, 720),
            cover_changed=True,
            title_changed=False,
            relative_to_baseline=1.7,
            sample_size=5,
        )

        present = {item["id"] for item in analysis["title"]["features"] if item["present"]}
        self.assertEqual(analysis["version"], 1)
        self.assertEqual(analysis["source"], "rule")
        self.assertEqual(analysis["performance"]["bucket"], "high")
        self.assertEqual(analysis["performance"]["confidence"], "ok")
        self.assertTrue({"question", "number", "comparison", "first_person", "conflict", "specificity"} <= present)
        self.assertEqual(analysis["cover"]["orientation"], "landscape")
        self.assertEqual(analysis["cover"]["width"], 1280)
        self.assertEqual(analysis["cover"]["height"], 720)
        self.assertAlmostEqual(analysis["cover"]["aspect_ratio"], 1.778)
        self.assertTrue(analysis["cover"]["cover_changed"])
        self.assertFalse(analysis["cover"]["title_changed"])
        self.assertTrue(analysis["explanation"]["structure"])
        self.assertTrue(analysis["explanation"]["features"])
        self.assertTrue(analysis["explanation"]["interpretation"])
        self.assertTrue(analysis["caveats"])

    def test_bucket_boundaries_match_frontend_performance_buckets(self):
        self.assertEqual(
            analyze_sample("普通标题", None, False, False, 1.5, 3)["performance"]["bucket"],
            "high",
        )
        self.assertEqual(
            analyze_sample("普通标题", None, False, False, 0.6, 3)["performance"]["bucket"],
            "steady",
        )
        self.assertEqual(
            analyze_sample("普通标题", None, False, False, 0.59, 3)["performance"]["bucket"],
            "low",
        )
        unknown = analyze_sample("普通标题", None, False, False, None, 3)
        self.assertEqual(unknown["performance"]["bucket"], "unknown")
        self.assertEqual(unknown["performance"]["confidence"], "low")
        nan_bucket = analyze_sample("普通标题", None, False, False, nan, 3)
        self.assertEqual(nan_bucket["performance"]["bucket"], "unknown")
        self.assertEqual(nan_bucket["performance"]["confidence"], "low")

    def test_missing_cover_keeps_title_only_analysis(self):
        analysis = analyze_sample(
            title="今天整理一下桌面设备",
            cover_dimensions=None,
            cover_changed=False,
            title_changed=False,
            relative_to_baseline=0.9,
            sample_size=1,
        )

        present = {item["id"] for item in analysis["title"]["features"] if item["present"]}
        self.assertEqual(present, set())
        self.assertFalse(analysis["cover"]["has_asset"])
        self.assertIsNone(analysis["cover"]["width"])
        self.assertEqual(analysis["cover"]["orientation"], "unknown")
        self.assertEqual(analysis["performance"]["bucket"], "steady")
        self.assertEqual(analysis["performance"]["confidence"], "low")
        self.assertIn("标题", analysis["explanation"]["structure"])

    def test_analysis_is_stable_for_identical_inputs(self):
        analysis = analyze_sample(
            title="智能眼镜这次能当主力屏幕吗？",
            cover_dimensions=(1600, 900),
            cover_changed=False,
            title_changed=False,
            relative_to_baseline=1.0,
            sample_size=4,
        )

        self.assertNotIn("generated_at", analysis)
        self.assertEqual(
            analysis,
            analyze_sample(
                title="智能眼镜这次能当主力屏幕吗？",
                cover_dimensions=(1600, 900),
                cover_changed=False,
                title_changed=False,
                relative_to_baseline=1.0,
                sample_size=4,
            ),
        )

    def test_none_title_falls_back_to_empty_title_analysis(self):
        analysis = analyze_sample(
            title=None,
            cover_dimensions=None,
            cover_changed=False,
            title_changed=False,
            relative_to_baseline=None,
            sample_size=0,
        )

        self.assertEqual(analysis["title"]["char_len"], 0)
        self.assertEqual(analysis["performance"]["bucket"], "unknown")
        self.assertIn("标题", analysis["explanation"]["structure"])

    def test_generated_copy_avoids_absolute_claim_words(self):
        analysis = analyze_sample(
            title="智能眼镜这次能当主力屏幕吗？",
            cover_dimensions=(1600, 900),
            cover_changed=False,
            title_changed=True,
            relative_to_baseline=0.4,
            sample_size=4,
        )

        text = " ".join(analysis["explanation"].values())
        banned = ["国家级", "最佳", "顶级", "极品", "销量领先", "领导品牌", "独家", "唯一", "最", "第一", "首个"]
        for word in banned:
            self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()
