from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st

from adcheck.engine import analyze
from adcheck.exporters import to_docx, to_json, to_markdown
from adcheck.ocr import extract_image
from adcheck.rules import load_rules

st.set_page_config(page_title="广告宣传材料合规检查助手", page_icon="🛡️", layout="wide")

st.markdown(
    """
<style>
:root { --brand: #0f8b8d; --navy: #16324f; --line: #d8e3e8; }
[data-testid="stAppViewContainer"] { background: linear-gradient(180deg, #eef8f8 0, #f7fafb 300px); }
[data-testid="stHeader"] { background: transparent; }
.hero {
  padding: 1.7rem 2rem; border-radius: 22px; color: white; margin: .2rem 0 1.2rem;
  background: linear-gradient(120deg, #16324f 0%, #0f8b8d 68%, #3fc1c9 100%);
  box-shadow: 0 14px 35px rgba(22,50,79,.18);
}
.hero h1 { color: white; margin: 0 0 .45rem; font-size: 2.15rem; }
.hero p { margin: 0; color: #e8ffff; font-size: 1rem; }
.section-card {
  background: rgba(255,255,255,.94); border: 1px solid var(--line); border-radius: 16px;
  padding: 1rem 1.15rem .45rem; margin: .65rem 0 1rem; box-shadow: 0 6px 18px rgba(22,50,79,.06);
}
.section-title { color: var(--navy); font-weight: 750; font-size: 1.15rem; margin-bottom: .15rem; }
.section-subtitle { color: #617889; font-size: .86rem; margin-bottom: .55rem; }
.metric-card { background: white; border: 1px solid var(--line); border-radius: 14px; padding: .75rem 1rem; }
.risk-pill { display: inline-block; padding: .15rem .55rem; border-radius: 999px; font-weight: 700; font-size: .78rem; }
.risk-high { color:#a80f21; background:#fde8eb; } .risk-mid-high { color:#a64b00; background:#fff0df; }
.risk-mid { color:#806300; background:#fff7cc; } .risk-low { color:#59636e; background:#edf0f2; }
[data-testid="stSidebar"] { background: #edf5f6; border-right: 1px solid #d7e5e8; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 { font-size: 1.08rem !important; }
[data-testid="stSidebar"] .stExpander { font-size: .80rem; }
[data-testid="stSidebar"] .stMarkdown p { font-size: .78rem; line-height: 1.45; }
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }
[data-testid="stDataFrame"] [role="columnheader"] { background: #dceff1 !important; font-weight: 700 !important; }
hr { border-color: #d8e3e8; }
</style>
<div class="hero">
  <h1>🛡️ 广告宣传材料合规检查助手</h1>
  <p>上传文案、海报或活动页截图，依据 A-01～A-10 完成发布前第一轮风险筛查。</p>
</div>
""",
    unsafe_allow_html=True,
)

def config_value(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, os.getenv(name, default)))
    except FileNotFoundError:
        return os.getenv(name, default)


api_key = config_value("ARK_API_KEY")
base_url = config_value("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
model = config_value("ARK_MODEL", "doubao-seed-2-0-lite-260215")

if "report" not in st.session_state:
    st.session_state.report = None
if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.markdown("## 🕘 本次会话历史")
    st.caption("最多保留最近 10 条；云容器重启后会清空。")
    if st.session_state.history:
        for index, entry in enumerate(st.session_state.history):
            icon = {"高": "🔴", "中高": "🟠", "中": "🟡", "低": "⚪", "无": "🟢"}.get(entry["highest"], "⚪")
            label = f"{icon} {entry['time']}｜{entry['count']} 项"
            if st.button(label, key=f"history_{index}", help=entry["summary"], use_container_width=True):
                st.session_state.report = entry["report"]
                st.rerun()
    else:
        st.caption("完成一次检查后，历史记录会显示在这里。")

    st.divider()
    st.markdown("## 📚 规则说明")
    rule_icons = {"高": "🔴", "中高": "🟠", "中": "🟡", "低": "⚪"}
    for rid, rule in load_rules().items():
        with st.expander(f"{rule_icons.get(rule['level'], '🔹')} {rid}｜{rule['name']}"):
            st.markdown(f"**匹配**　{rule['matcher']}")
            st.markdown(f"**默认等级**　{rule['level']}")
            st.markdown(rule["suggestion"])

if not api_key or api_key in {"sk-...", "your-ark-api-key"}:
    st.warning("⚠️ 未配置火山方舟 API Key，语义审查降级：A-05、A-07、A-09 将标记为需人工审核；确定性规则仍正常运行。")

st.markdown(
    '<div class="section-card"><div class="section-title">01｜提交检查材料</div>'
    '<div class="section-subtitle">粘贴文案，或上传海报/截图；多项材料将作为同一则广告联合检查。</div></div>',
    unsafe_allow_html=True,
)
text = st.text_area(
    "广告文案",
    height=180,
    max_chars=10000,
    placeholder="粘贴文案，或上传海报/截图。例如：全网最低价，0元领，仅需运费9.9元……",
)
evidence = st.text_area(
    "补充证据说明（可选）",
    height=90,
    max_chars=5000,
    placeholder="填写数据来源、统计口径、活动时间范围或授权材料说明……",
    help="系统不验证证明材料真伪，关键证据仍需人工核验。",
)
uploads = st.file_uploader(
    "上传海报或活动页截图（PNG/JPEG，最多 5 张）",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True,
)
complete = st.checkbox("我已提供完整页面/完整截图", value=True)

if st.button("🔍 开始检查", type="primary", use_container_width=True):
    if len(uploads) > 5:
        st.error("每次最多上传 5 张图片。")
    elif not text.strip() and not uploads:
        st.error("请至少输入文字或上传一张图片。")
    else:
        ocr_parts, reasons, confidences, semantic_images = [], [], [], []
        for upload in uploads:
            if upload.size > 10 * 1024 * 1024:
                reasons.append(f"{upload.name} 超过 10 MB，未处理")
                continue
            try:
                raw_image = upload.getvalue()
                result = extract_image(raw_image)
                ocr_parts.append(f"[{upload.name}]\n{result.text}")
                mime_type = upload.type if upload.type in {"image/png", "image/jpeg"} else "image/jpeg"
                semantic_images.append((raw_image, mime_type))
                reasons.extend(f"{upload.name}：{reason}" for reason in result.reasons)
                if result.confidence is not None:
                    confidences.append(result.confidence)
            except Exception as exc:
                reasons.append(f"{upload.name}：OCR 不可用（{type(exc).__name__}）")
        if uploads and not complete:
            reasons.append("用户标记截图或页面不完整")
        ocr_text = "\n".join(ocr_parts)
        combined = "\n".join(part for part in [text.strip(), ocr_text, evidence.strip()] if part)
        if len(combined) > 30000:
            st.error("输入文字与 OCR 结果合计超过 30,000 字符，请拆分后重试。")
        else:
            average = round(sum(confidences) / len(confidences), 1) if confidences else None
            with st.spinner("正在执行规则检查与语义审查……"):
                report = analyze(
                    combined,
                    api_key=api_key or None,
                    model=model,
                    base_url=base_url,
                    semantic_images=semantic_images,
                    a10_reasons=reasons,
                    ocr_text=ocr_text,
                    ocr_confidence=average,
                )
            st.session_state.report = report
            level_rank = {"高": 4, "中高": 3, "中": 2, "低": 1}
            highest = max((finding.level for finding in report.findings), key=lambda level: level_rank.get(level, 0), default="无")
            source_summary = text.strip() or "、".join(upload.name for upload in uploads) or "图片材料"
            st.session_state.history.insert(0, {
                "time": datetime.now().strftime("%H:%M:%S"),
                "summary": source_summary[:50],
                "count": len(report.findings),
                "highest": highest,
                "report": report,
            })
            st.session_state.history = st.session_state.history[:10]
            st.rerun()

report = st.session_state.report
if report:
    st.markdown(
        '<div class="section-card"><div class="section-title">02｜检查结果</div>'
        '<div class="section-subtitle">先查看整体结论，再按风险等级筛选并展开详情。</div></div>',
        unsafe_allow_html=True,
    )
    verdict_color = "red" if "拦截" in report.verdict else "orange" if "人工" in report.verdict else "green"
    high_count = sum(finding.level == "高" for finding in report.findings)
    left, middle, right = st.columns(3)
    left.metric("检查结论", report.verdict)
    middle.metric("风险项", len(report.findings))
    right.metric("高风险", high_count)
    st.markdown(f"### 结论：:{verdict_color}[{report.verdict}]")
    st.info(report.semantic_message)

    if report.ocr_text:
        with st.expander("📝 OCR 识别文字（可复制校对后重新提交）"):
            st.text_area("OCR 原始结果", report.ocr_text, height=160, disabled=True)

    rows = [finding.to_dict() for finding in report.findings]
    if rows:
        control_left, control_right = st.columns([1, 1])
        selected_levels = control_left.multiselect(
            "筛选风险等级",
            ["高", "中高", "中", "低"],
            default=["高", "中高", "中", "低"],
        )
        sort_mode = control_right.selectbox("排序", ["风险等级：高到低", "风险等级：低到高", "规则编号"])
        filtered = [row for row in rows if row["风险等级"] in selected_levels]
        rank = {"高": 4, "中高": 3, "中": 2, "低": 1}
        if sort_mode == "规则编号":
            filtered.sort(key=lambda row: row["对应规则"])
        else:
            filtered.sort(key=lambda row: rank.get(row["风险等级"], 0), reverse=sort_mode.endswith("高到低"))
        frame = pd.DataFrame(filtered)

        def shade_level(value: str) -> str:
            return {
                "高": "background-color:#fde8eb;color:#a80f21;font-weight:700",
                "中高": "background-color:#fff0df;color:#a64b00;font-weight:700",
                "中": "background-color:#fff7cc;color:#806300;font-weight:700",
                "低": "background-color:#edf0f2;color:#59636e;font-weight:700",
            }.get(value, "")

        if not frame.empty:
            st.dataframe(frame.style.map(shade_level, subset=["风险等级"]), use_container_width=True, hide_index=True)
        else:
            st.caption("当前筛选条件下没有风险项。")

        st.markdown(
            '<div class="section-card"><div class="section-title">03｜风险详情</div>'
            '<div class="section-subtitle">逐项查看命中原文、规则依据和可执行的修改建议。</div></div>',
            unsafe_allow_html=True,
        )
        class_name = {"高": "risk-high", "中高": "risk-mid-high", "中": "risk-mid", "低": "risk-low"}
        for index, finding in enumerate(report.findings, 1):
            item = finding.to_dict()
            with st.expander(f"{index}. {item['对应规则']}｜{item['风险内容原文']}", expanded=index == 1):
                css_class = class_name.get(item["风险等级"], "risk-low")
                st.markdown(f'<span class="risk-pill {css_class}">{item["风险等级"]}风险</span>', unsafe_allow_html=True)
                st.markdown(f"**风险类型：** {item['风险类型']}　　**置信度：** {item['置信度']}")
                st.markdown(f"**原因：** {item['原因']}")
                st.markdown(f"**修改建议：** {item['修改建议']}")
                st.markdown(f"**是否需要人工审核：** {'是' if item['是否需要人工审核'] else '否'}")
    else:
        st.success("未发现题设 A-01～A-10 规则风险。请注意，这不等同于完整法律合规结论。")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_col, markdown_col, word_col = st.columns(3)
    json_col.download_button(
        "⬇️ 导出 JSON", to_json(report), "ad-compliance-report.json", "application/json", use_container_width=True
    )
    markdown_col.download_button(
        "⬇️ 导出 Markdown", to_markdown(report), "ad-compliance-report.md", "text/markdown", use_container_width=True
    )
    word_col.download_button(
        "⬇️ 导出 Word",
        to_docx(report),
        f"合规检查报告_{timestamp}.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
    )

st.caption("隐私提示：历史仅保存在当前 Streamlit 会话中；刷新会话或云容器重启后可能丢失。")
