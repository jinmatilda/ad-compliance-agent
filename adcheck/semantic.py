from __future__ import annotations

import json
from typing import Any


SEMANTIC_RULES = ("A-01", "A-05", "A-07", "A-09")


def review(text: str, api_key: str, model: str = "gpt-4.1-mini") -> list[dict[str, Any]]:
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
        "你是广告材料初筛器，只检查 A-01绝对化、A-05未经验证效果承诺、"
        "A-07竞品贬损/无依据全面优越比较、A-09评价或专家机构背书。"
        "quote 必须逐字来自输入；没有充分依据则不输出。A-09只提示材料和人工核验，不能认定真伪。\n输入：\n"
        + text
    )
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=prompt,
        text={"format": {"type": "json_schema", "name": "semantic_findings", "strict": True, "schema": schema}},
    )
    return json.loads(response.output_text)["findings"]

