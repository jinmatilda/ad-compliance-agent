from __future__ import annotations

import re
from typing import Iterable

from .models import Finding, Report
from .rules import load_rules
from .semantic import review

ABSOLUTE = re.compile(r"全网最低|全球领先|行业第一|销量第一|排名第一|第一名|唯一|最佳|最强|100%|百分之百")
SENSITIVE = re.compile(r"治疗|治愈|无副作用|零风险|稳赚")
PROMOTION = re.compile(r"满\s*\d+(?:\.\d+)?\s*减\s*\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*折|赠品|买\w*送\w*|优惠")
DATE = re.compile(r"(?:20\d{2}[年./-])?\d{1,2}[月./-]\d{1,2}日?")
DATA = re.compile(r"\d+(?:\.\d+)?\s*(?:%|％|倍|万|亿|人|件|分钟|小时|天)")
SOURCE = re.compile(r"来源|数据来自|据.{0,12}(?:报告|统计|调查|监测)")
CALIBER = re.compile(r"统计口径|样本|基于|以.{0,12}为准|计算方式")
TIME_RANGE = re.compile(r"20\d{2}年|近\d+[年月日]|截至|期间|年度|季度")
LIMITS = {
    "适用商品": re.compile(r"适用|指定商品|部分商品|商品范围"),
    "渠道": re.compile(r"线上|线下|门店|小程序|APP|渠道"),
    "名额": re.compile(r"限量|名额|前\d+|数量有限"),
    "叠加限制": re.compile(r"不可叠加|可叠加|不与.{0,8}同享|每人限")
}
FREE = re.compile(r"免费|0\s*元|零元")
FEE = re.compile(r"押金|运费|自动续费|服务费|手续费|仅需\s*\d|另付")
EFFECT = re.compile(r"(?:保证|立刻|立即|彻底|永久).{0,10}(?:美白|祛斑|减肥|改善|提升|有效|见效)|(?:美白|祛斑|减肥|改善|提升).{0,8}(?:保证|见效|有效)")
COMPARE = re.compile(r"秒杀|碾压|吊打|远超|完胜|优于所有|其他品牌都|竞品.{0,8}(?:差|不行)")
ENDORSE = re.compile(r"专家推荐|权威认证|官方认证|机构认证|用户一致好评|万人好评|明星推荐|消费者评价")


def _finding(rules, rid: str, quote: str, reason: str, confidence="高", status="明确风险", source="输入文本"):
    r = rules[rid]
    return Finding(quote, r["name"], rid, r["name"], r["level"], r["suggestion"], True, confidence, reason, status, source)


def _matches(pattern: re.Pattern[str], text: str) -> Iterable[str]:
    return dict.fromkeys(m.group(0) for m in pattern.finditer(text))


def analyze(text: str, *, api_key: str | None = None,
            model: str = "doubao-seed-2-0-lite-260215",
            base_url: str | None = "https://ark.cn-beijing.volces.com/api/v3",
            semantic_images: list[tuple[bytes, str]] | None = None,
            a10_reasons: list[str] | None = None, ocr_text: str = "",
            ocr_confidence: float | None = None) -> Report:
    rules = load_rules()
    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()

    def add(rid, quote, reason, confidence="高", status="明确风险", source="输入文本"):
        key = (rid, quote)
        if key not in seen:
            seen.add(key)
            findings.append(_finding(rules, rid, quote, reason, confidence, status, source))

    for quote in _matches(SENSITIVE, text):
        add("A-06", quote, "命中必须拦截并人工复核的敏感词")
    for quote in _matches(ABSOLUTE, text):
        add("A-01", quote, "命中绝对化表述，需要可核验证据或删除")

    if PROMOTION.search(text):
        dates = list(DATE.finditer(text))
        if len(dates) < 2:
            add("A-03", PROMOTION.search(text).group(0), "优惠未同时披露开始和结束日期", "高")
        missing = [name for name, pat in LIMITS.items() if not pat.search(text)]
        if missing:
            add("A-04", PROMOTION.search(text).group(0), "未披露主要条件：" + "、".join(missing), "中", "待核实")

    for match in DATA.finditer(text):
        context = text[max(0, match.start()-50):match.end()+80]
        missing = []
        if not SOURCE.search(context): missing.append("来源")
        if not CALIBER.search(context): missing.append("统计口径")
        if not TIME_RANGE.search(context): missing.append("时间范围")
        if missing:
            add("A-02", match.group(0), "数据宣传缺少：" + "、".join(missing), "中", "待核实")

    if FREE.search(text) and FEE.search(text):
        start = max(0, min(FREE.search(text).start(), FEE.search(text).start()) - 10)
        end = min(len(text), max(FREE.search(text).end(), FEE.search(text).end()) + 10)
        add("A-08", text[start:end], "免费/零元宣传与必要费用同时出现，需显著披露费用条件")

    for rid, pattern, reason in [
        ("A-05", EFFECT, "出现未经验证的效果承诺候选"),
        ("A-07", COMPARE, "出现竞品贬损或全面优越比较候选"),
        ("A-09", ENDORSE, "背书真实性与授权无法由 Agent 独立确认"),
    ]:
        for quote in _matches(pattern, text):
            add(rid, quote, reason, "中", "待核实")

    for reason in a10_reasons or []:
        add("A-10", "图片/截图", reason, "低", "无法判断", "图片质量")

    if api_key:
        try:
            semantic = review(
                text,
                api_key,
                model,
                base_url=base_url,
                images=semantic_images,
            )
            for item in semantic:
                rid, quote = item["rule_id"], item["quote"]
                if quote and (quote in text or semantic_images):
                    source = "图片语义审查" if quote not in text else "输入文本"
                    add(rid, quote, item["reason"], item["confidence"], "待核实", source)
            semantic_status = "完成"
            semantic_message = "火山方舟语义与视觉审查已完成；确定性规则命中不会被撤销。"
        except Exception as exc:
            semantic_status = "降级"
            semantic_message = f"语义审查调用失败，A-05/A-07/A-09 转人工：{type(exc).__name__}"
            for rid in ("A-05", "A-07", "A-09"):
                add(rid, "语义审查未完成", semantic_message, "低", "无法判断", "系统状态")
    else:
        semantic_status = "降级"
        semantic_message = "未配置 API Key，语义审查降级；A-05、A-07、A-09 需人工审核。"
        for rid in ("A-05", "A-07", "A-09"):
            add(rid, "语义审查未完成", semantic_message, "低", "无法判断", "系统状态")

    return Report(findings, semantic_status, semantic_message, ocr_text, ocr_confidence)
