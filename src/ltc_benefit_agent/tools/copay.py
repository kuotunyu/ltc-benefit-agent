"""照顧及專業服務月額與部分負擔的整數試算。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .rules import (
    CARE_AND_PROFESSIONAL_QUOTAS,
    COPAY_PERCENTAGES,
    FOREIGN_CAREGIVER_QUOTA_PERCENT,
    RuleSnapshot,
    RuleVersion,
    get_rule_snapshot,
)


class WelfareCategory(StrEnum):
    FIRST = "FIRST"
    SECOND = "SECOND"
    THIRD = "THIRD"


class CalculationBasis(StrEnum):
    PLANNED_SPEND = "PLANNED_SPEND"
    FULL_QUOTA_EXAMPLE = "FULL_QUOTA_EXAMPLE"


_WELFARE_LABELS = {
    RuleVersion.LEGACY_2022: {
        WelfareCategory.FIRST: "長照低收入戶",
        WelfareCategory.SECOND: "長照中低收入戶",
        WelfareCategory.THIRD: "長照一般戶",
    },
    RuleVersion.CURRENT_2026_07: {
        WelfareCategory.FIRST: "第一類",
        WelfareCategory.SECOND: "第二類",
        WelfareCategory.THIRD: "第三類",
    },
}


@dataclass(frozen=True, slots=True)
class CopayInput:
    cms_level: int
    welfare_category: WelfareCategory
    has_foreign_caregiver: bool
    planned_spend: int | None = None
    rule_version: RuleVersion = RuleVersion.CURRENT_2026_07


@dataclass(frozen=True, slots=True)
class CopayResult:
    rule: RuleSnapshot
    cms_level: int
    welfare_category: WelfareCategory
    welfare_label: str
    copay_percent: int
    has_foreign_caregiver: bool
    base_quota: int
    adjusted_quota: int
    planned_spend: int | None
    calculation_basis: CalculationBasis
    calculation_spend: int
    eligible_spend: int
    copay: int
    government_payment: int
    overage: int
    total_out_of_pocket: int
    disclaimer: str = (
        "僅試算照顧及專業服務；實際額度、服務組合與費用以照管中心核定為準。"
    )


@dataclass(frozen=True, slots=True)
class QuotaReferenceRow:
    rule: RuleSnapshot
    cms_level: int
    monthly_quota: int
    foreign_caregiver_adjusted_quota: int


def _validate_input(data: CopayInput) -> None:
    if not isinstance(data, CopayInput):
        raise TypeError("data 必須是 CopayInput")
    if isinstance(data.cms_level, bool) or not isinstance(data.cms_level, int):
        raise TypeError("cms_level 必須是整數")
    if data.cms_level not in range(2, 9):
        raise ValueError("CMS 等級只接受 2 至 8")
    if not isinstance(data.welfare_category, WelfareCategory):
        raise TypeError("welfare_category 必須是 WelfareCategory")
    if not isinstance(data.has_foreign_caregiver, bool):
        raise TypeError("has_foreign_caregiver 必須是 bool")
    if data.planned_spend is not None:
        if isinstance(data.planned_spend, bool) or not isinstance(data.planned_spend, int):
            raise TypeError("planned_spend 必須是整數或 None")
        if data.planned_spend < 0:
            raise ValueError("planned_spend 不得為負數")
    if not isinstance(data.rule_version, RuleVersion):
        raise TypeError("rule_version 必須是 RuleVersion")


def _adjust_quota(base_quota: int, has_foreign_caregiver: bool) -> int:
    if not has_foreign_caregiver:
        return base_quota
    return base_quota * FOREIGN_CAREGIVER_QUOTA_PERCENT // 100


def calculate_copay(data: CopayInput) -> CopayResult:
    """只用整數運算計算額度、部分負擔、政府給付與超額。"""

    _validate_input(data)
    base_quota = CARE_AND_PROFESSIONAL_QUOTAS[data.rule_version][data.cms_level]
    adjusted_quota = _adjust_quota(base_quota, data.has_foreign_caregiver)
    calculation_basis = (
        CalculationBasis.FULL_QUOTA_EXAMPLE
        if data.planned_spend is None
        else CalculationBasis.PLANNED_SPEND
    )
    calculation_spend = (
        adjusted_quota if data.planned_spend is None else data.planned_spend
    )
    eligible_spend = min(calculation_spend, adjusted_quota)
    copay_percent = COPAY_PERCENTAGES[data.welfare_category.value]
    copay = eligible_spend * copay_percent // 100
    government_payment = eligible_spend - copay
    overage = max(calculation_spend - adjusted_quota, 0)

    return CopayResult(
        rule=get_rule_snapshot(data.rule_version),
        cms_level=data.cms_level,
        welfare_category=data.welfare_category,
        welfare_label=_WELFARE_LABELS[data.rule_version][data.welfare_category],
        copay_percent=copay_percent,
        has_foreign_caregiver=data.has_foreign_caregiver,
        base_quota=base_quota,
        adjusted_quota=adjusted_quota,
        planned_spend=data.planned_spend,
        calculation_basis=calculation_basis,
        calculation_spend=calculation_spend,
        eligible_spend=eligible_spend,
        copay=copay,
        government_payment=government_payment,
        overage=overage,
        total_out_of_pocket=copay + overage,
    )


def get_quota_reference_table(
    rule_version: RuleVersion = RuleVersion.CURRENT_2026_07,
) -> tuple[QuotaReferenceRow, ...]:
    """CMS 未知時使用的 2 至 8 級參考表，不替個人推定等級。"""

    rule = get_rule_snapshot(rule_version)
    return tuple(
        QuotaReferenceRow(
            rule=rule,
            cms_level=cms_level,
            monthly_quota=quota,
            foreign_caregiver_adjusted_quota=_adjust_quota(quota, True),
        )
        for cms_level, quota in CARE_AND_PROFESSIONAL_QUOTAS[rule_version].items()
    )
