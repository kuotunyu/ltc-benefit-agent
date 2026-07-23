from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from ltc_benefit_agent.audit import (
    ConsistencyStatus,
    ReviewDecision,
    RuleAuditStatus,
    audit_content,
    check_project_consistency,
    load_audit_evidence,
    load_manifest,
    render_review_report,
    unavailable_result,
)
from ltc_benefit_agent.audit.cli import main as audit_cli_main
from ltc_benefit_agent.audit.extractors import (
    ExtractionReviewRequiredError,
    extract_copay_numbers_from_text,
    extract_quota_numbers_from_text,
)
from ltc_benefit_agent.audit.manifest import (
    APPROVED_OFFICIAL_URLS,
    default_manifest_path,
    semantic_fingerprint,
)


ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "rule_audit"
RULE_FILES = tuple(
    ROOT / "src" / "ltc_benefit_agent" / "tools" / filename
    for filename in ("rules.py", "eligibility.py", "copay.py")
)


def _current_manifest():
    return load_manifest().get("current-2026-07-regulation")


def test_packaged_manifest_covers_only_approved_official_sources() -> None:
    manifest = load_manifest()

    assert manifest.schema_version == "1"
    assert manifest.manifest_version == "2026-07-23.1"
    assert {source.source_id for source in manifest.sources} == set(
        APPROVED_OFFICIAL_URLS
    )
    assert default_manifest_path().is_file()
    for source in manifest.sources:
        assert source.canonical_url == APPROVED_OFFICIAL_URLS[source.source_id]
        assert semantic_fingerprint(source.semantic_snapshot) == (
            source.semantic_fingerprint
        )


def test_manifest_rejects_arbitrary_url(tmp_path: Path) -> None:
    payload = json.loads(default_manifest_path().read_text(encoding="utf-8"))
    payload["sources"][0]["canonical_url"] = "https://example.invalid/rules"
    candidate = tmp_path / "unapproved.json"
    candidate.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="canonical URL is not approved"):
        load_manifest(candidate)


def test_semantically_equal_fixture_is_verified_despite_raw_hash_change() -> None:
    source = _current_manifest()
    content = (FIXTURES / "current-verified.html").read_bytes()

    result = audit_content(
        source,
        content,
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html; charset=utf-8",
    )

    assert result.status is RuleAuditStatus.VERIFIED_SNAPSHOT
    assert result.raw_sha256_actual != result.raw_sha256_expected
    assert result.semantic_fingerprint_actual == result.semantic_fingerprint_expected
    assert result.changed_fields == ()
    assert result.errors == ()
    assert result.writes_performed is False


def test_semantic_age_change_requires_review_with_field_level_diff() -> None:
    source = _current_manifest()
    content = (FIXTURES / "current-review-age-66.html").read_bytes()

    result = audit_content(
        source,
        content,
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )

    assert result.status is RuleAuditStatus.REVIEW_REQUIRED
    age_change = next(
        field
        for field in result.changed_fields
        if field.path == "eligibility.minimum_age"
    )
    assert age_change.expected == 65
    assert age_change.actual == 66
    assert "eligibility.CURRENT_2026_07" in age_change.impacted_rule_ids
    assert result.writes_performed is False


def test_missing_required_structure_requires_review() -> None:
    result = audit_content(
        _current_manifest(),
        b"<html><body>no regulation structure</body></html>",
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )

    assert result.status is RuleAuditStatus.REVIEW_REQUIRED
    assert result.changed_fields[0].path == "extractor.required_structure"
    assert result.semantic_fingerprint_actual is None


def test_fetch_unavailable_fixture_is_not_treated_as_verified() -> None:
    fixture = json.loads(
        (FIXTURES / "fetch-unavailable.json").read_text(encoding="utf-8")
    )
    result = unavailable_result(
        _current_manifest(),
        fetch_result=fixture["fetch_result"],
        error=fixture["error"],
        http_status=fixture["http_status"],
        checked_at="2026-07-23T00:00:00Z",
    )

    assert result.status is RuleAuditStatus.CHECK_UNAVAILABLE
    assert result.semantic_fingerprint_actual is None
    assert result.changed_fields == ()
    assert result.writes_performed is False


def test_unexpected_content_type_is_check_unavailable() -> None:
    result = audit_content(
        _current_manifest(),
        (FIXTURES / "current-verified.html").read_bytes(),
        checked_at="2026-07-23T00:00:00Z",
        content_type="application/pdf",
    )

    assert result.status is RuleAuditStatus.CHECK_UNAVAILABLE
    assert result.fetch_result == "unexpected_content_type"
    assert "Expected text/html" in result.errors[0]


def test_extractor_version_drift_requires_review() -> None:
    source = replace(_current_manifest(), extractor_version="future-v2")
    result = audit_content(
        source,
        (FIXTURES / "current-verified.html").read_bytes(),
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )

    assert result.status is RuleAuditStatus.REVIEW_REQUIRED
    assert "Extractor version differs" in result.errors[0]


def test_quota_text_fixture_reproduces_cms_2_to_8_amounts() -> None:
    result = extract_quota_numbers_from_text(
        (FIXTURES / "quota-table.txt").read_text(encoding="utf-8")
    )

    assert result["care_and_professional_monthly"] == {
        "2": 10_020,
        "3": 15_460,
        "4": 18_580,
        "5": 24_100,
        "6": 28_070,
        "7": 32_090,
        "8": 36_180,
    }


def test_copay_text_fixture_reproduces_official_matrix() -> None:
    result = extract_copay_numbers_from_text(
        (FIXTURES / "copay-table.txt").read_text(encoding="utf-8")
    )

    assert result["percentage_matrix"]["care_and_professional"] == [0, 5, 16]
    assert result["percentage_matrix"]["transport_region_2"] == [0, 9, 27]
    assert result["percentage_matrix"]["transport_region_4"] == [0, 7, 21]
    assert result["percentage_matrix"]["respite"] == [0, 5, 16]


@pytest.mark.parametrize(
    ("extractor", "text", "message"),
    [
        (extract_quota_numbers_from_text, "10,020 15,460", "expected 15 amounts"),
        (extract_copay_numbers_from_text, "0 5 16", "expected 21 percentages"),
    ],
)
def test_numeric_table_shape_change_requires_review(
    extractor,
    text: str,
    message: str,
) -> None:
    with pytest.raises(ExtractionReviewRequiredError, match=message):
        extractor(text)


def test_fixture_audits_never_modify_business_rule_files() -> None:
    before = {path: path.read_bytes() for path in RULE_FILES}

    audit_content(
        _current_manifest(),
        (FIXTURES / "current-verified.html").read_bytes(),
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )
    audit_content(
        _current_manifest(),
        (FIXTURES / "current-review-age-66.html").read_bytes(),
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )

    assert {path: path.read_bytes() for path in RULE_FILES} == before


def test_public_status_enum_contains_exactly_three_states() -> None:
    assert {status.value for status in RuleAuditStatus} == {
        "VERIFIED_SNAPSHOT",
        "REVIEW_REQUIRED",
        "CHECK_UNAVAILABLE",
    }


def _copy_consistency_inputs(destination: Path) -> None:
    for relative in (
        Path("README.md"),
        Path("tests/test_rule_audit.py"),
        Path("tests/fixtures/rule_audit/quota-table.txt"),
        Path("tests/fixtures/rule_audit/copay-table.txt"),
    ):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)


def test_project_consistency_matches_manifest_runtime_readme_and_tests() -> None:
    result = check_project_consistency(ROOT)

    assert result.status is ConsistencyStatus.CONSISTENT
    assert result.issues == ()
    assert result.writes_performed is False
    assert set(result.checked_targets) == {
        "manifest_vs_runtime_metadata",
        "manifest_vs_runtime_constants",
        "manifest_vs_readme",
        "manifest_vs_test_fixtures",
        "manifest_vs_test_assertions",
    }


def test_project_consistency_detects_readme_drift(tmp_path: Path) -> None:
    _copy_consistency_inputs(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace("10,020", "10,021", 1),
        encoding="utf-8",
    )

    result = check_project_consistency(tmp_path)

    assert result.status is ConsistencyStatus.DRIFT_DETECTED
    assert any(issue.path == "quota.amounts" for issue in result.issues)
    assert result.writes_performed is False


def test_project_consistency_detects_fixture_and_assertion_drift(
    tmp_path: Path,
) -> None:
    _copy_consistency_inputs(tmp_path)
    quota_fixture = tmp_path / "tests/fixtures/rule_audit/quota-table.txt"
    quota_fixture.write_text(
        quota_fixture.read_text(encoding="utf-8").replace("10,020", "10,021", 1),
        encoding="utf-8",
    )
    test_file = tmp_path / "tests/test_rule_audit.py"
    test_file.write_text(
        test_file.read_text(encoding="utf-8").replace(
            '"2": 10_020',
            '"2": 10_021',
            1,
        ),
        encoding="utf-8",
    )

    result = check_project_consistency(tmp_path)

    paths = {issue.path for issue in result.issues}
    assert "quota_fixture.care_and_professional_monthly" in paths
    assert "test_assertions.care_and_professional_monthly" in paths


def test_review_report_is_zh_tw_deterministic_and_lists_changed_fields() -> None:
    audit = audit_content(
        _current_manifest(),
        (FIXTURES / "current-review-age-66.html").read_bytes(),
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )

    report = render_review_report(
        (audit,),
        check_project_consistency(ROOT),
        manifest_version=load_manifest().manifest_version,
    )

    assert "# 長照規則來源人工複核報告" in report
    assert "不使用 LLM 判斷法規差異" in report
    assert "一般年齡門檻" in report
    assert "65" in report
    assert "66" in report
    assert "`eligibility.CURRENT_2026_07`" in report
    assert "重跑資格矩陣" in report
    assert "`writes_performed`：`false`" in report


def test_rejected_review_keeps_business_rules_unchanged() -> None:
    before = {path: path.read_bytes() for path in RULE_FILES}
    audit = audit_content(
        _current_manifest(),
        (FIXTURES / "current-review-age-66.html").read_bytes(),
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )

    report = render_review_report(
        (audit,),
        check_project_consistency(ROOT),
        manifest_version=load_manifest().manifest_version,
        decision=ReviewDecision.REJECTED,
        review_note="官方差異尚未取得作者核准。",
    )

    assert "作者已拒絕；現行核准快照保持不變" in report
    assert "保留現行核准快照與業務常數" in report
    assert {path: path.read_bytes() for path in RULE_FILES} == before


def test_audit_evidence_rejects_claimed_writes(tmp_path: Path) -> None:
    evidence = tmp_path / "unsafe.json"
    evidence.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "manifest_version": load_manifest().manifest_version,
                "writes_performed": True,
                "results": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="writes_performed=false"):
        load_audit_evidence(evidence)


def test_cli_renders_review_from_offline_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest = load_manifest()
    audit = audit_content(
        _current_manifest(),
        (FIXTURES / "current-verified.html").read_bytes(),
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "manifest_version": manifest.manifest_version,
                "writes_performed": False,
                "results": [audit.to_dict()],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report = tmp_path / "review.md"

    exit_code = audit_cli_main(
        [
            "--input",
            str(evidence),
            "--review-output",
            str(report),
            "--project-root",
            str(ROOT),
        ]
    )

    assert exit_code == 0
    report_text = report.read_text(encoding="utf-8")
    assert "# 長照規則來源人工複核報告" in report_text
    assert "差異欄位：無" in report_text
    assert "project_consistency: CONSISTENT" in capsys.readouterr().out
