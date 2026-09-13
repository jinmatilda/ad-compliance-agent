from __future__ import annotations

import os

import streamlit as st

from adcheck.engine import analyze
from adcheck.exporters import to_json, to_markdown
from adcheck.ocr import extract_image
from adcheck.rules import load_rules

st.set_page_config(page_title="广告宣传材料合规检查助手", page_icon="🛡️", layout="wide")
st.title("🛡️ 广告宣传材料合规检查助手")
st.caption("依据题目 A-01～A-10 进行发布前第一轮提示；结果不构成法律意见。")

try:
    api_key = st.secrets["OPENAI_API_KEY"]
except (KeyError, FileNotFoundError):
    api_key = os.getenv("OPENAI_API_KEY", "")
try:
    model = st.secrets.get("OPENAI_MODEL", "gpt-4.1-mini")
except FileNotFoundError:
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

if not api_key or api_key == "sk-...":
    st.warning("未配置 API Key，语义审查降级：A-05、A-07、A-09 将标记为需人工审核。确定性规则仍正常运行。")

with st.sidebar:
    st.header("规则说明")
    for rid, rule in load_rules().items():
        with st.expander(f"{rid}｜{rule['name']}"):
            st.write(f"匹配：{rule['matcher']}")
            st.write(f"默认等级：{rule['level']}")
            st.write(rule["suggestion"])

text = st.text_area("广告文案", height=180, max_chars=10000, placeholder="粘贴朋友圈文案、海报文字或活动页文案……")
evidence = st.text_area("补充证据说明（可选）", height=90, max_chars=5000, help="可填写数据来源、统计口径、时间范围或授权材料说明；系统不验证材料真伪。")
uploads = st.file_uploader("上传海报或活动页截图（PNG/JPEG，最多 5 张）", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
complete = st.checkbox("我已提供完整页面/完整截图", value=True)

if "report" not in st.session_state:
    st.session_state.report = None

if st.button("开始检查", type="primary", use_container_width=True):
    if len(uploads) > 5:
        st.error("每次最多上传 5 张图片。")
    elif not text.strip() and not uploads:
        st.error("请至少输入文字或上传一张图片。")
    else:
        ocr_parts, reasons, confidences = [], [], []
        for upload in uploads:
            if upload.size > 10 * 1024 * 1024:
                reasons.append(f"{upload.name} 超过 10 MB，未处理")
                continue
            try:
                result = extract_image(upload.getvalue())
                ocr_parts.append(f"[{upload.name}]\n{result.text}")
                reasons.extend(f"{upload.name}：{r}" for r in result.reasons)
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
            avg = round(sum(confidences) / len(confidences), 1) if confidences else None
            with st.spinner("正在执行规则检查与语义审查……"):
                st.session_state.report = analyze(combined, api_key=api_key or None, model=model,
                                                  a10_reasons=reasons, ocr_text=ocr_text,
                                                  ocr_confidence=avg)

report = st.session_state.report
if report:
    st.divider()
    color = "red" if "拦截" in report.verdict else "orange" if "人工" in report.verdict else "green"
    st.markdown(f"### 检查结论：:{color}[{report.verdict}]")
    st.info(report.semantic_message)
    if report.ocr_text:
        with st.expander("OCR 识别文字（可复制校对后重新提交）"):
            st.text_area("OCR 原始结果", report.ocr_text, height=160, disabled=True)
    rows = [f.to_dict() for f in report.findings]
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.subheader("风险详情")
        for idx, finding in enumerate(report.findings, 1):
            item = finding.to_dict()
            with st.expander(f"{idx}. {item['对应规则']}｜{item['风险内容原文']}", expanded=idx == 1):
                st.write(f"**风险类型：** {item['风险类型']}　**等级：** {item['风险等级']}　**置信度：** {item['置信度']}")
                st.write(f"**原因：** {item['原因']}")
                st.write(f"**修改建议：** {item['修改建议']}")
                st.write(f"**人工审核：** {'是' if item['是否需要人工审核'] else '否'}")
    else:
        st.success("未发现题设 A-01～A-10 规则风险。请注意，这不等同于完整法律合规结论。")
    left, right = st.columns(2)
    left.download_button("导出 JSON", to_json(report), "ad-compliance-report.json", "application/json", use_container_width=True)
    right.download_button("导出 Markdown", to_markdown(report), "ad-compliance-report.md", "text/markdown", use_container_width=True)

