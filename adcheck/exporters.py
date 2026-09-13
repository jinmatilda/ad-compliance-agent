from __future__ import annotations

import json

from .models import Report


def to_json(report: Report) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)


def to_markdown(report: Report) -> str:
    data = report.to_dict()
    lines = ["# 广告宣传材料合规初筛报告", "", f"**结论：{data['结论']}**", "", data["声明"], "",
             f"语义审查：{data['语义审查状态']} — {data['语义审查说明']}", ""]
    if not report.findings:
        lines.append("未发现题设 A-01～A-10 规则风险。")
    for i, finding in enumerate(report.findings, 1):
        item = finding.to_dict()
        lines.extend([f"## {i}. {item['对应规则']} {item['规则名称']}", "",
                      f"- 风险内容原文：{item['风险内容原文']}", f"- 风险类型：{item['风险类型']}",
                      f"- 风险等级：{item['风险等级']}", f"- 判定状态：{item['判定状态']}",
                      f"- 置信度：{item['置信度']}", f"- 原因：{item['原因']}",
                      f"- 修改建议：{item['修改建议']}", f"- 是否需要人工审核：{'是' if item['是否需要人工审核'] else '否'}", ""])
    return "\n".join(lines)
