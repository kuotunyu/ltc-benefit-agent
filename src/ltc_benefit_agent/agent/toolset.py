"""供 create_agent 呼叫的確定性工具集合。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Annotated, Any, Literal

from langchain_core.tools import BaseTool, tool

from ltc_benefit_agent.tools.copay import CopayInput, WelfareCategory, calculate_copay
from ltc_benefit_agent.tools.eligibility import (
    EligibilityInput,
    ResidenceStatus,
    assess_eligibility,
)
from ltc_benefit_agent.tools.faq_search import search_faq_standalone
from ltc_benefit_agent.tools.rules import RuleVersion

from .privacy import SafeAuditLogger, redact_value
from .reports import ReportRegistry, render_report


RuleVersionValue = Literal["LEGACY_2022", "CURRENT_2026_07"]
ResidenceStatusValue = Literal[
    "COMMUNITY", "RESIDENTIAL_INSTITUTION", "GROUP_HOME", "UNKNOWN"
]
WelfareCategoryValue = Literal["FIRST", "SECOND", "THIRD"]


def _json(value: Any) -> str:
    return json.dumps(redact_value(value), ensure_ascii=False, default=str, sort_keys=True)


def _eligibility_input(
    *,
    age: int | None,
    indigenous: bool | None,
    has_disability_certificate: bool | None,
    has_dementia_diagnosis: bool | None,
    is_pac_case: bool | None,
    has_functional_impairment: bool | None,
    impairment_duration_months: int | None,
    residence_status: ResidenceStatusValue,
    official_cms_level: int | None,
    rule_version: RuleVersionValue,
) -> EligibilityInput:
    return EligibilityInput(
        age=age,
        indigenous=indigenous,
        has_disability_certificate=has_disability_certificate,
        has_dementia_diagnosis=has_dementia_diagnosis,
        is_pac_case=is_pac_case,
        has_functional_impairment=has_functional_impairment,
        impairment_duration_months=impairment_duration_months,
        residence_status=ResidenceStatus(residence_status),
        official_cms_level=official_cms_level,
        rule_version=RuleVersion(rule_version),
    )


@dataclass(frozen=True, slots=True)
class ToolBundle:
    tools: tuple[BaseTool, ...]
    registry: ReportRegistry


def build_tool_bundle(audit: SafeAuditLogger | None = None) -> ToolBundle:
    audit = audit or SafeAuditLogger()
    registry = ReportRegistry()

    @tool("eligibility_check")
    def eligibility_check(
        age: Annotated[int | None, "實際年齡整數；未知才傳 null"] = None,
        indigenous: Annotated[bool | None, "是原住民傳 true，不是傳 false"] = None,
        has_disability_certificate: Annotated[
            bool | None, "有身障證明傳 true，沒有傳 false"
        ] = None,
        has_dementia_diagnosis: Annotated[
            bool | None, "有確診失智傳 true，沒有傳 false"
        ] = None,
        is_pac_case: Annotated[
            bool | None, "是 PAC 個案傳 true，不是傳 false"
        ] = None,
        has_functional_impairment: Annotated[
            bool | None, "有失能或生活協助需求傳 true，沒有傳 false"
        ] = None,
        impairment_duration_months: Annotated[
            int | None, "失能或協助需求持續月數；未知才傳 null"
        ] = None,
        residence_status: Annotated[
            ResidenceStatusValue,
            "住家裡或居家傳 COMMUNITY；住宿式機構傳 RESIDENTIAL_INSTITUTION；團體家屋才傳 GROUP_HOME",
        ] = "UNKNOWN",
        official_cms_level: Annotated[
            int | None, "正式 CMS 2 到 8；尚未評估或不知道傳 null"
        ] = None,
        rule_version: RuleVersionValue = RuleVersion.CURRENT_2026_07.value,
    ) -> str:
        """依指定規則版本做長照申請資格初篩；不得用本工具推測 CMS。"""
        args = {
            "age": age,
            "indigenous": indigenous,
            "has_disability_certificate": has_disability_certificate,
            "has_dementia_diagnosis": has_dementia_diagnosis,
            "is_pac_case": is_pac_case,
            "has_functional_impairment": has_functional_impairment,
            "impairment_duration_months": impairment_duration_months,
            "residence_status": residence_status,
            "official_cms_level": official_cms_level,
            "rule_version": rule_version,
        }
        audit.record("tool_call", tool_name="eligibility_check", payload=args)
        result = assess_eligibility(_eligibility_input(**args))
        payload = asdict(result)
        audit.record("tool_result", tool_name="eligibility_check", payload=payload)
        return _json(payload)

    @tool("copay_estimate")
    def copay_estimate(
        cms_level: Annotated[int, "必填；只能傳正式 CMS 整數 2 到 8"],
        welfare_category: Annotated[
            WelfareCategoryValue,
            "必填；第一類／長照低收入戶傳 FIRST、第二類／長照中低收入戶傳 SECOND、第三類／長照一般戶／一般戶傳 THIRD，不可傳數字",
        ],
        has_foreign_caregiver: Annotated[
            bool,
            "必填且不可省略；有外籍家庭看護傳 true，沒有則明確傳 false",
        ],
        planned_spend: Annotated[
            int | None,
            "預計每月服務費整數；未知才傳 null，不可自行計算",
        ] = None,
        rule_version: RuleVersionValue = RuleVersion.CURRENT_2026_07.value,
    ) -> str:
        """資格工具之後，以正式 CMS 2–8 做全整數試算；完成後繼續建稿。"""
        audit.record(
            "tool_call",
            tool_name="copay_estimate",
            payload={
                "cms_level": cms_level,
                "welfare_category": welfare_category,
                "has_foreign_caregiver": has_foreign_caregiver,
                "planned_spend": planned_spend,
                "rule_version": rule_version,
            },
        )
        result = calculate_copay(
            CopayInput(
                cms_level=cms_level,
                welfare_category=WelfareCategory(welfare_category),
                has_foreign_caregiver=has_foreign_caregiver,
                planned_spend=planned_spend,
                rule_version=RuleVersion(rule_version),
            )
        )
        payload = asdict(result)
        audit.record("tool_result", tool_name="copay_estimate", payload=payload)
        return _json(payload)

    @tool("faq_search")
    def faq_search(query: str, limit: int = 5) -> str:
        """搜尋長照資格、額度、外籍看護、部分負擔與申請流程法源。"""
        audit.record(
            "tool_call",
            tool_name="faq_search",
            payload={"query": query, "limit": limit},
        )
        payload = [asdict(item) for item in search_faq_standalone(query, limit=limit)]
        audit.record("tool_result", tool_name="faq_search", payload=payload)
        return _json(payload)

    @tool("build_report_draft")
    def build_report_draft(
        age: int | None,
        indigenous: bool | None,
        has_disability_certificate: bool | None,
        has_dementia_diagnosis: bool | None,
        is_pac_case: bool | None,
        has_functional_impairment: bool | None,
        impairment_duration_months: int | None,
        residence_status: ResidenceStatusValue,
        official_cms_level: int | None = None,
        welfare_category: WelfareCategoryValue | None = None,
        has_foreign_caregiver: bool | None = None,
        planned_spend: int | None = None,
        rule_version: RuleVersionValue = RuleVersion.CURRENT_2026_07.value,
        compare_legacy: bool = False,
    ) -> str:
        """資格與必要金額工具之後，建立不可由 LLM 改算數字的 Markdown 草稿。"""
        audit.record(
            "tool_call",
            tool_name="build_report_draft",
            payload={
                "age": age,
                "indigenous": indigenous,
                "has_disability_certificate": has_disability_certificate,
                "has_dementia_diagnosis": has_dementia_diagnosis,
                "is_pac_case": is_pac_case,
                "has_functional_impairment": has_functional_impairment,
                "impairment_duration_months": impairment_duration_months,
                "residence_status": residence_status,
                "official_cms_level": official_cms_level,
                "welfare_category": welfare_category,
                "has_foreign_caregiver": has_foreign_caregiver,
                "planned_spend": planned_spend,
                "rule_version": rule_version,
                "compare_legacy": compare_legacy,
            },
        )
        eligibility_input = _eligibility_input(
            age=age,
            indigenous=indigenous,
            has_disability_certificate=has_disability_certificate,
            has_dementia_diagnosis=has_dementia_diagnosis,
            is_pac_case=is_pac_case,
            has_functional_impairment=has_functional_impairment,
            impairment_duration_months=impairment_duration_months,
            residence_status=residence_status,
            official_cms_level=official_cms_level,
            rule_version=rule_version,
        )
        markdown = render_report(
            eligibility_input=eligibility_input,
            welfare_category=(
                WelfareCategory(welfare_category) if welfare_category is not None else None
            ),
            has_foreign_caregiver=has_foreign_caregiver,
            planned_spend=planned_spend,
            compare_legacy=compare_legacy,
        )
        draft = registry.register(markdown)
        payload = asdict(draft)
        audit.record("tool_result", tool_name="build_report_draft", payload=payload)
        return _json(payload)

    @tool("publish_report")
    def publish_report(report_id: str, report_markdown: str) -> str:
        """人工核准後發布完整報告；report_markdown 必須與已登錄草稿完全一致。"""
        audit.record(
            "tool_call",
            tool_name="publish_report",
            payload={"report_id": report_id, "report_markdown": report_markdown},
        )
        published = registry.verify_and_publish(report_id, report_markdown)
        audit.record(
            "tool_result",
            tool_name="publish_report",
            payload={"report_id": report_id, "published": True},
        )
        return published

    return ToolBundle(
        tools=(
            eligibility_check,
            copay_estimate,
            faq_search,
            build_report_draft,
            publish_report,
        ),
        registry=registry,
    )
