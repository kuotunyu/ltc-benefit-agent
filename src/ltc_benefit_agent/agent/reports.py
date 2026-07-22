"""最終 Markdown 建議書的確定性 renderer 與不可竄改 registry。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from threading import Lock

from ltc_benefit_agent.tools.copay import (
    CopayInput,
    CopayResult,
    WelfareCategory,
    calculate_copay,
    get_quota_reference_table,
)
from ltc_benefit_agent.tools.eligibility import (
    EligibilityInput,
    EligibilityResult,
    assess_eligibility,
)
from ltc_benefit_agent.tools.faq_search import FaqSearchResult
from ltc_benefit_agent.tools.rules import APPLICATION_GUIDE_URL, RuleVersion


@dataclass(frozen=True, slots=True)
class ReportDraft:
    report_id: str
    markdown: str


class ReportPublicationRejected(ValueError):
    """確定性 registry 拒絕未知或遭竄改的報告發布要求。"""


class ReportRegistry:
    def __init__(self) -> None:
        self._reports: dict[str, str] = {}
        self._lock = Lock()

    def register(self, markdown: str) -> ReportDraft:
        report_id = hashlib.sha256(markdown.encode("utf-8")).hexdigest()[:20]
        with self._lock:
            self._reports[report_id] = markdown
        return ReportDraft(report_id=report_id, markdown=markdown)

    def verify_and_publish(self, report_id: str, report_markdown: str) -> str:
        with self._lock:
            expected = self._reports.get(report_id)
        if expected is None:
            raise ReportPublicationRejected("未知的 report_id；請先建立報告草稿")
        if report_markdown != expected:
            raise ReportPublicationRejected(
                "報告內容與確定性草稿不一致，拒絕發布"
            )
        return expected


def _money(value: int) -> str:
    return f"NT$ {value:,}"


def _eligibility_section(result: EligibilityResult) -> list[str]:
    bases = "、".join(basis.value for basis in result.qualifying_bases) or "無"
    reasons = "；".join(result.reasons)
    return [
        "## 資格初篩",
        "",
        f"- 結論：`{result.status.value}`",
        f"- 符合身分依據：{bases}",
        f"- 說明：{reasons}",
    ]


def _copay_section(result: CopayResult) -> list[str]:
    basis_note = (
        "依使用者提供的預計服務費"
        if result.planned_spend is not None
        else "額度全數使用示例（非實際帳單）"
    )
    return [
        "## 估算額度表",
        "",
        f"> 計算基礎：{basis_note}",
        "",
        "| 項目 | 金額／比率 |",
        "|---|---:|",
        f"| CMS 等級 | {result.cms_level} |",
        f"| 法定福利類別 | {result.welfare_label} |",
        f"| 原始月額 | {_money(result.base_quota)} |",
        f"| 調整後月額 | {_money(result.adjusted_quota)} |",
        f"| 本次計算服務費 | {_money(result.calculation_spend)} |",
        f"| 部分負擔比率 | {result.copay_percent}% |",
        f"| 政府給付 | {_money(result.government_payment)} |",
        f"| 額度內部分負擔 | {_money(result.copay)} |",
        f"| 超額自費 | {_money(result.overage)} |",
        f"| 合計自付 | {_money(result.total_out_of_pocket)} |",
    ]


def _reference_section(version: RuleVersion) -> list[str]:
    lines = [
        "## CMS 未知：僅提供額度參考",
        "",
        "尚未提供照管中心正式核定的 CMS，因此不做個人化試算，也不從描述猜級。",
        "",
        "| CMS | 照顧及專業服務月額 | 外籍看護等情形 30% 額度 |",
        "|---:|---:|---:|",
    ]
    for row in get_quota_reference_table(version):
        lines.append(
            f"| {row.cms_level} | {_money(row.monthly_quota)} | "
            f"{_money(row.foreign_caregiver_adjusted_quota)} |"
        )
    return lines


def render_report(
    *,
    eligibility_input: EligibilityInput,
    welfare_category: WelfareCategory | None,
    has_foreign_caregiver: bool | None,
    planned_spend: int | None,
    faq_results: tuple[FaqSearchResult, ...] = (),
    compare_legacy: bool = False,
) -> str:
    eligibility = assess_eligibility(eligibility_input)
    rule = eligibility.rule
    lines = [
        "# 長照服務資格與補助初步建議書",
        "",
        *_eligibility_section(eligibility),
        "",
        "## 規則版本",
        "",
        f"- `{rule.version.value}`",
        f"- 生效基準：{rule.effective_date.isoformat()}",
        f"- 查證日期：{rule.verified_on.isoformat()}",
    ]

    if eligibility_input.official_cms_level is None:
        lines.extend(["", *_reference_section(eligibility_input.rule_version)])
    elif welfare_category is None or has_foreign_caregiver is None:
        lines.extend(
            [
                "",
                "## 估算額度表",
                "",
                "已有正式 CMS，但福利類別或外籍看護資訊不足，暫不計算金額。",
            ]
        )
    else:
        copay = calculate_copay(
            CopayInput(
                cms_level=eligibility_input.official_cms_level,
                welfare_category=welfare_category,
                has_foreign_caregiver=has_foreign_caregiver,
                planned_spend=planned_spend,
                rule_version=eligibility_input.rule_version,
            )
        )
        lines.extend(["", *_copay_section(copay)])

    if compare_legacy and eligibility_input.rule_version is RuleVersion.CURRENT_2026_07:
        legacy_input = EligibilityInput(
            age=eligibility_input.age,
            indigenous=eligibility_input.indigenous,
            has_disability_certificate=eligibility_input.has_disability_certificate,
            has_dementia_diagnosis=eligibility_input.has_dementia_diagnosis,
            is_pac_case=eligibility_input.is_pac_case,
            has_functional_impairment=eligibility_input.has_functional_impairment,
            impairment_duration_months=eligibility_input.impairment_duration_months,
            residence_status=eligibility_input.residence_status,
            official_cms_level=eligibility_input.official_cms_level,
            rule_version=RuleVersion.LEGACY_2022,
        )
        legacy = assess_eligibility(legacy_input)
        lines.extend(
            [
                "",
                "## 舊制比較",
                "",
                f"- `LEGACY_2022` 初篩：`{legacy.status.value}`",
                "- 舊制比較僅供理解規則差異，不代表可追溯申請。",
            ]
        )

    source_rows = [(rule.label, rule.regulation_url)]
    source_rows.extend((item.title, item.url) for item in faq_results if item.url)
    source_rows.append(("1966 長照申請指引", APPLICATION_GUIDE_URL))
    deduped = list(dict.fromkeys(source_rows))
    lines.extend(["", "## 引用來源", ""])
    lines.extend(f"- [{title}]({url})" for title, url in deduped)
    lines.extend(
        [
            "",
            "## 下一步申請流程",
            "",
            "1. 撥打 1966 或聯絡所在地長期照顧管理中心。",
            "2. 由照管專員到府或依規定完成正式評估。",
            "3. 與個案管理員確認 CMS、服務組合、額度與照顧計畫。",
            "",
            "## 免責聲明",
            "",
            "本報告僅供初步試算，不是官方資格核定、法律、醫療或財務建議。"
            "最終以照管中心、地方主管機關與 1966 回覆為準。",
        ]
    )
    return "\n".join(lines)
