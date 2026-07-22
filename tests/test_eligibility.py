from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from ltc_benefit_agent.tools.eligibility import (
    EligibilityBasis,
    EligibilityInput,
    EligibilityStatus,
    ResidenceStatus,
    assess_eligibility,
)
from ltc_benefit_agent.tools.rules import RuleVersion


def make_input(**overrides: object) -> EligibilityInput:
    values: dict[str, object] = {
        "age": 70,
        "indigenous": False,
        "has_disability_certificate": False,
        "has_dementia_diagnosis": False,
        "is_pac_case": False,
        "has_functional_impairment": True,
        "impairment_duration_months": 6,
        "residence_status": ResidenceStatus.COMMUNITY,
        "official_cms_level": None,
        "rule_version": RuleVersion.CURRENT_2026_07,
    }
    values.update(overrides)
    return EligibilityInput(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "expected_status", "expected_basis"),
    [
        (
            {"age": 64},
            EligibilityStatus.PRELIMINARY_CRITERIA_NOT_MET,
            None,
        ),
        (
            {"age": 65},
            EligibilityStatus.POTENTIALLY_ELIGIBLE_TO_APPLY,
            EligibilityBasis.AGE_65_OR_OVER,
        ),
        (
            {"age": 54, "indigenous": True},
            EligibilityStatus.PRELIMINARY_CRITERIA_NOT_MET,
            None,
        ),
        (
            {"age": 55, "indigenous": True},
            EligibilityStatus.POTENTIALLY_ELIGIBLE_TO_APPLY,
            EligibilityBasis.INDIGENOUS_AGE_55_OR_OVER,
        ),
        (
            {"age": 20, "has_disability_certificate": True},
            EligibilityStatus.POTENTIALLY_ELIGIBLE_TO_APPLY,
            EligibilityBasis.DISABILITY_CERTIFICATE,
        ),
        (
            {"age": 49, "has_dementia_diagnosis": True},
            EligibilityStatus.POTENTIALLY_ELIGIBLE_TO_APPLY,
            EligibilityBasis.DEMENTIA,
        ),
        (
            {"age": 20, "is_pac_case": True},
            EligibilityStatus.POTENTIALLY_ELIGIBLE_TO_APPLY,
            EligibilityBasis.PAC_CASE,
        ),
    ],
)
def test_current_eligibility_boundaries(
    overrides: dict[str, object],
    expected_status: EligibilityStatus,
    expected_basis: EligibilityBasis | None,
) -> None:
    result = assess_eligibility(make_input(**overrides))
    assert result.status is expected_status
    if expected_basis is not None:
        assert expected_basis in result.qualifying_bases


@pytest.mark.parametrize(
    ("age", "expected_status"),
    [
        (49, EligibilityStatus.PRELIMINARY_CRITERIA_NOT_MET),
        (50, EligibilityStatus.POTENTIALLY_ELIGIBLE_TO_APPLY),
    ],
)
def test_legacy_dementia_age_boundary(
    age: int, expected_status: EligibilityStatus
) -> None:
    result = assess_eligibility(
        make_input(
            age=age,
            has_dementia_diagnosis=True,
            rule_version=RuleVersion.LEGACY_2022,
        )
    )
    assert result.status is expected_status


def test_legacy_does_not_treat_pac_as_a_basis() -> None:
    result = assess_eligibility(
        make_input(age=40, is_pac_case=True, rule_version=RuleVersion.LEGACY_2022)
    )
    assert result.status is EligibilityStatus.PRELIMINARY_CRITERIA_NOT_MET
    assert EligibilityBasis.PAC_CASE not in result.qualifying_bases


@pytest.mark.parametrize("version", list(RuleVersion))
def test_residential_institution_is_excluded(version: RuleVersion) -> None:
    result = assess_eligibility(
        make_input(
            rule_version=version,
            residence_status=ResidenceStatus.RESIDENTIAL_INSTITUTION,
        )
    )
    assert result.status is EligibilityStatus.PRELIMINARY_CRITERIA_NOT_MET


def test_group_home_is_excluded_in_both_snapshots() -> None:
    current = assess_eligibility(
        make_input(residence_status=ResidenceStatus.GROUP_HOME)
    )
    legacy = assess_eligibility(
        make_input(
            residence_status=ResidenceStatus.GROUP_HOME,
            rule_version=RuleVersion.LEGACY_2022,
        )
    )
    assert current.status is EligibilityStatus.PRELIMINARY_CRITERIA_NOT_MET
    assert legacy.status is EligibilityStatus.PRELIMINARY_CRITERIA_NOT_MET


@pytest.mark.parametrize("duration", [None, 0, 1, 5])
def test_current_pac_allows_short_term_need(duration: int | None) -> None:
    result = assess_eligibility(
        make_input(age=40, is_pac_case=True, impairment_duration_months=duration)
    )
    assert result.status is EligibilityStatus.POTENTIALLY_ELIGIBLE_TO_APPLY
    assert EligibilityBasis.PAC_CASE in result.qualifying_bases
    assert "impairment_duration_months" not in result.missing_fields


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {"has_functional_impairment": False},
            EligibilityStatus.PRELIMINARY_CRITERIA_NOT_MET,
        ),
        (
            {"impairment_duration_months": 5},
            EligibilityStatus.PRELIMINARY_CRITERIA_NOT_MET,
        ),
        (
            {"impairment_duration_months": 6},
            EligibilityStatus.POTENTIALLY_ELIGIBLE_TO_APPLY,
        ),
        (
            {"has_functional_impairment": None},
            EligibilityStatus.INSUFFICIENT_INFORMATION,
        ),
        (
            {"impairment_duration_months": None},
            EligibilityStatus.INSUFFICIENT_INFORMATION,
        ),
        (
            {"residence_status": ResidenceStatus.UNKNOWN},
            EligibilityStatus.INSUFFICIENT_INFORMATION,
        ),
    ],
)
def test_impairment_duration_and_missing_information(
    overrides: dict[str, object], expected_status: EligibilityStatus
) -> None:
    result = assess_eligibility(make_input(**overrides))
    assert result.status is expected_status


def test_only_decision_relevant_unknown_fields_are_requested() -> None:
    already_qualified = assess_eligibility(
        make_input(
            age=70,
            has_disability_certificate=None,
            has_dementia_diagnosis=None,
            is_pac_case=None,
        )
    )
    ambiguous = assess_eligibility(
        make_input(
            age=60,
            indigenous=None,
            has_disability_certificate=False,
            has_dementia_diagnosis=False,
            is_pac_case=False,
        )
    )
    assert already_qualified.status is EligibilityStatus.POTENTIALLY_ELIGIBLE_TO_APPLY
    assert already_qualified.missing_fields == ()
    assert ambiguous.status is EligibilityStatus.INSUFFICIENT_INFORMATION
    assert ambiguous.missing_fields == ("indigenous",)


def test_missing_age_is_not_required_when_disability_certificate_qualifies() -> None:
    result = assess_eligibility(
        make_input(age=None, has_disability_certificate=True)
    )
    assert result.status is EligibilityStatus.POTENTIALLY_ELIGIBLE_TO_APPLY
    assert "age" not in result.missing_fields


@pytest.mark.parametrize("cms_level", range(2, 9))
def test_official_cms_allows_estimate_without_reinferring_impairment(
    cms_level: int,
) -> None:
    result = assess_eligibility(
        make_input(
            official_cms_level=cms_level,
            has_functional_impairment=None,
            impairment_duration_months=None,
        )
    )
    assert result.status is EligibilityStatus.CMS_PROVIDED_FOR_ESTIMATE
    assert result.official_cms_level == cms_level


@pytest.mark.parametrize("cms_level", [1, 9, -2])
def test_invalid_cms_level_is_rejected(cms_level: int) -> None:
    with pytest.raises(ValueError):
        assess_eligibility(make_input(official_cms_level=cms_level))


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("age", -1, ValueError),
        ("age", True, TypeError),
        ("indigenous", "yes", TypeError),
        ("impairment_duration_months", -1, ValueError),
        ("impairment_duration_months", True, TypeError),
        ("official_cms_level", True, TypeError),
        ("residence_status", "COMMUNITY", TypeError),
        ("rule_version", "CURRENT_2026_07", TypeError),
    ],
)
def test_invalid_inputs_are_rejected(
    field: str, value: object, error: type[Exception]
) -> None:
    with pytest.raises(error):
        assess_eligibility(make_input(**{field: value}))


def test_input_and_result_are_immutable() -> None:
    data = make_input()
    result = assess_eligibility(data)
    with pytest.raises(FrozenInstanceError):
        data.age = 80  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.status = EligibilityStatus.PRELIMINARY_CRITERIA_NOT_MET  # type: ignore[misc]
    assert replace(data, age=80).age == 80


def test_result_always_includes_rule_and_disclaimer() -> None:
    result = assess_eligibility(make_input())
    assert result.rule.version is RuleVersion.CURRENT_2026_07
    assert result.rule.verified_on.isoformat() == "2026-07-22"
    assert "照管中心" in result.disclaimer
