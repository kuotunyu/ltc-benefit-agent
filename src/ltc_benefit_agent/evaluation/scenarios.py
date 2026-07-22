"""載入並驗證版本固定的 20 題診斷集。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class FollowupExpectation:
    after_turn: int
    any_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvaluationScenario:
    scenario_id: str
    title: str
    tags: tuple[str, ...]
    user_turns: tuple[str, ...]
    followups: tuple[FollowupExpectation, ...]
    required_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    expected_tool_args: dict[str, dict[str, Any]]
    expected_money: dict[str, int] | None
    pii_secrets: tuple[str, ...]


def default_scenario_path() -> Path:
    return Path(__file__).resolve().parents[3] / "eval" / "scenarios.json"


def load_scenarios(path: Path | None = None) -> tuple[EvaluationScenario, ...]:
    source = path or default_scenario_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    scenarios = tuple(
        EvaluationScenario(
            scenario_id=item["id"],
            title=item["title"],
            tags=tuple(item["tags"]),
            user_turns=tuple(item["user_turns"]),
            followups=tuple(
                FollowupExpectation(
                    after_turn=followup["after_turn"],
                    any_terms=tuple(followup["any_terms"]),
                )
                for followup in item.get("followups", [])
            ),
            required_tools=tuple(item["required_tools"]),
            forbidden_tools=tuple(item.get("forbidden_tools", [])),
            expected_tool_args=item.get("expected_tool_args", {}),
            expected_money=item.get("expected_money"),
            pii_secrets=tuple(item.get("pii_secrets", [])),
        )
        for item in raw
    )
    ids = [scenario.scenario_id for scenario in scenarios]
    if len(scenarios) != 20:
        raise ValueError(f"診斷集必須固定為 20 題，目前為 {len(scenarios)} 題")
    if len(ids) != len(set(ids)):
        raise ValueError("診斷集 id 不得重複")
    for scenario in scenarios:
        if not scenario.user_turns:
            raise ValueError(f"{scenario.scenario_id} 缺少 user_turns")
        for followup in scenario.followups:
            if not 0 <= followup.after_turn < len(scenario.user_turns):
                raise ValueError(f"{scenario.scenario_id} followup turn 越界")
    return scenarios
