from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

import ltc_benefit_agent.audit.checker as audit_checker_module
import ltc_benefit_agent.audit.cli as audit_cli_module
from ltc_benefit_agent.audit import (
    ConsistencyStatus,
    ReviewDecision,
    RuleAuditResult,
    RuleAuditStatus,
    RuleSourceManifest,
    audit_content,
    build_public_audit_summary,
    check_project_consistency,
    default_approved_status_path,
    load_audit_evidence,
    load_approved_audit_status,
    load_manifest,
    render_approved_audit_status_html,
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


def _result_for_source(
    template: RuleAuditResult,
    source: RuleSourceManifest,
) -> RuleAuditResult:
    return replace(
        template,
        source_id=source.source_id,
        title=source.title,
        canonical_url=source.canonical_url,
        rule_version=source.rule_version,
        effective_date=source.effective_date,
        raw_sha256_expected=source.raw_sha256,
        semantic_fingerprint_expected=source.semantic_fingerprint,
    )


def _complete_manifest_results(
    default: RuleAuditResult,
    *,
    overrides: dict[str, RuleAuditResult] | None = None,
) -> tuple[RuleAuditResult, ...]:
    replacements = overrides or {}
    return tuple(
        _result_for_source(replacements.get(source.source_id, default), source)
        for source in load_manifest().sources
    )


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


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload.__setitem__("unexpected", True),
            "unexpected fields",
        ),
        (
            lambda payload: payload["sources"][0].__setitem__(
                "unexpected", True
            ),
            "unexpected fields",
        ),
        (
            lambda payload: payload["sources"][0].__setitem__(
                "verified_at", "2026-07-22T00:00:00"
            ),
            "must include a timezone",
        ),
        (
            lambda payload: payload["sources"][0].__setitem__(
                "impacted_rule_ids", "eligibility.LEGACY_2022"
            ),
            "must be a list",
        ),
        (
            lambda payload: payload["sources"][0].__setitem__(
                "semantic_snapshot", []
            ),
            "must be an object",
        ),
    ],
)
def test_manifest_rejects_ambiguous_or_unexpected_schema(
    tmp_path: Path,
    mutate,
    message: str,
) -> None:
    payload = json.loads(default_manifest_path().read_text(encoding="utf-8"))
    mutate(payload)
    candidate = tmp_path / "invalid-manifest.json"
    candidate.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
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


def test_audit_rejects_ambiguous_timestamp_without_timezone() -> None:
    with pytest.raises(ValueError, match="must include a timezone"):
        audit_content(
            _current_manifest(),
            (FIXTURES / "current-verified.html").read_bytes(),
            checked_at="2026-07-23T00:00:00",
            content_type="text/html",
        )


def test_online_audit_rejects_non_200_success_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _current_manifest()

    class FakeResponse:
        status = 204
        headers = {"Content-Type": "text/html"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def geturl(self) -> str:
            return source.canonical_url

        def read(self, _limit: int) -> bytes:
            return b""

    monkeypatch.setattr(
        audit_checker_module,
        "urlopen",
        lambda _request, *, timeout: FakeResponse(),
    )

    result = audit_checker_module.audit_online(
        source,
        checked_at="2026-07-23T00:00:00+08:00",
    )

    assert result.status is RuleAuditStatus.CHECK_UNAVAILABLE
    assert result.fetch_result == "unexpected_http_status"
    assert result.http_status == 204
    assert result.checked_at == "2026-07-22T16:00:00Z"


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_online_audit_rejects_invalid_timeout(timeout: float) -> None:
    with pytest.raises(ValueError, match="finite and greater than zero"):
        audit_checker_module.audit_online(
            _current_manifest(),
            timeout_seconds=timeout,
        )


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


def test_public_summary_uses_only_whitelisted_minimized_fields() -> None:
    verified = audit_content(
        _current_manifest(),
        (FIXTURES / "current-verified.html").read_bytes(),
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )
    review = audit_content(
        _current_manifest(),
        (FIXTURES / "current-review-age-66.html").read_bytes(),
        checked_at="2026-07-23T00:01:00Z",
        content_type="text/html",
    )
    unavailable = unavailable_result(
        _current_manifest(),
        fetch_result="network_error",
        error="private diagnostic must not be published",
        checked_at="2026-07-23T00:02:00Z",
    )
    results = (
        replace(verified, source_id="verified"),
        replace(review, source_id="review"),
        replace(unavailable, source_id="unavailable"),
    )

    summary = build_public_audit_summary(
        results,
        manifest_version=load_manifest().manifest_version,
        expected_source_ids=tuple(result.source_id for result in results),
    )

    assert set(summary) == {
        "schema_version",
        "manifest_version",
        "generated_at",
        "overall_status",
        "source_count",
        "status_counts",
        "writes_performed",
        "results",
    }
    assert summary["overall_status"] == "CHECK_UNAVAILABLE"
    assert summary["source_count"] == 3
    assert summary["generated_at"] == "2026-07-23T00:02:00Z"
    assert summary["writes_performed"] is False
    assert summary["status_counts"] == {
        "VERIFIED_SNAPSHOT": 1,
        "REVIEW_REQUIRED": 1,
        "CHECK_UNAVAILABLE": 1,
    }
    assert [result["source_id"] for result in summary["results"]] == [
        "review",
        "unavailable",
        "verified",
    ]
    serialized = json.dumps(summary, ensure_ascii=False)
    result_keys = set().union(
        *(result.keys() for result in summary["results"])
    )
    assert result_keys == {
        "source_id",
        "title",
        "rule_version",
        "effective_date",
        "checked_at",
        "status",
        "http_status",
        "changed_field_count",
        "has_errors",
        "writes_performed",
    }
    for private_field in (
        "canonical_url",
        "fetch_result",
        "raw_sha256",
        "semantic_fingerprint",
        "changed_fields",
        "errors",
    ):
        assert private_field not in result_keys
    assert "private diagnostic" not in serialized
    assert summary["results"][0]["changed_field_count"] == 1
    assert summary["results"][1]["has_errors"] is True


def test_public_summary_orders_timezone_aware_timestamps_chronologically() -> None:
    result = audit_content(
        _current_manifest(),
        (FIXTURES / "current-verified.html").read_bytes(),
        checked_at="2026-07-23T01:00:00+02:00",
        content_type="text/html",
    )
    later = replace(
        result,
        source_id="later",
        checked_at="2026-07-23T00:30:00Z",
    )

    summary = build_public_audit_summary(
        (result, later),
        manifest_version=load_manifest().manifest_version,
        expected_source_ids=(result.source_id, later.source_id),
    )

    assert summary["generated_at"] == "2026-07-23T00:30:00Z"
    checked_at_by_source = {
        row["source_id"]: row["checked_at"] for row in summary["results"]
    }
    assert checked_at_by_source[result.source_id] == "2026-07-22T23:00:00Z"
    assert checked_at_by_source[later.source_id] == "2026-07-23T00:30:00Z"


def test_public_summary_rejects_timestamp_without_timezone() -> None:
    result = audit_content(
        _current_manifest(),
        (FIXTURES / "current-verified.html").read_bytes(),
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )
    result = replace(result, checked_at="2026-07-23T00:00:00")

    with pytest.raises(ValueError, match="must include a timezone"):
        build_public_audit_summary(
            (result,),
            manifest_version=load_manifest().manifest_version,
            expected_source_ids=(result.source_id,),
        )


def test_public_summary_rejects_empty_result_set() -> None:
    with pytest.raises(ValueError, match="at least one result"):
        build_public_audit_summary(
            (),
            manifest_version=load_manifest().manifest_version,
            expected_source_ids=tuple(
                source.source_id for source in load_manifest().sources
            ),
        )


def test_public_summary_requires_explicit_manifest_identity() -> None:
    result = audit_content(
        _current_manifest(),
        (FIXTURES / "current-verified.html").read_bytes(),
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )

    with pytest.raises(ValueError, match="manifest_version is required"):
        build_public_audit_summary(
            (result,),
            manifest_version="",
            expected_source_ids=(result.source_id,),
        )
    with pytest.raises(ValueError, match="sequence of strings"):
        build_public_audit_summary(
            (result,),
            manifest_version=load_manifest().manifest_version,
            expected_source_ids=result.source_id,
        )


def test_public_summary_rejects_duplicate_source_ids() -> None:
    result = audit_content(
        _current_manifest(),
        (FIXTURES / "current-verified.html").read_bytes(),
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )

    with pytest.raises(ValueError, match="source_id values must be unique"):
        build_public_audit_summary(
            (result, result),
            manifest_version=load_manifest().manifest_version,
            expected_source_ids=(result.source_id,),
        )


def test_public_summary_requires_complete_manifest_coverage() -> None:
    result = audit_content(
        _current_manifest(),
        (FIXTURES / "current-verified.html").read_bytes(),
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )
    manifest = load_manifest()

    with pytest.raises(ValueError, match="exactly cover the manifest sources"):
        build_public_audit_summary(
            (result,),
            manifest_version=manifest.manifest_version,
            expected_source_ids=tuple(
                source.source_id for source in manifest.sources
            ),
        )


def test_packaged_approved_status_matches_manifest_and_renders_static_ui() -> None:
    status = load_approved_audit_status()
    rendered = render_approved_audit_status_html(status)

    assert default_approved_status_path().is_file()
    assert status.manifest_version == load_manifest().manifest_version
    assert status.last_successful_audit_date.isoformat() == "2026-07-23"
    assert status.source_count == status.verified_source_count == 4
    assert status.writes_performed is False
    assert "法規快照 2026-07-23.1 已核准" in rendered
    assert "最後成功稽核：2026-07-23 · 4/4 官方來源一致" in rendered
    assert "對話期間不即時抓取法規" in rendered


def test_approved_status_rejects_stale_manifest_version(tmp_path: Path) -> None:
    payload = json.loads(
        default_approved_status_path().read_text(encoding="utf-8")
    )
    payload["manifest_version"] = "stale"
    candidate = tmp_path / "approved-status.json"
    candidate.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="manifest_version is stale"):
        load_approved_audit_status(candidate)


def test_approved_status_rejects_non_boolean_write_flag(tmp_path: Path) -> None:
    payload = json.loads(
        default_approved_status_path().read_text(encoding="utf-8")
    )
    payload["writes_performed"] = "false"
    candidate = tmp_path / "approved-status.json"
    candidate.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="writes_performed must be boolean"):
        load_approved_audit_status(candidate)


@pytest.mark.parametrize("invalid_count", [True, 0, "4"])
def test_approved_status_rejects_non_positive_integer_counts(
    tmp_path: Path,
    invalid_count,
) -> None:
    payload = json.loads(
        default_approved_status_path().read_text(encoding="utf-8")
    )
    payload["source_count"] = invalid_count
    candidate = tmp_path / "approved-status.json"
    candidate.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must be a positive integer"):
        load_approved_audit_status(candidate)


def test_approved_status_rejects_unexpected_fields(tmp_path: Path) -> None:
    payload = json.loads(
        default_approved_status_path().read_text(encoding="utf-8")
    )
    payload["private_note"] = "must not be silently accepted"
    candidate = tmp_path / "approved-status.json"
    candidate.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unexpected fields"):
        load_approved_audit_status(candidate)


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
    audits = _complete_manifest_results(audit)
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "manifest_version": manifest.manifest_version,
                "writes_performed": False,
                "results": [result.to_dict() for result in audits],
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
            "--quiet",
        ]
    )

    assert exit_code == 0
    report_text = report.read_text(encoding="utf-8")
    assert "# 長照規則來源人工複核報告" in report_text
    assert "差異欄位：無" in report_text
    captured = capsys.readouterr().out
    assert all(
        f"{result.source_id}: VERIFIED_SNAPSHOT" in captured
        for result in audits
    )
    assert "project_consistency: CONSISTENT" in captured
    assert "canonical_url" not in captured
    assert "raw_sha256" not in captured
    assert "semantic_fingerprint" not in captured
    assert "changed_fields" not in captured
    assert "errors" not in captured


def test_cli_writes_public_summary_before_review_required_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = audit_content(
        _current_manifest(),
        (FIXTURES / "current-review-age-66.html").read_bytes(),
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )
    verified = audit_content(
        _current_manifest(),
        (FIXTURES / "current-verified.html").read_bytes(),
        checked_at="2026-07-23T00:00:00Z",
        content_type="text/html",
    )
    audits = _complete_manifest_results(
        verified,
        overrides={audit.source_id: audit},
    )
    results_by_source = {result.source_id: result for result in audits}
    monkeypatch.setattr(
        audit_cli_module,
        "audit_online",
        lambda source, *, timeout_seconds: results_by_source[source.source_id],
    )
    public_output = tmp_path / "public-summary.json"

    exit_code = audit_cli_main(
        [
            "--public-output",
            str(public_output),
            "--quiet",
        ]
    )

    assert exit_code == 2
    payload = json.loads(public_output.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "REVIEW_REQUIRED"
    changed = {
        result["source_id"]: result["changed_field_count"]
        for result in payload["results"]
    }
    assert changed[audit.source_id] == 1
    assert payload["source_count"] == len(load_manifest().sources)


def test_cli_rejects_archived_input_public_summary_before_file_read(
    tmp_path: Path,
) -> None:
    public_output = tmp_path / "public-summary.json"

    with pytest.raises(SystemExit) as error:
        audit_cli_main(
            [
                "--input",
                str(tmp_path / "does-not-exist.json"),
                "--public-output",
                str(public_output),
            ]
        )

    assert error.value.code == 2
    assert not public_output.exists()


def test_cli_rejects_partial_source_public_summary_before_network(
    tmp_path: Path,
) -> None:
    public_output = tmp_path / "public-summary.json"

    with pytest.raises(SystemExit) as error:
        audit_cli_main(
            [
                "--source",
                _current_manifest().source_id,
                "--public-output",
                str(public_output),
            ]
        )

    assert error.value.code == 2
    assert not public_output.exists()


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf"])
def test_cli_rejects_invalid_timeout_before_network(timeout: str) -> None:
    with pytest.raises(SystemExit) as error:
        audit_cli_main(["--timeout", timeout, "--quiet"])

    assert error.value.code == 2


def test_cli_rejects_colliding_output_paths_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "same.json"
    monkeypatch.setattr(
        audit_cli_module,
        "audit_online",
        lambda *args, **kwargs: pytest.fail("network path must not run"),
    )

    with pytest.raises(SystemExit) as error:
        audit_cli_main(
            [
                "--output",
                str(output),
                "--public-output",
                str(output),
                "--quiet",
            ]
        )

    assert error.value.code == 2
    assert not output.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows path aliases are case-insensitive")
def test_cli_rejects_case_alias_output_paths_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "evidence.json"
    alias = tmp_path / "EVIDENCE.JSON"
    monkeypatch.setattr(
        audit_cli_module,
        "audit_online",
        lambda *args, **kwargs: pytest.fail("network path must not run"),
    )

    with pytest.raises(SystemExit) as error:
        audit_cli_main(
            [
                "--output",
                str(output),
                "--public-output",
                str(alias),
                "--quiet",
            ]
        )

    assert error.value.code == 2
    assert not output.exists()
    assert not alias.exists()


def test_cli_rejects_hard_link_output_alias_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "evidence.json"
    alias = tmp_path / "public.json"
    output.write_text("unchanged", encoding="utf-8")
    try:
        os.link(output, alias)
    except OSError as exc:
        pytest.skip(f"hard links unavailable: {exc}")
    monkeypatch.setattr(
        audit_cli_module,
        "audit_online",
        lambda *args, **kwargs: pytest.fail("network path must not run"),
    )

    with pytest.raises(SystemExit) as error:
        audit_cli_main(
            [
                "--output",
                str(output),
                "--public-output",
                str(alias),
                "--quiet",
            ]
        )

    assert error.value.code == 2
    assert output.read_text(encoding="utf-8") == "unchanged"
    assert alias.read_text(encoding="utf-8") == "unchanged"


def test_cli_rejects_output_that_matches_archived_input_before_file_read(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "not-created.json"

    with pytest.raises(SystemExit) as error:
        audit_cli_main(
            [
                "--input",
                str(evidence),
                "--output",
                str(evidence),
                "--quiet",
            ]
        )

    assert error.value.code == 2
    assert not evidence.exists()


def test_cli_rejects_hard_link_manifest_alias_before_file_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = tmp_path / "manifest.json"
    alias = tmp_path / "evidence.json"
    shutil.copyfile(default_manifest_path(), manifest)
    try:
        os.link(manifest, alias)
    except OSError as exc:
        pytest.skip(f"hard links unavailable: {exc}")
    before = manifest.read_bytes()
    monkeypatch.setattr(
        audit_cli_module,
        "load_manifest",
        lambda *args, **kwargs: pytest.fail("manifest must not be read"),
    )

    with pytest.raises(SystemExit) as error:
        audit_cli_main(
            [
                "--manifest",
                str(manifest),
                "--output",
                str(alias),
                "--quiet",
            ]
        )

    assert error.value.code == 2
    assert manifest.read_bytes() == before
    assert alias.read_bytes() == before


def test_cli_rejects_env_output_before_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / ".env"
    monkeypatch.setattr(
        audit_cli_module,
        "audit_online",
        lambda *args, **kwargs: pytest.fail("network path must not run"),
    )

    with pytest.raises(SystemExit) as error:
        audit_cli_main(["--output", str(output), "--quiet"])

    assert error.value.code == 2
    assert not output.exists()


@pytest.mark.parametrize(
    "protected_path",
    [
        default_manifest_path(),
        default_approved_status_path(),
        *RULE_FILES,
    ],
)
def test_cli_rejects_protected_output_before_network(
    protected_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = protected_path.read_bytes()
    monkeypatch.setattr(
        audit_cli_module,
        "audit_online",
        lambda *args, **kwargs: pytest.fail("network path must not run"),
    )

    with pytest.raises(SystemExit) as error:
        audit_cli_main(["--output", str(protected_path), "--quiet"])

    assert error.value.code == 2
    assert protected_path.read_bytes() == before
