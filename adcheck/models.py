from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Finding:
    quote: str
    risk_type: str
    rule_id: str
    rule_name: str
    level: str
    suggestion: str
    manual_review: bool
    confidence: str
    reason: str
    status: str = "明确风险"
    source: str = "输入文本"

    def to_dict(self) -> dict[str, Any]:
        return {
            "风险内容原文": self.quote,
            "风险类型": self.risk_type,
            "对应规则": self.rule_id,
            "规则名称": self.rule_name,
            "风险等级": self.level,
            "修改建议": self.suggestion,
            "是否需要人工审核": self.manual_review,
            "置信度": self.confidence,
            "判定状态": self.status,
            "原因": self.reason,
            "来源": self.source,
        }


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    semantic_status: str = "未运行"
    semantic_message: str = ""
    ocr_text: str = ""
    ocr_confidence: float | None = None
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def verdict(self) -> str:
        if any(f.rule_id == "A-06" for f in self.findings):
            return "拦截并人工复核"
        if self.findings or self.semantic_status != "完成":
            return "需人工审核"
        return "未发现题设规则风险"

    def to_dict(self) -> dict[str, Any]:
        return {
            "结论": self.verdict,
            "检查时间": self.checked_at,
            "语义审查状态": self.semantic_status,
            "语义审查说明": self.semantic_message,
            "OCR平均置信度": self.ocr_confidence,
            "OCR文字": self.ocr_text,
            "风险项": [f.to_dict() for f in self.findings],
            "声明": "本结果仅用于广告发布前第一轮提示，不构成法律意见。",
        }

