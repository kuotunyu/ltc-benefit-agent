"""長照服務申請資格的保守初篩。

本模組不做正式資格核定，也不從生活描述推定 CMS。只要缺少會影響結論的
資料，就回傳 INSUFFICIENT_INFORMATION。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .rules import MIN_LONG_TERM_MONTHS, RuleSnapshot, RuleVersion, get_rule_snapshot


class ResidenceStatus(StrEnum):
    COMMUNITY = "COMMUNITY"
    RESIDENTIAL_INSTITUTION = "RESIDENTIAL_INSTITUTION"
    GROUP_HOME = "GROUP_HOME"
    UNKNOWN = "UNKNOWN"


class EligibilityStatus(StrEnum):
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    POTENTIALLY_ELIGIBLE_TO_APPLY = "POTENTIALLY_ELIGIBLE_TO_APPLY"
    PRELIMINARY_CRITERIA_NOT_MET = "PRELIMINARY_CRITERIA_NOT_MET"
    CMS_PROVIDED_FOR_ESTIMATE = "CMS_PROVIDED_FOR_ESTIMATE"


class EligibilityBasis(StrEnum):
    AGE_65_OR_OVER = "AGE_65_OR_OVER"
    INDIGENOUS_AGE_55_OR_OVER = "INDIGENOUS_AGE_55_OR_OVER"
    DISABILITY_CERTIFICATE = "DISABILITY_CERTIFICATE"
    DEMENTIA = "DEMENTIA"
    PAC_CASE = "PAC_CASE"


@dataclass(frozen=True, slots=True)
class EligibilityInput:
    age: int | None
    indigenous: bool | None
    has_disability_certificate: bool | None
    has_dementia_diagnosis: bool | None
    is_pac_case: bool | None
    has_functional_impairment: bool | None
    impairment_duration_months: int | None
    residence_status: ResidenceStatus
    official_cms_level: int | None = None
    rule_version: RuleVersion = RuleVersion.CURRENT_2026_07


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    status: EligibilityStatus
    rule: RuleSnapshot
    qualifying_bases: tuple[EligibilityBasis, ...]
    missing_fields: tuple[str, ...]
    reasons: tuple[str, ...]
    official_cms_level: int | None
    disclaimer: str = (
        "僅供申請資格初篩；正式資格、CMS 等級與給付額度以照管中心核定為準。"
    )


def _validate_optional_bool(value: bool | None, field_name: str) -> None:
    if value is not None and not isinstance(value, bool):
        raise TypeError(f"{field_name} 必須是 bool 或 None")


def _validate_input(data: EligibilityInput) -> None:
    if not isinstance(data, EligibilityInput):
        raise TypeError("data 必須是 EligibilityInput")
    if not isinstance(data.rule_version, RuleVersion):
        raise TypeError("rule_version 必須是 RuleVersion")
    if data.age is not None:
        if isinstance(data.age, bool) or not isinstance(data.age, int):
            raise TypeError("age 必須是整數或 None")
        if data.age < 0:
            raise ValueError("age 不得為負數")
    for field_name in (
        "indigenous",
        "has_disability_certificate",
        "has_dementia_diagnosis",
        "is_pac_case",
        "has_functional_impairment",
    ):
        _validate_optional_bool(getattr(data, field_name), field_name)
    if data.impairment_duration_months is not None:
        if isinstance(data.impairment_duration_months, bool) or not isinstance(
            data.impairment_duration_months, int
        ):
            raise TypeError("impairment_duration_months 必須是整數或 None")
        if data.impairment_duration_months < 0:
            raise ValueError("impairment_duration_months 不得為負數")
    if not isinstance(data.residence_status, ResidenceStatus):
        raise TypeError("residence_status 必須是 ResidenceStatus")
    if data.official_cms_level is not None:
        if isinstance(data.official_cms_level, bool) or not isinstance(
            data.official_cms_level, int
        ):
            raise TypeError("official_cms_level 必須是整數或 None")
        if data.official_cms_level not in range(2, 9):
            raise ValueError("正式 CMS 等級只接受 2 至 8")


def _result(
    data: EligibilityInput,
    status: EligibilityStatus,
    *,
    bases: tuple[EligibilityBasis, ...] = (),
    missing: tuple[str, ...] = (),
    reasons: tuple[str, ...],
) -> EligibilityResult:
    return EligibilityResult(
        status=status,
        rule=get_rule_snapshot(data.rule_version),
        qualifying_bases=bases,
        missing_fields=missing,
        reasons=reasons,
        official_cms_level=data.official_cms_level,
    )


def _qualifying_bases(data: EligibilityInput) -> tuple[EligibilityBasis, ...]:
    bases: list[EligibilityBasis] = []
    if data.age is not None:
        if data.age >= 65:
            bases.append(EligibilityBasis.AGE_65_OR_OVER)
        elif data.age >= 55 and data.indigenous is True:
            bases.append(EligibilityBasis.INDIGENOUS_AGE_55_OR_OVER)
    if data.has_disability_certificate is True:
        bases.append(EligibilityBasis.DISABILITY_CERTIFICATE)
    if data.has_dementia_diagnosis is True:
        if data.rule_version is RuleVersion.CURRENT_2026_07:
            bases.append(EligibilityBasis.DEMENTIA)
        elif data.age is not None and data.age >= 50:
            bases.append(EligibilityBasis.DEMENTIA)
    if (
        data.rule_version is RuleVersion.CURRENT_2026_07
        and data.is_pac_case is True
    ):
        bases.append(EligibilityBasis.PAC_CASE)
    return tuple(bases)


def _unknown_basis_fields(data: EligibilityInput) -> tuple[str, ...]:
    missing: list[str] = []
    if data.age is None:
        missing.append("age")
    elif 55 <= data.age < 65 and data.indigenous is None:
        missing.append("indigenous")
    if data.has_disability_certificate is None:
        missing.append("has_disability_certificate")
    if data.has_dementia_diagnosis is None:
        missing.append("has_dementia_diagnosis")
    if (
        data.rule_version is RuleVersion.CURRENT_2026_07
        and data.is_pac_case is None
    ):
        missing.append("is_pac_case")
    return tuple(dict.fromkeys(missing))


def assess_eligibility(data: EligibilityInput) -> EligibilityResult:
    """依指定快照做保守初篩；不進行 CMS 推估。"""

    _validate_input(data)

    # 現制第 2 條明文排除團體家屋；修法對照表說明在明文化以前，主管機關
    # 已以 2020 年函釋認定團體家屋不列為本辦法給付對象。
    excluded_residences = {
        ResidenceStatus.RESIDENTIAL_INSTITUTION,
        ResidenceStatus.GROUP_HOME,
    }
    if data.residence_status in excluded_residences:
        return _result(
            data,
            EligibilityStatus.PRELIMINARY_CRITERIA_NOT_MET,
            reasons=("指定規則快照將目前住宿狀態排除於本辦法給付範圍。",),
        )

    is_current_pac = (
        data.rule_version is RuleVersion.CURRENT_2026_07
        and data.is_pac_case is True
    )
    if data.official_cms_level is None:
        if data.has_functional_impairment is False:
            return _result(
                data,
                EligibilityStatus.PRELIMINARY_CRITERIA_NOT_MET,
                reasons=("輸入顯示目前沒有需他人協助的身心失能。",),
            )
        if (
            not is_current_pac
            and data.impairment_duration_months is not None
            and data.impairment_duration_months < MIN_LONG_TERM_MONTHS
        ):
            return _result(
                data,
                EligibilityStatus.PRELIMINARY_CRITERIA_NOT_MET,
                reasons=("失能已達或預期期間未滿六個月，不符合長照定義。",),
            )

    bases = _qualifying_bases(data)
    missing: list[str] = []
    if data.residence_status is ResidenceStatus.UNKNOWN:
        missing.append("residence_status")
    if data.official_cms_level is None:
        if data.has_functional_impairment is None:
            missing.append("has_functional_impairment")
        if data.impairment_duration_months is None and not is_current_pac:
            missing.append("impairment_duration_months")
    if not bases:
        missing.extend(_unknown_basis_fields(data))

    if missing:
        return _result(
            data,
            EligibilityStatus.INSUFFICIENT_INFORMATION,
            bases=bases,
            missing=tuple(dict.fromkeys(missing)),
            reasons=("仍缺少會影響資格初篩的必要資訊。",),
        )

    if not bases:
        return _result(
            data,
            EligibilityStatus.PRELIMINARY_CRITERIA_NOT_MET,
            reasons=("未符合此規則快照列出的年齡或身分類別。",),
        )

    if data.official_cms_level is not None:
        return _result(
            data,
            EligibilityStatus.CMS_PROVIDED_FOR_ESTIMATE,
            bases=bases,
            reasons=(
                "使用者已提供正式 CMS 2 至 8 級，可進入照顧及專業服務參考試算。",
            ),
        )

    return _result(
        data,
        EligibilityStatus.POTENTIALLY_ELIGIBLE_TO_APPLY,
        bases=bases,
        reasons=("符合申請身分與長照期間的保守初篩，仍須照管中心正式評估。",),
    )
