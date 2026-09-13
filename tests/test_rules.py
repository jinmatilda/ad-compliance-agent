import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from adcheck.engine import analyze
from adcheck.exporters import to_json, to_markdown
from adcheck.rules import load_rules
from adcheck.ocr import extract_image


class RuleTests(unittest.TestCase):
    def rules(self, text):
        return {x.rule_id for x in analyze(text).findings}

    def test_rule_catalog(self):
        self.assertEqual(set(load_rules()), {f"A-{i:02d}" for i in range(1, 11)})

    def test_a01(self): self.assertIn("A-01", self.rules("全网最低价，第一名"))
    def test_a02(self): self.assertIn("A-02", self.rules("满意度提升90%"))
    def test_a02_complete_context(self):
        text = "截至2026年，来源：用户调查；统计口径：1000份有效样本，满意度90%"
        self.assertNotIn("A-02", self.rules(text))
    def test_a03(self): self.assertIn("A-03", self.rules("满100减50"))
    def test_a04(self): self.assertIn("A-04", self.rules("满100减50，活动1月1日至1月2日"))
    def test_a05(self): self.assertIn("A-05", self.rules("保证7天美白见效"))
    def test_a06(self):
        report = analyze("治疗失眠，无副作用")
        self.assertIn("A-06", {x.rule_id for x in report.findings})
        self.assertEqual(report.verdict, "拦截并人工复核")
    def test_a07(self): self.assertIn("A-07", self.rules("效果碾压所有竞品"))
    def test_a08(self): self.assertIn("A-08", self.rules("0元领，仅需运费9.9"))
    def test_a09(self):
        result = [x for x in analyze("权威专家推荐").findings if x.rule_id == "A-09"]
        self.assertTrue(result and result[0].manual_review)
    def test_a10(self):
        report = analyze("普通文案", a10_reasons=["图片模糊"])
        self.assertIn("A-10", {x.rule_id for x in report.findings})
        self.assertNotEqual(report.verdict, "未发现题设规则风险")
    def test_no_key_degrades_semantic(self):
        report = analyze("普通文案")
        self.assertEqual(report.semantic_status, "降级")
        self.assertTrue({"A-05", "A-07", "A-09"} <= {x.rule_id for x in report.findings})
    def test_output_fields_and_exports(self):
        report = analyze("全网最低")
        required = {"风险内容原文", "风险类型", "对应规则", "风险等级", "修改建议", "是否需要人工审核"}
        self.assertTrue(required <= report.findings[0].to_dict().keys())
        self.assertIn('"风险项"', to_json(report))
        self.assertIn("广告宣传材料合规初筛报告", to_markdown(report))

    def test_blurry_image_quality_signal_without_real_tesseract(self):
        buf = BytesIO()
        Image.new("RGB", (300, 200), "white").save(buf, "PNG")
        fake = {"text": ["测试"], "conf": ["45"]}
        with patch("adcheck.ocr.pytesseract.image_to_data", return_value=fake):
            result = extract_image(buf.getvalue())
        self.assertTrue(result.blurry)
        self.assertTrue(any("置信度" in reason for reason in result.reasons))


if __name__ == "__main__":
    unittest.main()
