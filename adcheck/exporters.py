from __future__ import annotations

import json
from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

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


def to_docx(report: Report) -> bytes:
    """Render the same report data as an editable Word document."""
    document = Document()
    title = document.add_heading("广告宣传材料合规初筛报告", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_paragraph(f"检查结论：{report.verdict}")
    document.add_paragraph(f"检查时间：{report.checked_at}")
    document.add_paragraph("本结果仅用于广告发布前第一轮提示，不构成法律意见。")

    for index, finding in enumerate(report.findings, 1):
        item = finding.to_dict()
        document.add_heading(f"{index}. {item['对应规则']} {item['规则名称']}", level=1)
        fields = (
            ("风险内容原文", item["风险内容原文"]),
            ("风险类型", item["风险类型"]),
            ("对应规则", item["对应规则"]),
            ("风险等级", item["风险等级"]),
            ("修改建议", item["修改建议"]),
            ("是否需要人工审核", "是" if item["是否需要人工审核"] else "否"),
        )
        table = document.add_table(rows=0, cols=2)
        table.style = "Light Shading Accent 1"
        for label, value in fields:
            cells = table.add_row().cells
            cells[0].text = label
            cells[1].text = str(value)

    if not report.findings:
        document.add_paragraph("未发现题设 A-01～A-10 规则风险。")
    for style_name in ("Normal", "Body Text"):
        style = document.styles[style_name]
        style.font.name = "Arial"
        style.font.size = Pt(10.5)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
