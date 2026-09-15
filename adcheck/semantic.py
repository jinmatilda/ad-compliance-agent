from __future__ import annotations

import base64
import json
from typing import Any


SEMANTIC_RULES = ("A-01", "A-05", "A-07", "A-09")


def _data_url(raw: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def review(
    text: str,
    api_key: str,
    model: str = "doubao-seed-2-0-lite-260215",
    *,
    base_url: str | None = "https://ark.cn-beijing.volces.com/api/v3",
    images: list[tuple[bytes, str]] | None = None,
) -> list[dict[str, Any]]:
    from openai import OpenAI

    schema = {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "rule_id": {"type": "string", "enum": list(SEMANTIC_RULES)},
                        "quote": {"type": "string"},
                        "reason": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["高", "中", "低"]},
                    },
                    "required": ["rule_id", "quote", "reason", "confidence"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["findings"],
        "additionalProperties": False,
    }
    prompt = (
        "你是广告材料初筛器。结合输入文字和上传图片，只检查 A-01绝对化、"
        "A-05未经验证效果承诺、A-07竞品贬损/无依据全面优越比较、"
        "A-09评价或专家机构背书。quote 必须逐字来自输入文字或图片中清晰可见的文字；"
        "无法确认文字时不要猜测。没有充分依据则不输出。A-09只提示补充材料和人工核验，"
        "不能认定真伪。每项必须说明判断理由。\n输入文字：\n" + text
    )
    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)
    content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    for raw, mime_type in images or []:
        content.append({"type": "input_image", "image_url": _data_url(raw, mime_type)})
    response = client.responses.create(
        model=model,
        input=[{"role": "user", "content": content}],
        text={"format": {"type": "json_schema", "name": "semantic_findings", "strict": True, "schema": schema}},
    )
    payload = json.loads(response.output_text)
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise ValueError("模型响应缺少 findings 数组")
    return findings
