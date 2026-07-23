"""Read-only consistency checks across approved rule evidence and project files."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from ltc_benefit_agent.tools.rules import (
    CARE_AND_PROFESSIONAL_QUOTAS,
    COPAY_PERCENTAGES,
    FOREIGN_CAREGIVER_QUOTA_PERCENT,
    RULE_SNAPSHOTS,
    RuleVersion,
)

from .extractors import (
    extract_copay_numbers_from_text,
    extract_quota_numbers_from_text,
)
from .manifest import load_manifest
from .models import RuleSourceManifestSet


class ConsistencyStatus(StrEnum):
    """Outcome of the deterministic cross-file consistency check."""

    CONSISTENT = "CONSISTENT"
    DRIFT_DETECTED = "DRIFT_DETECTED"


@dataclass(frozen=True, slots=True)
class ConsistencyIssue:
    """One mismatch that requires an author to reconcile project evidence."""

    scope: str
    path: str
    expected: Any
    actual: Any
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "path": self.path,
            "expected": self.expected,
            "actual": self.actual,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True, slots=True)
class ConsistencyCheckResult:
    """Complete evidence from a read-only project consistency check."""

    status: ConsistencyStatus
    checked_targets: tuple[str, ...]
    issues: tuple[ConsistencyIssue, ...]
    writes_performed: bool = False

    def __post_init__(self) -> None:
        if self.writes_performed:
            raise ValueError("Consistency checks must never report writes_performed=true")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "checked_targets": list(self.checked_targets),
            "issues": [issue.to_dict() for issue in self.issues],
            "writes_performed": self.writes_performed,
        }


def _append_if_different(
    issues: list[ConsistencyIssue],
    *,
    scope: str,
    path: str,
    expected: Any,
    actual: Any,
    recommendation: str,
) -> None:
    if expected != actual:
        issues.append(
            ConsistencyIssue(
                scope=scope,
                path=path,
                expected=expected,
                actual=actual,
                recommendation=recommendation,
            )
        )


def _verified_date(value: str) -> str:
    return value[:10]


def _literal_assertion(
    test_path: Path,
    expected_path: tuple[str, ...],
) -> Any:
    """Return a literal compared with the requested subscript path in an assert."""

    tree = ast.parse(test_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert) or not isinstance(node.test, ast.Compare):
            continue
        if len(node.test.ops) != 1 or not isinstance(node.test.ops[0], ast.Eq):
            continue
        if _expression_path(node.test.left) != expected_path:
            continue
        if len(node.test.comparators) != 1:
            continue
        return ast.literal_eval(node.test.comparators[0])
    raise ValueError(f"Missing literal assertion: {'.'.join(expected_path)}")


def _expression_path(node: ast.expr) -> tuple[str, ...] | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Subscript):
        if not isinstance(current.slice, ast.Constant):
            return None
        parts.append(str(current.slice.value))
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return tuple(reversed(parts))


def _read_fixture_semantics(
    path: Path,
    *,
    kind: str,
) -> Any:
    text = path.read_text(encoding="utf-8")
    if kind == "quota":
        return extract_quota_numbers_from_text(text)["care_and_professional_monthly"]
    return extract_copay_numbers_from_text(text)["percentage_matrix"][
        "care_and_professional"
    ]


def check_project_consistency(
    project_root: str | Path,
    manifest_set: RuleSourceManifestSet | None = None,
) -> ConsistencyCheckResult:
    """Compare manifest semantics with runtime rules, README, fixtures and tests."""

    root = Path(project_root).resolve()
    manifests = manifest_set or load_manifest()
    issues: list[ConsistencyIssue] = []
    checked_targets = (
        "manifest_vs_runtime_metadata",
        "manifest_vs_runtime_constants",
        "manifest_vs_readme",
        "manifest_vs_test_fixtures",
        "manifest_vs_test_assertions",
    )

    legacy = manifests.get("legacy-2022-regulation")
    current = manifests.get("current-2026-07-regulation")
    quota = manifests.get("current-care-professional-quota")
    copay = manifests.get("current-copay-percentages")
    runtime_legacy = RULE_SNAPSHOTS[RuleVersion.LEGACY_2022]
    runtime_current = RULE_SNAPSHOTS[RuleVersion.CURRENT_2026_07]

    metadata_pairs = (
        (
            "legacy.regulation_url",
            legacy.canonical_url,
            runtime_legacy.regulation_url,
        ),
        (
            "legacy.rule_version",
            legacy.rule_version,
            runtime_legacy.version.value,
        ),
        (
            "legacy.effective_date",
            legacy.effective_date,
            runtime_legacy.effective_date.isoformat(),
        ),
        (
            "legacy.verified_at",
            _verified_date(legacy.verified_at),
            runtime_legacy.verified_on.isoformat(),
        ),
        (
            "current.regulation_url",
            current.canonical_url,
            runtime_current.regulation_url,
        ),
        (
            "current.quota_url",
            quota.canonical_url,
            runtime_current.quota_url,
        ),
        (
            "current.copay_url",
            copay.canonical_url,
            runtime_current.copay_url,
        ),
        (
            "current.rule_version",
            current.rule_version,
            runtime_current.version.value,
        ),
        (
            "current.effective_date",
            current.effective_date,
            runtime_current.effective_date.isoformat(),
        ),
        (
            "current.verified_at",
            _verified_date(current.verified_at),
            runtime_current.verified_on.isoformat(),
        ),
    )
    for path, expected, actual in metadata_pairs:
        _append_if_different(
            issues,
            scope="runtime_metadata",
            path=path,
            expected=expected,
            actual=actual,
            recommendation="同步 manifest 與 tools/rules.py 的來源 metadata，並重新測試。",
        )

    manifest_quotas_by_level = {
        str(level): int(amount)
        for level, amount in quota.semantic_snapshot[
            "care_and_professional_monthly"
        ].items()
    }
    manifest_quotas = {
        int(level): int(amount)
        for level, amount in manifest_quotas_by_level.items()
    }
    for version in (RuleVersion.LEGACY_2022, RuleVersion.CURRENT_2026_07):
        _append_if_different(
            issues,
            scope="runtime_constants",
            path=f"CARE_AND_PROFESSIONAL_QUOTAS.{version.value}",
            expected=manifest_quotas,
            actual=dict(CARE_AND_PROFESSIONAL_QUOTAS[version]),
            recommendation="人工核准官方差異後，另開小功能更新額度常數與金額矩陣。",
        )

    manifest_copay = list(
        copay.semantic_snapshot["percentage_matrix"]["care_and_professional"]
    )
    runtime_copay = [
        COPAY_PERCENTAGES["FIRST"],
        COPAY_PERCENTAGES["SECOND"],
        COPAY_PERCENTAGES["THIRD"],
    ]
    _append_if_different(
        issues,
        scope="runtime_constants",
        path="COPAY_PERCENTAGES.care_and_professional",
        expected=manifest_copay,
        actual=runtime_copay,
        recommendation="人工核准官方差異後，另開小功能更新部分負擔與進位測試。",
    )
    for source in (legacy, current):
        _append_if_different(
            issues,
            scope="runtime_constants",
            path=f"FOREIGN_CAREGIVER_QUOTA_PERCENT.{source.rule_version}",
            expected=source.semantic_snapshot["foreign_caregiver"]["quota_percent"],
            actual=FOREIGN_CAREGIVER_QUOTA_PERCENT,
            recommendation="人工核准官方差異後，另開小功能更新外籍看護額度規則。",
        )

    readme_path = root / "README.md"
    try:
        readme = readme_path.read_text(encoding="utf-8")
    except OSError as exc:
        issues.append(
            ConsistencyIssue(
                scope="readme",
                path="README.md",
                expected="可讀取的 README.md",
                actual=f"{type(exc).__name__}: {exc}",
                recommendation="恢復 README.md 後重新執行一致性檢查。",
            )
        )
    else:
        required_readme_fragments = {
            "version.LEGACY_2022": (
                "| `LEGACY_2022` | 2022-02-01 |",
                "README 的舊制版本日期需與 manifest 一致。",
            ),
            "version.CURRENT_2026_07": (
                "| `CURRENT_2026_07` | 2026-07-01 完整快照 |",
                "README 的現制版本日期需與 manifest 一致。",
            ),
            "quota.amounts": (
                "CMS 2–8 的照顧及專業服務月額為 "
                + "、".join(f"{amount:,}" for amount in manifest_quotas.values())
                + " 元。",
                "README 的 CMS 2–8 月額需與 manifest 一致。",
            ),
            "copay.percentages": (
                "部分負擔比率為第一類 0%、第二類 5%、第三類 16%。",
                "README 的部分負擔比率需與 manifest 一致。",
            ),
        }
        for source in manifests.sources:
            required_readme_fragments[f"url.{source.source_id}"] = (
                source.canonical_url,
                "README 的官方來源 URL 需與 allowlist manifest 一致。",
            )
        for path, (fragment, recommendation) in required_readme_fragments.items():
            _append_if_different(
                issues,
                scope="readme",
                path=path,
                expected=fragment,
                actual=fragment if fragment in readme else "<missing>",
                recommendation=recommendation,
            )

    fixture_checks = (
        (
            root / "tests" / "fixtures" / "rule_audit" / "quota-table.txt",
            "quota",
            "quota_fixture.care_and_professional_monthly",
            manifest_quotas_by_level,
        ),
        (
            root / "tests" / "fixtures" / "rule_audit" / "copay-table.txt",
            "copay",
            "copay_fixture.care_and_professional",
            manifest_copay,
        ),
    )
    for path, kind, issue_path, expected in fixture_checks:
        try:
            actual = _read_fixture_semantics(path, kind=kind)
        except (OSError, ValueError, RuntimeError) as exc:
            actual = f"{type(exc).__name__}: {exc}"
        _append_if_different(
            issues,
            scope="test_fixtures",
            path=issue_path,
            expected=expected,
            actual=actual,
            recommendation="同步離線 fixture 與核准 manifest，並重跑 extractor 測試。",
        )

    test_path = root / "tests" / "test_rule_audit.py"
    assertion_checks = (
        (
            ("result", "care_and_professional_monthly"),
            "test_assertions.care_and_professional_monthly",
            manifest_quotas_by_level,
        ),
        (
            ("result", "percentage_matrix", "care_and_professional"),
            "test_assertions.care_and_professional",
            manifest_copay,
        ),
    )
    for expression_path, issue_path, expected in assertion_checks:
        try:
            actual = _literal_assertion(test_path, expression_path)
        except (OSError, SyntaxError, ValueError) as exc:
            actual = f"{type(exc).__name__}: {exc}"
        _append_if_different(
            issues,
            scope="test_assertions",
            path=issue_path,
            expected=expected,
            actual=actual,
            recommendation="同步明確測試預期值與核准 manifest，不可只改常數而不改測試。",
        )

    return ConsistencyCheckResult(
        status=(
            ConsistencyStatus.DRIFT_DETECTED
            if issues
            else ConsistencyStatus.CONSISTENT
        ),
        checked_targets=checked_targets,
        issues=tuple(issues),
        writes_performed=False,
    )
