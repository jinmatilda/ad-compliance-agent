from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_rules(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    rule_path = Path(path) if path else Path(__file__).resolve().parent.parent / "rules.yaml"
    data = yaml.safe_load(rule_path.read_text(encoding="utf-8"))
    required = {"rule_id", "name", "level", "matcher", "manual", "suggestion"}
    rules: dict[str, dict[str, Any]] = {}
    for item in data.get("rules", []):
        missing = required - item.keys()
        if missing:
            raise ValueError(f"规则缺少字段: {sorted(missing)}")
        rid = item["rule_id"]
        if rid in rules:
            raise ValueError(f"重复规则: {rid}")
        rules[rid] = item
    expected = {f"A-{i:02d}" for i in range(1, 11)}
    if set(rules) != expected:
        raise ValueError("规则库必须且只能包含 A-01 至 A-10")
    return rules

