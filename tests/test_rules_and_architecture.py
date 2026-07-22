from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path

import pytest

from ltc_benefit_agent.tools.copay import CopayInput
from ltc_benefit_agent.tools.eligibility import EligibilityInput
from ltc_benefit_agent.tools.rules import (
    CARE_AND_PROFESSIONAL_QUOTAS,
    COPAY_PERCENTAGES,
    RULE_SNAPSHOTS,
    RuleVersion,
    get_rule_snapshot,
)


TOOLS_DIR = Path(__file__).parents[1] / "src" / "ltc_benefit_agent" / "tools"


@pytest.mark.parametrize("version", list(RuleVersion))
def test_rule_metadata_is_complete(version: RuleVersion) -> None:
    snapshot = get_rule_snapshot(version)
    assert snapshot.version is version
    assert snapshot.effective_date <= snapshot.verified_on
    assert snapshot.verified_on.isoformat() == "2026-07-22"
    assert snapshot.regulation_url.startswith("https://")
    assert snapshot.quota_url.startswith("https://")
    assert snapshot.copay_url.startswith("https://")
    assert snapshot.notes


def test_rule_maps_cover_exact_public_enums() -> None:
    assert set(RULE_SNAPSHOTS) == set(RuleVersion)
    assert set(CARE_AND_PROFESSIONAL_QUOTAS) == set(RuleVersion)
    assert set(COPAY_PERCENTAGES) == {"FIRST", "SECOND", "THIRD"}
    for quota_map in CARE_AND_PROFESSIONAL_QUOTAS.values():
        assert list(quota_map) == list(range(2, 9))


def test_current_snapshot_records_staged_effective_dates() -> None:
    snapshot = get_rule_snapshot(RuleVersion.CURRENT_2026_07)
    notes = " ".join(snapshot.notes)
    assert snapshot.label.endswith("2026-07-01 完整快照）")
    assert "2025-09-01" in notes
    assert "2026-01-01" in notes
    assert "2026-07-01" in notes
    assert "不代表所有規則都在該日才生效" in notes


def test_rule_maps_are_read_only() -> None:
    with pytest.raises(TypeError):
        RULE_SNAPSHOTS[RuleVersion.LEGACY_2022] = get_rule_snapshot(  # type: ignore[index]
            RuleVersion.CURRENT_2026_07
        )
    with pytest.raises(TypeError):
        CARE_AND_PROFESSIONAL_QUOTAS[RuleVersion.CURRENT_2026_07][2] = 1  # type: ignore[index]


def test_business_modules_have_no_langchain_env_or_network_imports() -> None:
    forbidden_roots = {
        "langchain",
        "langgraph",
        "os",
        "dotenv",
        "requests",
        "httpx",
        "socket",
    }
    for filename in ("rules.py", "eligibility.py", "copay.py"):
        tree = ast.parse((TOOLS_DIR / filename).read_text(encoding="utf-8"))
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])
        assert imported_roots.isdisjoint(forbidden_roots), (
            filename,
            imported_roots & forbidden_roots,
        )


def test_calculation_module_contains_no_float_literals() -> None:
    tree = ast.parse((TOOLS_DIR / "copay.py").read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.Constant) and isinstance(node.value, float)
        for node in ast.walk(tree)
    )


def test_public_inputs_do_not_accept_pii_fields() -> None:
    pii_names = {"name", "id_number", "national_id", "phone", "address"}
    assert pii_names.isdisjoint(field.name for field in fields(EligibilityInput))
    assert pii_names.isdisjoint(field.name for field in fields(CopayInput))


def test_invalid_rule_version_lookup_is_rejected() -> None:
    with pytest.raises(TypeError):
        get_rule_snapshot("CURRENT_2026_07")  # type: ignore[arg-type]
