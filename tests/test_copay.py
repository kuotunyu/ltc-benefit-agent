from __future__ import annotations

from dataclasses import FrozenInstanceError
from itertools import product

import pytest

from ltc_benefit_agent.tools.copay import (
    CalculationBasis,
    CopayInput,
    WelfareCategory,
    calculate_copay,
    get_quota_reference_table,
)
from ltc_benefit_agent.tools.rules import RuleVersion


QUOTAS = {2: 10_020, 3: 15_460, 4: 18_580, 5: 24_100, 6: 28_070, 7: 32_090, 8: 36_180}
PERCENTS = {
    WelfareCategory.FIRST: 0,
    WelfareCategory.SECOND: 5,
    WelfareCategory.THIRD: 16,
}


MATRIX_CASES = list(
    product(
        list(RuleVersion),
        range(2, 9),
        list(WelfareCategory),
        [False, True],
        ["zero", "below", "equal", "above"],
    )
)


@pytest.mark.parametrize(
    ("version", "cms", "category", "has_foreign_caregiver", "spend_case"),
    MATRIX_CASES,
)
def test_complete_copay_matrix(
    version: RuleVersion,
    cms: int,
    category: WelfareCategory,
    has_foreign_caregiver: bool,
    spend_case: str,
) -> None:
    base_quota = QUOTAS[cms]
    adjusted_quota = (
        base_quota * 30 // 100 if has_foreign_caregiver else base_quota
    )
    planned_spend = {
        "zero": 0,
        "below": max(adjusted_quota // 2, 1),
        "equal": adjusted_quota,
        "above": adjusted_quota + 1_234,
    }[spend_case]
    result = calculate_copay(
        CopayInput(
            cms_level=cms,
            welfare_category=category,
            has_foreign_caregiver=has_foreign_caregiver,
            planned_spend=planned_spend,
            rule_version=version,
        )
    )

    expected_eligible = min(planned_spend, adjusted_quota)
    expected_copay = expected_eligible * PERCENTS[category] // 100
    expected_overage = max(planned_spend - adjusted_quota, 0)
    assert result.base_quota == base_quota
    assert result.adjusted_quota == adjusted_quota
    assert result.eligible_spend == expected_eligible
    assert result.copay == expected_copay
    assert result.government_payment == expected_eligible - expected_copay
    assert result.overage == expected_overage
    assert result.total_out_of_pocket == expected_copay + expected_overage
    assert result.calculation_basis is CalculationBasis.PLANNED_SPEND
    assert all(
        isinstance(value, int)
        for value in (
            result.base_quota,
            result.adjusted_quota,
            result.eligible_spend,
            result.copay,
            result.government_payment,
            result.overage,
            result.total_out_of_pocket,
        )
    )


@pytest.mark.parametrize("version", list(RuleVersion))
@pytest.mark.parametrize("cms", range(2, 9))
def test_unknown_planned_spend_is_explicit_full_quota_example(
    version: RuleVersion, cms: int
) -> None:
    result = calculate_copay(
        CopayInput(
            cms_level=cms,
            welfare_category=WelfareCategory.THIRD,
            has_foreign_caregiver=False,
            planned_spend=None,
            rule_version=version,
        )
    )
    assert result.planned_spend is None
    assert result.calculation_basis is CalculationBasis.FULL_QUOTA_EXAMPLE
    assert result.calculation_spend == QUOTAS[cms]
    assert result.eligible_spend == QUOTAS[cms]


def test_copay_fraction_is_truncated_not_rounded() -> None:
    result = calculate_copay(
        CopayInput(
            cms_level=2,
            welfare_category=WelfareCategory.THIRD,
            has_foreign_caregiver=False,
            planned_spend=1_001,
        )
    )
    assert result.copay == 160


@pytest.mark.parametrize(
    ("category", "expected_label"),
    [
        (WelfareCategory.FIRST, "長照低收入戶"),
        (WelfareCategory.SECOND, "長照中低收入戶"),
        (WelfareCategory.THIRD, "長照一般戶"),
    ],
)
def test_legacy_welfare_labels(
    category: WelfareCategory, expected_label: str
) -> None:
    result = calculate_copay(
        CopayInput(2, category, False, 1_000, RuleVersion.LEGACY_2022)
    )
    assert result.welfare_label == expected_label


@pytest.mark.parametrize("category", list(WelfareCategory))
def test_current_welfare_labels_use_legal_category_names(
    category: WelfareCategory,
) -> None:
    result = calculate_copay(CopayInput(2, category, False, 1_000))
    assert result.welfare_label == {
        WelfareCategory.FIRST: "第一類",
        WelfareCategory.SECOND: "第二類",
        WelfareCategory.THIRD: "第三類",
    }[category]


@pytest.mark.parametrize("version", list(RuleVersion))
def test_quota_reference_table_has_all_levels(version: RuleVersion) -> None:
    rows = get_quota_reference_table(version)
    assert [row.cms_level for row in rows] == list(range(2, 9))
    assert [row.monthly_quota for row in rows] == list(QUOTAS.values())
    assert all(
        row.foreign_caregiver_adjusted_quota == row.monthly_quota * 30 // 100
        for row in rows
    )
    assert all(row.rule.version is version for row in rows)


@pytest.mark.parametrize("cms", [1, 9, -1])
def test_invalid_cms_is_rejected(cms: int) -> None:
    with pytest.raises(ValueError):
        calculate_copay(CopayInput(cms, WelfareCategory.FIRST, False, 0))


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"cms_level": True}, TypeError),
        ({"welfare_category": "FIRST"}, TypeError),
        ({"has_foreign_caregiver": 1}, TypeError),
        ({"planned_spend": -1}, ValueError),
        ({"planned_spend": 1.5}, TypeError),
        ({"planned_spend": True}, TypeError),
        ({"rule_version": "CURRENT_2026_07"}, TypeError),
    ],
)
def test_invalid_input_types_are_rejected(
    kwargs: dict[str, object], error: type[Exception]
) -> None:
    values: dict[str, object] = {
        "cms_level": 2,
        "welfare_category": WelfareCategory.FIRST,
        "has_foreign_caregiver": False,
        "planned_spend": 0,
        "rule_version": RuleVersion.CURRENT_2026_07,
    }
    values.update(kwargs)
    with pytest.raises(error):
        calculate_copay(CopayInput(**values))  # type: ignore[arg-type]


def test_result_is_immutable_and_has_disclaimer() -> None:
    result = calculate_copay(CopayInput(2, WelfareCategory.FIRST, False, 100))
    with pytest.raises(FrozenInstanceError):
        result.copay = 999  # type: ignore[misc]
    assert "照管中心" in result.disclaimer
