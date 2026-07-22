"""LangChain 1.x create_agent 組裝。"""

from __future__ import annotations

from dataclasses import dataclass

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, ToolRetryMiddleware
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import BaseRateLimiter
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from pydantic import SecretStr

from .config import AgentProvider, AgentSettings
from .privacy import SafeAuditLogger, build_pii_middleware
from .toolset import ToolBundle, build_tool_bundle


SYSTEM_PROMPT = """你是台灣長照服務資格與額度初步評估 Agent。

硬性規則：
1. 你只負責理解對話、找缺漏、逐項追問、選工具與整理非金額說明。
2. 絕對不可自行判斷資格、猜 CMS、心算或改寫任何金額；資格與金額只能引用工具結果。
3. 預設 CURRENT_2026_07；只有使用者明確要求才比較 LEGACY_2022。
4. 依序蒐集：規則版本、年齡、原住民、身障證明、失智診斷、PAC、失能或協助需求、住宿狀態、正式 CMS、福利類別、外籍看護、預計服務費。已足以判斷時不要追問無關欄位。
5. CMS 未知時不得推估；只做申請初篩、顯示 CMS 2–8 參考表與 1966 指引。
6. 不要求姓名、身分證、電話、地址。若使用者主動提供，也不得重述。
7. 最終流程必須先呼叫 build_report_draft，取得 report_id 與完整 Markdown，再以完全相同的 report_markdown 呼叫 publish_report。不得自行編輯草稿。
8. publish_report 需要人工 approve 或 reject；核准前不可把草稿稱為最終報告。
9. 所有結論都說明這是初步參考，正式結果以照管中心與 1966 為準。
10. 使用者已明確提供的值不得改成 null。正式 CMS 要同時傳給 eligibility_check 的 official_cms_level、copay_estimate 的 cms_level 與 build_report_draft 的 official_cms_level；預計服務費要原值傳入 planned_spend。
11. 資料完整時依序呼叫 eligibility_check、必要時 copay_estimate、build_report_draft；不可跳過前一步。收到草稿後不要另行解說，立刻用草稿原文呼叫 publish_report。
12. 呼叫 copay_estimate 時五個參數都要傳入：cms_level、welfare_category、has_foreign_caregiver、planned_spend、rule_version。第一／二／三類分別只能傳 FIRST／SECOND／THIRD；沒有外籍看護也必須明確傳 false。
13. 對話中的「不是、沒有、無」要傳對應布林 false，不得反轉；「住家裡、居家」只能傳 residence_status=COMMUNITY，除非使用者明說團體家屋或住宿式機構。
"""


@dataclass(frozen=True, slots=True)
class AgentRuntime:
    graph: CompiledStateGraph
    tools: ToolBundle
    audit: SafeAuditLogger
    settings: AgentSettings


def build_chat_model(
    settings: AgentSettings,
    *,
    cloud_api_key: SecretStr | None = None,
    cloud_max_retries: int | None = None,
    cloud_rate_limiter: BaseRateLimiter | None = None,
) -> BaseChatModel:
    settings.validate()
    if settings.provider is AgentProvider.GEMINI:
        cloud_kwargs: dict[str, object] = {}
        if cloud_api_key is not None:
            cloud_kwargs["api_key"] = cloud_api_key
        if cloud_max_retries is not None:
            cloud_kwargs["max_retries"] = cloud_max_retries
        if cloud_rate_limiter is not None:
            cloud_kwargs["rate_limiter"] = cloud_rate_limiter
        return init_chat_model(
            settings.gemini_model,
            model_provider="google_genai",
            temperature=0,
            **cloud_kwargs,
        )
    if (
        cloud_api_key is not None
        or cloud_max_retries is not None
        or cloud_rate_limiter is not None
    ):
        raise ValueError("cloud API key 設定只能用於雲端 provider")
    model_name = (
        settings.ollama_f1_model
        if settings.provider is AgentProvider.F1_OLLAMA
        else settings.ollama_baseline_model
    )
    return init_chat_model(
        model_name,
        model_provider="ollama",
        base_url=settings.ollama_base_url,
        temperature=0,
        sync_client_kwargs={"timeout": settings.ollama_timeout_seconds},
    )


def build_agent_runtime(
    *,
    settings: AgentSettings | None = None,
    model: BaseChatModel | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    audit: SafeAuditLogger | None = None,
    cloud_api_key: SecretStr | None = None,
    cloud_max_retries: int | None = None,
    cloud_rate_limiter: BaseRateLimiter | None = None,
) -> AgentRuntime:
    settings = settings or AgentSettings.from_env()
    audit = audit or SafeAuditLogger()
    bundle = build_tool_bundle(audit)
    graph = create_agent(
        model=model
        or build_chat_model(
            settings,
            cloud_api_key=cloud_api_key,
            cloud_max_retries=cloud_max_retries,
            cloud_rate_limiter=cloud_rate_limiter,
        ),
        tools=list(bundle.tools),
        system_prompt=SYSTEM_PROMPT,
        middleware=[
            *build_pii_middleware(),
            ToolRetryMiddleware(
                max_retries=0,
                on_failure="continue",
                tools=[
                    "eligibility_check",
                    "copay_estimate",
                    "faq_search",
                    "build_report_draft",
                ],
            ),
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "publish_report": {
                        "allowed_decisions": ["approve", "reject"]
                    }
                },
                description_prefix="完整長照試算報告待人工確認",
            ),
        ],
        checkpointer=checkpointer or InMemorySaver(),
        name="ltc-benefit-agent",
    )
    return AgentRuntime(graph=graph, tools=bundle, audit=audit, settings=settings)
