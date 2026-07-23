"""跨輪保留使用者明確提供的必要欄位，並守住工具執行順序。

這個 middleware 只用保守的 literal parser 保存計算必要欄位，不推論資格、
CMS 或金額。模型若在已有多個明確欄位時仍漏掉第一個資格工具，最多只會被
要求重試一次；真正的 tool call 仍必須由模型產生。
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any, NotRequired
from uuid import uuid4

from langchain.agents.middleware.types import AgentState
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command


_ELIGIBILITY_FIELDS = (
    "age",
    "indigenous",
    "has_disability_certificate",
    "has_dementia_diagnosis",
    "is_pac_case",
    "has_functional_impairment",
    "impairment_duration_months",
    "residence_status",
    "official_cms_level",
    "rule_version",
)

_FIELD_LABELS = {
    "age": "實際年齡（幾歲）",
    "indigenous": "是否為原住民",
    "has_disability_certificate": "是否領有身心障礙證明",
    "has_dementia_diagnosis": "是否經醫師確診失智",
    "is_pac_case": "是否為 PAC（急性後期照護）個案",
    "has_functional_impairment": "洗澡、穿衣、吃飯、起身走動或如廁是否需要他人協助",
    "impairment_duration_months": "上述失能或需要協助已持續幾個月",
    "residence_status": "目前住家裡、團體家屋或住宿式機構",
    "official_cms_level": "是否已有照管中心正式核定的長照需要等級（CMS 第 2–8 級；不知道可直接回答不知道）",
}

_BLOCKED_STATUS = "BLOCKED_UNTIL_ELIGIBILITY_COMPLETE"
_INITIAL_RETRY_MARKER = "INITIAL_ELIGIBILITY_TOOL_RETRY"
_TOOL_CALL_CODE_FENCE = re.compile(
    r"^\s*```(?:tool_call|json)\s*(\{.*\})\s*```\s*$", re.DOTALL
)
_AGE_PATTERN = re.compile(r"(?<!\d)(\d{1,3})\s*歲")
_CMS_LEVEL_PATTERN = re.compile(
    r"(?<![A-Za-z])CMS\s*(?:等級)?\s*[:：]?\s*([2-8])(?!\d)", re.IGNORECASE
)
_CMS_REFERENCE_RANGE_PATTERN = re.compile(
    r"(?<![A-Za-z])CMS\s*(?:等級)?\s*[:：]?\s*[2-8]\s*"
    r"(?:至|到|[-–—~～])\s*[2-8]\s*(?:級)?",
    re.IGNORECASE,
)
_CMS_UNKNOWN_PATTERNS = (
    re.compile(
        r"(?:尚未|還沒|未曾|沒有)\s*(?:接受|進行|做|取得|獲得)?\s*"
        r"(?:正式)?\s*CMS(?:\s*(?:評估|等級|結果))?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:不知道|不清楚|未知|尚不確定|無法確認)\s*(?:正式)?\s*"
        r"CMS(?:\s*等級)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:不知道|不清楚|未知|尚不確定|無法確認)\s*(?:自己)?\s*"
        r"(?:有沒有|是否有)?\s*(?:正式)?\s*CMS(?:\s*等級)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![A-Za-z])CMS(?:\s*等級)?\s*"
        r"(?:我|本人)?\s*(?:未知|不知道|不清楚|尚未評估|未評估|不確定)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:不要|不得|請勿)\s*(?:推估|猜測|臆測)\s*(?:正式)?\s*CMS",
        re.IGNORECASE,
    ),
)
_DURATION_PATTERNS = (
    re.compile(
        r"(?:失能|生活需要協助|需要生活協助|需要(?:他人)?協助|"
        r"生活協助需求|協助需求|需求)"
        r"\s*(?:已|持續|只有)?\s*(\d+)\s*(天|日|週|周|星期|個?月|年)"
    ),
    re.compile(r"(?:已|持續|大約|約|只有)\s*(\d+)\s*(天|日|週|周|星期|個?月|年)"),
)
_PLANNED_SPEND_PATTERN = re.compile(
    r"(?:預計(?:每月)?服務費|這個月預計服務費|服務費|預計服務)"
    r"\s*([\d,]+)\s*元?"
)
_WELFARE_CATEGORY_PATTERN = re.compile(
    r"(?P<second>第二類|(?:長照)?中低收入戶)"
    r"|(?P<first>第一類|(?:長照)?低收入戶)"
    r"|(?P<third>第三類|(?:長照)?一般戶)"
)

_FIELD_EVIDENCE_PATTERNS: dict[str, re.Pattern[str]] = {
    "age": re.compile(r"年齡|\d{1,3}\s*歲"),
    "indigenous": re.compile(r"原住民"),
    "has_disability_certificate": re.compile(r"身障|身心障礙"),
    "has_dementia_diagnosis": re.compile(r"失智"),
    "is_pac_case": re.compile(r"PAC|急性後期照護|出院準備", re.IGNORECASE),
    "has_functional_impairment": re.compile(
        r"失能|生活協助|需要(?:他人)?協助|不需要(?:他人)?協助|"
        r"洗澡|穿衣|吃飯|走動|如廁|"
        r"(?:自己|自行|獨立).{0,8}(?:進行|完成|處理|做)|"
        r"(?:希望|想要|需要).{0,6}(?:有人|他人)?(?:幫助|幫忙)"
    ),
    "impairment_duration_months": re.compile(
        r"\d+\s*(?:天|日|週|周|星期|個?月|年)|半年|一年"
    ),
    "residence_status": re.compile(
        r"住家裡|住在家|居家|住宿式機構|團體家屋|獨居|"
        r"(?:自己|獨自)住|(?:1|一)個人住|"
        r"住(?:在)?[^，。；\n]{0,12}(?:套房|公寓|住宅|透天|自宅|家中|家裡)"
    ),
    "official_cms_level": re.compile(r"CMS", re.IGNORECASE),
}


class CaseIntakeState(AgentState):
    """跨模型／工具節點保留使用者明確寫出的計算必要欄位。"""

    case_explicit_eligibility_facts: NotRequired[dict[str, Any]]
    case_explicit_copay_facts: NotRequired[dict[str, Any]]


def _message_text(message: BaseMessage | None) -> str:
    if message is None:
        return ""
    if isinstance(message.content, str):
        return message.content
    parts: list[str] = []
    for block in message.content_blocks:
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "".join(parts)


def _messages_from_state(state: Any) -> list[BaseMessage]:
    if not isinstance(state, dict):
        return []
    messages = state.get("messages", [])
    return [message for message in messages if isinstance(message, BaseMessage)]


def _current_turn(messages: list[BaseMessage]) -> list[BaseMessage]:
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return messages[index:]
    return messages


def _is_missing(field: str, value: Any) -> bool:
    if value is None:
        return True
    if field == "residence_status" and value == "UNKNOWN":
        return True
    return False


def _has_user_evidence(messages: list[BaseMessage], field: str) -> bool:
    """確認使用者至少談過該欄位，避免模型把未提及的值當成已知。"""

    pattern = _FIELD_EVIDENCE_PATTERNS.get(field)
    if pattern is None:
        return field == "rule_version"
    return any(
        isinstance(message, HumanMessage) and pattern.search(_message_text(message))
        for message in messages
    )


def _desired_rule_version(messages: list[BaseMessage]) -> str:
    """只有使用者明確提到舊制時才離開現制預設。"""

    for message in reversed(messages):
        if not isinstance(message, HumanMessage):
            continue
        text = _message_text(message)
        if "LEGACY_2022" in text or "舊制" in text or "2022" in text:
            return "LEGACY_2022"
        if "CURRENT_2026_07" in text or "現制" in text or "2026" in text:
            return "CURRENT_2026_07"
    return "CURRENT_2026_07"


def _rule_version_intent(text: str) -> str | None:
    if "LEGACY_2022" in text or "舊制" in text or "2022" in text:
        return "LEGACY_2022"
    if "CURRENT_2026_07" in text or "現制" in text or "2026" in text:
        return "CURRENT_2026_07"
    return None


def _explicit_bool(
    text: str, *, false_patterns: tuple[str, ...], true_patterns: tuple[str, ...]
) -> bool | None:
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in false_patterns):
        return False
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in true_patterns):
        return True
    return None


def explicit_cms_intent(messages: list[BaseMessage]) -> tuple[bool, int | None]:
    """回傳使用者最新的正式 CMS 意圖；參考範圍不視為個人等級。

    第一個布林值表示使用者是否明確談到自己的 CMS 狀態；第二個值為
    正式等級，或在明確表示尚未評估／不知道時為 ``None``。單純要求
    「CMS 2 至 8 級參考表」會回傳 ``(False, None)``。
    """

    latest: tuple[int, int | None] | None = None
    offset = 0
    for message in messages:
        if not isinstance(message, HumanMessage):
            continue
        text = _message_text(message)
        range_spans = [match.span() for match in _CMS_REFERENCE_RANGE_PATTERN.finditer(text)]
        for match in _CMS_LEVEL_PATTERN.finditer(text):
            if any(start <= match.start() < end for start, end in range_spans):
                continue
            candidate = (offset + match.start(), int(match.group(1)))
            if latest is None or candidate[0] >= latest[0]:
                latest = candidate
        for pattern in _CMS_UNKNOWN_PATTERNS:
            for match in pattern.finditer(text):
                candidate = (offset + match.start(), None)
                if latest is None or candidate[0] >= latest[0]:
                    latest = candidate
        offset += len(text) + 1
    if latest is None:
        return False, None
    return True, latest[1]


def _explicit_eligibility_facts(messages: list[BaseMessage]) -> dict[str, Any]:
    """只擷取格式明確、可逐字核對的欄位，不從疾病或年齡推定失能。"""

    facts: dict[str, Any] = {}
    for message in messages:
        if not isinstance(message, HumanMessage):
            continue
        text = _message_text(message)
        if match := _AGE_PATTERN.search(text):
            facts["age"] = int(match.group(1))
        boolean_specs = {
            "indigenous": (
                (r"不是原住民", r"非原住民"),
                (r"是原住民", r"(?<!不)(?<!非)原住民"),
            ),
            "has_disability_certificate": (
                (
                    r"沒有身(?:心)?障",
                    r"無身(?:心)?障",
                    r"(?:身心障礙證明|身障證明|身心障礙)[^。；\n]{0,20}(?:都)?沒有",
                ),
                (r"有身心障礙證明", r"領有身心障礙證明", r"有身障證明"),
            ),
            "has_dementia_diagnosis": (
                (
                    r"沒有失智",
                    r"沒有[^，。；]{0,8}失智",
                    r"無失智",
                    r"(?:醫師)?(?:確診|診斷)?失智[^。；\n]{0,12}(?:都)?沒有",
                ),
                (r"確診失智", r"有失智診斷", r"醫師.*失智"),
            ),
            "is_pac_case": (
                (
                    r"不是\s*PAC",
                    r"非\s*PAC",
                    r"沒有\s*PAC",
                    r"沒有[^，。；]{0,20}(?:或)?\s*PAC",
                    r"無(?:身障)?(?:失智)?\s*PAC",
                ),
                (r"是.*PAC.*個案", r"PAC\s*個案", r"出院準備\s*PAC"),
            ),
            "has_functional_impairment": (
                (
                    r"不需要(?:他人)?協助",
                    r"無需(?:他人)?協助",
                    r"沒有失能",
                    r"(?:自己|自行|獨立)(?:都)?可以(?:完成|處理|做|進行)",
                    r"可以(?:自己|自行|獨立)(?:完成|處理|做|進行)",
                ),
                (
                    r"生活(?<!不)需要協助",
                    r"(?<!不)需要生活協助",
                    r"(?<!不)需要(?:他人)?協助",
                    r"(?:希望|想要|需要).{0,6}(?:有人|他人)?(?:幫助|幫忙)",
                    r"生活協助需求",
                    r"目前需要協助",
                    r"失能\s*\d+\s*(?:個)?月",
                    r"(?:洗澡|穿衣|吃飯|起身走動|走動|如廁)"
                    r".{0,20}(?<!不)需要.*協助",
                ),
            ),
        }
        for field, (false_patterns, true_patterns) in boolean_specs.items():
            if field == "has_functional_impairment":
                # 同一句可能同時列出「洗澡需協助、吃飯不需協助」。只要有
                # 一項明確需要協助即為 True；只有負向敘述時才是 False。
                value = _explicit_bool(
                    text,
                    false_patterns=(),
                    true_patterns=tuple(true_patterns),
                )
                if value is None:
                    value = _explicit_bool(
                        text,
                        false_patterns=tuple(false_patterns),
                        true_patterns=(),
                    )
            else:
                value = _explicit_bool(
                    text,
                    false_patterns=tuple(false_patterns),
                    true_patterns=tuple(true_patterns),
                )
            if value is not None:
                facts[field] = value

        for pattern in _DURATION_PATTERNS:
            if match := pattern.search(text):
                value = int(match.group(1))
                unit = match.group(2)
                if unit in {"天", "日"}:
                    months = value // 30
                elif unit in {"週", "周", "星期"}:
                    months = (value * 7) // 30
                elif unit == "年":
                    months = value * 12
                else:
                    months = value
                facts["impairment_duration_months"] = months
                break

        if "住宿式機構" in text:
            facts["residence_status"] = "RESIDENTIAL_INSTITUTION"
        elif "團體家屋" in text:
            facts["residence_status"] = "GROUP_HOME"
        elif (
            "住家裡" in text
            or "住在家裡" in text
            or "居家" in text
            or re.search(
                r"(?:獨居|(?:自己|獨自)住|(?:1|一)個人住|"
                r"住(?:在)?[^，。；\n]{0,12}(?:套房|公寓|住宅|透天|自宅|家中|家裡))",
                text,
            )
        ):
            facts["residence_status"] = "COMMUNITY"

    cms_was_stated, cms_level = explicit_cms_intent(messages)
    if cms_was_stated:
        facts["official_cms_level"] = cms_level
    facts["rule_version"] = _desired_rule_version(messages)
    return facts


def _explicit_copay_facts(messages: list[BaseMessage]) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    for message in messages:
        if not isinstance(message, HumanMessage):
            continue
        text = _message_text(message)
        category_matches = list(_WELFARE_CATEGORY_PATTERN.finditer(text))
        if category_matches:
            latest = category_matches[-1]
            facts["welfare_category"] = {
                "first": "FIRST",
                "second": "SECOND",
                "third": "THIRD",
            }[latest.lastgroup or "third"]
        caregiver = _explicit_bool(
            text,
            false_patterns=(
                r"沒有外籍(?:家庭)?看護",
                r"無外籍(?:家庭)?看護",
                r"沒有外看",
                r"無外看",
            ),
            true_patterns=(r"有外籍(?:家庭)?看護", r"有外看"),
        )
        if caregiver is not None:
            facts["has_foreign_caregiver"] = caregiver
        if match := _PLANNED_SPEND_PATTERN.search(text):
            facts["planned_spend"] = int(match.group(1).replace(",", ""))
    cms_was_stated, cms_level = explicit_cms_intent(messages)
    if cms_was_stated:
        facts["cms_level"] = cms_level
    facts["rule_version"] = _desired_rule_version(messages)
    return facts


def merge_explicit_case_facts(
    text: str,
    *,
    previous_eligibility: dict[str, Any] | None = None,
    previous_copay: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """把單一已遮蔽 user turn 合併成不含原文的跨輪必要欄位。"""

    message = HumanMessage(content=text)
    eligibility = dict(previous_eligibility or {})
    copay = dict(previous_copay or {})
    current_eligibility = _explicit_eligibility_facts([message])
    current_copay = _explicit_copay_facts([message])
    current_eligibility.pop("rule_version", None)
    current_copay.pop("rule_version", None)
    eligibility.update(current_eligibility)
    copay.update(current_copay)
    version = _rule_version_intent(text) or eligibility.get(
        "rule_version", "CURRENT_2026_07"
    )
    eligibility["rule_version"] = version
    copay["rule_version"] = version
    return eligibility, copay


def _accumulated_eligibility_args(messages: list[BaseMessage]) -> dict[str, Any]:
    accumulated: dict[str, Any] = {}
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        for call in message.tool_calls:
            if call.get("name") != "eligibility_check":
                continue
            args = call.get("args")
            if not isinstance(args, dict):
                continue
            for field in _ELIGIBILITY_FIELDS:
                value = args.get(field)
                if _has_user_evidence(messages, field) and not _is_missing(
                    field, value
                ):
                    accumulated[field] = value
    accumulated.update(_explicit_eligibility_facts(messages))
    return accumulated


def _merge_eligibility_args(
    messages: list[BaseMessage], incoming: dict[str, Any]
) -> dict[str, Any]:
    merged = _accumulated_eligibility_args(messages)
    for field in _ELIGIBILITY_FIELDS:
        value = incoming.get(field)
        if _has_user_evidence(messages, field) and not _is_missing(field, value):
            merged[field] = value
    merged.update(_explicit_eligibility_facts(messages))
    return merged


def _tool_payload(message: ToolMessage | None) -> dict[str, Any] | None:
    if message is None or not isinstance(message.content, str):
        return None
    try:
        payload = json.loads(message.content)
    except (TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _latest_tool_message(
    messages: list[BaseMessage], name: str
) -> tuple[int, ToolMessage] | None:
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if (
            isinstance(message, ToolMessage)
            and message.name == name
            and getattr(message, "status", "success") != "error"
        ):
            return index, message
    return None


def _eligibility_ready(messages: list[BaseMessage]) -> tuple[bool, dict[str, Any] | None]:
    latest = _latest_tool_message(messages, "eligibility_check")
    payload = _tool_payload(latest[1]) if latest is not None else None
    return bool(payload and payload.get("status") != "INSUFFICIENT_INFORMATION"), payload


def _exact_publication_args(messages: list[BaseMessage]) -> dict[str, str] | None:
    """從確定性 draft tool result 取回 HITL 必須展示的原文。"""

    latest = _latest_tool_message(messages, "build_report_draft")
    payload = _tool_payload(latest[1]) if latest is not None else None
    if payload is None:
        return None
    report_id = payload.get("report_id")
    markdown = payload.get("markdown")
    if not isinstance(report_id, str) or not isinstance(markdown, str):
        return None
    return {"report_id": report_id, "report_markdown": markdown}


def _blocked_message(request: ToolCallRequest, reason: str) -> ToolMessage:
    return ToolMessage(
        content=json.dumps(
            {"status": _BLOCKED_STATUS, "reason": reason},
            ensure_ascii=False,
            sort_keys=True,
        ),
        name=request.tool_call["name"],
        tool_call_id=request.tool_call["id"],
        status="error",
    )


def _guard_tool_call(request: ToolCallRequest) -> ToolCallRequest | ToolMessage:
    messages = _messages_from_state(request.state)
    state = request.state if isinstance(request.state, dict) else {}
    explicit_eligibility = state.get("case_explicit_eligibility_facts", {})
    explicit_eligibility = (
        dict(explicit_eligibility) if isinstance(explicit_eligibility, dict) else {}
    )
    explicit_copay = state.get("case_explicit_copay_facts", {})
    explicit_copay = dict(explicit_copay) if isinstance(explicit_copay, dict) else {}
    name = request.tool_call["name"]
    args = request.tool_call.get("args", {})
    args = dict(args) if isinstance(args, dict) else {}
    cms_was_stated, explicit_cms_level = explicit_cms_intent(messages)
    cms_is_explicitly_unknown = (
        cms_was_stated and explicit_cms_level is None
    ) or (
        "official_cms_level" in explicit_eligibility
        and explicit_eligibility["official_cms_level"] is None
    )

    if name == "eligibility_check":
        validated_args = _merge_eligibility_args(messages, args)
        # before_model 已看過該輪最新 HumanMessage；它的明確值優先於模型誤讀。
        validated_args.update(explicit_eligibility)
        modified = {
            **request.tool_call,
            "args": validated_args,
        }
        return request.override(tool_call=modified)

    if name == "copay_estimate":
        if cms_is_explicitly_unknown:
            return _blocked_message(
                request,
                "使用者已明確表示尚未取得正式 CMS；不得猜測個人等級或呼叫"
                " copay_estimate。請改建立 CMS 未知參考報告。",
            )
        ready, _ = _eligibility_ready(messages)
        if not ready:
            return _blocked_message(
                request,
                "資格資料尚未完整。請先依所有使用者訊息重新呼叫 eligibility_check；"
                "不得直接試算金額。",
            )
        args.update(_explicit_copay_facts(messages))
        args.update(explicit_copay)
        if payload := _eligibility_ready(messages)[1]:
            if payload.get("official_cms_level") is not None:
                args["cms_level"] = payload["official_cms_level"]
        return request.override(tool_call={**request.tool_call, "args": args})

    if name == "build_report_draft":
        ready, payload = _eligibility_ready(messages)
        if not ready or payload is None:
            return _blocked_message(
                request,
                "資格資料尚未完整。請先完成 eligibility_check，再建立報告草稿。",
            )
        if payload.get("official_cms_level") is None and (
            _has_explicit_cms(messages)
            or explicit_eligibility.get("official_cms_level") is not None
        ):
            return _blocked_message(
                request,
                "使用者已明確提供正式 CMS 2–8，但 eligibility_check 漏傳該值。"
                "請先依原文重新呼叫 eligibility_check；不得降級成 CMS 未知參考報告。",
            )
        eligibility = _latest_tool_message(messages, "eligibility_check")
        copay = _latest_tool_message(messages, "copay_estimate")
        if payload.get("official_cms_level") is not None and not cms_is_explicitly_unknown and (
            eligibility is None or copay is None or copay[0] < eligibility[0]
        ):
            return _blocked_message(
                request,
                "已有正式 CMS，但尚未完成對應的 copay_estimate；不得跳過金額工具建稿。",
            )
        args["rule_version"] = explicit_eligibility.get(
            "rule_version", _desired_rule_version(messages)
        )
        eligibility_message = _latest_tool_message(messages, "eligibility_check")
        if eligibility_message is not None:
            artifact = eligibility_message[1].artifact
            if isinstance(artifact, dict) and isinstance(
                artifact.get("validated_arguments"), dict
            ):
                args.update(artifact["validated_arguments"])
        if copay is not None and not cms_is_explicitly_unknown:
            artifact = copay[1].artifact
            if isinstance(artifact, dict) and isinstance(
                artifact.get("validated_arguments"), dict
            ):
                copay_args = artifact["validated_arguments"]
                for source, target in (
                    ("welfare_category", "welfare_category"),
                    ("has_foreign_caregiver", "has_foreign_caregiver"),
                    ("planned_spend", "planned_spend"),
                ):
                    if source in copay_args:
                        args[target] = copay_args[source]
        args["rule_version"] = explicit_eligibility.get(
            "rule_version", _desired_rule_version(messages)
        )
        if cms_is_explicitly_unknown:
            args["official_cms_level"] = None
            for field in (
                "welfare_category",
                "has_foreign_caregiver",
                "planned_spend",
            ):
                args.pop(field, None)
        return request.override(tool_call={**request.tool_call, "args": args})

    return request


def _guard_model_response(
    request: ModelRequest, response: ModelResponse[Any]
) -> ModelResponse[Any]:
    """在 tool node 建立前校正模型工具參數，使用此輪最新的 state facts。"""

    state = request.state if isinstance(request.state, dict) else {}
    explicit_eligibility = state.get("case_explicit_eligibility_facts", {})
    explicit_eligibility = (
        dict(explicit_eligibility) if isinstance(explicit_eligibility, dict) else {}
    )
    explicit_copay = state.get("case_explicit_copay_facts", {})
    explicit_copay = dict(explicit_copay) if isinstance(explicit_copay, dict) else {}
    latest_eligibility = _latest_tool_message(request.messages, "eligibility_check")
    eligibility_payload = (
        _tool_payload(latest_eligibility[1])
        if latest_eligibility is not None
        else None
    )
    cms_was_stated, explicit_cms_level = explicit_cms_intent(request.messages)
    cms_is_explicitly_unknown = (
        cms_was_stated and explicit_cms_level is None
    ) or (
        "official_cms_level" in explicit_eligibility
        and explicit_eligibility["official_cms_level"] is None
    )
    changed = False
    result: list[BaseMessage] = []
    for message in response.result:
        if not isinstance(message, AIMessage):
            result.append(message)
            continue
        if not message.tool_calls:
            if _should_recheck_eligibility(
                explicit_eligibility, eligibility_payload
            ):
                result.append(
                    message.model_copy(
                        update={
                            "content": "",
                            "tool_calls": [
                                {
                                    "name": "eligibility_check",
                                    "args": explicit_eligibility,
                                    "id": f"intake-recheck-{uuid4().hex}",
                                    "type": "tool_call",
                                }
                            ],
                        }
                    )
                )
                changed = True
            elif (
                eligibility_payload
                and eligibility_payload.get("status") == "INSUFFICIENT_INFORMATION"
            ):
                result.append(
                    message.model_copy(
                        update={
                            "content": _missing_followup(
                                request.messages, eligibility_payload
                            )
                        }
                    )
                )
                changed = True
            else:
                result.append(message)
            continue
        tool_calls: list[dict[str, Any]] = []
        for tool_call in message.tool_calls:
            name = tool_call.get("name")
            guarded_name = name
            raw_args = tool_call.get("args")
            args = dict(raw_args) if isinstance(raw_args, dict) else {}
            if name == "eligibility_check":
                args = _merge_eligibility_args(request.messages, args)
                args.update(explicit_eligibility)
                if cms_is_explicitly_unknown:
                    args["official_cms_level"] = None
            elif name == "copay_estimate":
                ready, _ = _eligibility_ready(request.messages)
                if cms_is_explicitly_unknown and ready:
                    # 明確 unknown CMS 時，即使模型硬猜等級也直接改走參考報告；
                    # build_report_draft 的 tool guard 會填入已驗證的資格 artifact。
                    guarded_name = "build_report_draft"
                    args = {}
                elif not ready:
                    # 模型若在新一輪補資料後直接跳到試算，先改成資格重檢；
                    # 不使用或計算任何金額。
                    guarded_name = "eligibility_check"
                    args = _merge_eligibility_args(request.messages, {})
                    args.update(explicit_eligibility)
                    if cms_is_explicitly_unknown:
                        args["official_cms_level"] = None
                else:
                    args.update(explicit_copay)
                    if explicit_eligibility.get("official_cms_level") is not None:
                        args["cms_level"] = explicit_eligibility[
                            "official_cms_level"
                        ]
            elif name == "publish_report":
                # 相容 adapter 偶爾把 Markdown 換行再次跳脫成字面 `\n`；HITL
                # 必須改用剛才確定性 draft tool 的原始 ID 與 Markdown。
                exact_publication = _exact_publication_args(request.messages)
                if exact_publication is not None:
                    args = exact_publication
            tool_calls.append({**tool_call, "name": guarded_name, "args": args})
            changed = changed or guarded_name != name or args != raw_args
        result.append(
            message.model_copy(update={"tool_calls": tool_calls})
            if tool_calls != message.tool_calls
            else message
        )
    if not changed:
        return response
    return ModelResponse(result=result, structured_response=response.structured_response)


def _response_has_tool_calls(response: ModelResponse[Any]) -> bool:
    return any(
        isinstance(message, AIMessage) and bool(message.tool_calls)
        for message in response.result
    )


def _normalize_explicit_tool_call_content(
    response: ModelResponse[Any], *, allowed_tools: set[str]
) -> ModelResponse[Any]:
    """把相容 adapter 明確輸出的單一 JSON tool call 正規化。

    只接受完整 code fence、已註冊工具名稱與 dict arguments；不從一般文字猜測
    意圖，也不補任何參數。後續仍會經 `_guard_model_response` 與 tool middleware。
    """

    changed = False
    normalized: list[BaseMessage] = []
    for message in response.result:
        if not isinstance(message, AIMessage) or message.tool_calls:
            normalized.append(message)
            continue
        match = _TOOL_CALL_CODE_FENCE.fullmatch(_message_text(message))
        if match is None:
            normalized.append(message)
            continue
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            normalized.append(message)
            continue
        name = payload.get("name") if isinstance(payload, dict) else None
        arguments = payload.get("arguments") if isinstance(payload, dict) else None
        if name not in allowed_tools or not isinstance(arguments, dict):
            normalized.append(message)
            continue
        normalized.append(
            message.model_copy(
                update={
                    "content": "",
                    "tool_calls": [
                        {
                            "name": name,
                            "args": arguments,
                            "id": f"adapter-normalized-{uuid4().hex}",
                            "type": "tool_call",
                        }
                    ],
                }
            )
        )
        changed = True
    if not changed:
        return response
    return ModelResponse(
        result=normalized, structured_response=response.structured_response
    )


def _initial_eligibility_retry_prompt(request: ModelRequest) -> str | None:
    """資料已具體但模型只回文字時，產生一次有界重試提示。

    至少要有兩個非空的明確欄位，避免一般 FAQ 或只提到一個年齡數字時被
    強制切入個案初篩。這裡只要求模型重新選工具，不合成或執行 tool call。
    """

    if _latest_tool_message(request.messages, "eligibility_check") is not None:
        return None
    state = request.state if isinstance(request.state, dict) else {}
    facts = state.get("case_explicit_eligibility_facts", {})
    facts = dict(facts) if isinstance(facts, dict) else {}
    visible = {
        field: value
        for field, value in facts.items()
        if field in _ELIGIBILITY_FIELDS
        and field != "rule_version"
        and not _is_missing(field, value)
    }
    if len(visible) < 2:
        return None
    return "\n".join(
        [
            f"{_INITIAL_RETRY_MARKER}（本模型節點只允許重試一次）：",
            "上一個回應沒有呼叫任何工具，但使用者已明確提供多個資格初篩欄位。",
            "現在不要輸出說明、不要重問已提供的欄位，也不要自行判斷資格或計算金額。",
            "請立刻由你產生一個 eligibility_check tool call；帶入下列明確值，",
            "其餘未明確提供的欄位維持 null／UNKNOWN：",
            json.dumps(visible, ensure_ascii=False, sort_keys=True),
            f"rule_version 必須是 {facts.get('rule_version', 'CURRENT_2026_07')}。",
        ]
    )


def _request_with_added_system_prompt(request: ModelRequest, prompt: str) -> ModelRequest:
    existing = request.system_message
    base = _message_text(existing)
    guarded = SystemMessage(content=f"{base}\n\n{prompt}" if base else prompt)
    return request.override(system_message=guarded)


def _initial_retry_request(request: ModelRequest, prompt: str) -> ModelRequest:
    """重試時只暴露已註冊的 eligibility tool，降低相容 adapter 負擔。"""

    guarded = _request_with_added_system_prompt(request, prompt)
    eligibility_tools = [
        tool
        for tool in request.tools
        if getattr(tool, "name", None) == "eligibility_check"
        or (isinstance(tool, dict) and tool.get("name") == "eligibility_check")
    ]
    if not eligibility_tools:  # pragma: no cover - create_agent 註冊契約破壞時保守回退
        return guarded
    return guarded.override(
        # 不把可能含提示注入或不必要 PII 的原始對話再次送入 retry；system prompt
        # 已只有 PII 後、literal parser 明確抽出的必要欄位。
        messages=[
            HumanMessage(
                content=(
                    "請依 system 提供的結構化欄位，立即呼叫唯一的 "
                    "eligibility_check 工具；不要輸出其他文字。"
                )
            )
        ],
        tools=eligibility_tools,
        # 支援 tool_choice 的 provider 會直接強制；目前 Ollama connector 會忽略，
        # 但仍只看得到上方唯一一個已註冊工具。
        tool_choice="eligibility_check",
    )


def _should_recheck_eligibility(
    facts: dict[str, Any], payload: dict[str, Any] | None
) -> bool:
    """判斷明確欄位是否足以重跑工具；不在此判斷資格結論。"""

    if payload and payload.get("status") != "INSUFFICIENT_INFORMATION":
        return False
    if payload:
        missing = tuple(str(field) for field in payload.get("missing_fields", []))
        return bool(missing) and all(
            not _is_missing(field, facts.get(field)) for field in missing
        )
    return False


def _attach_validated_arguments(
    request: ToolCallRequest, result: ToolMessage | Command[Any]
) -> ToolMessage | Command[Any]:
    """把實際執行參數留在不送給模型的 artifact，供後段 renderer 使用。"""

    if not isinstance(result, ToolMessage):
        return result
    args = request.tool_call.get("args")
    if not isinstance(args, dict):
        return result
    artifact = dict(result.artifact) if isinstance(result.artifact, dict) else {}
    artifact["validated_arguments"] = dict(args)
    return result.model_copy(update={"artifact": artifact})


def _latest_human_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return _message_text(message)
    return ""


def _has_explicit_cms(messages: list[BaseMessage]) -> bool:
    was_stated, level = explicit_cms_intent(messages)
    return was_stated and level is not None


def _intake_prompt(messages: list[BaseMessage]) -> str | None:
    facts = _accumulated_eligibility_args(messages)
    latest = _latest_tool_message(messages, "eligibility_check")
    payload = _tool_payload(latest[1]) if latest is not None else None
    if not facts and payload is None:
        return None

    visible_facts = {
        field: value
        for field, value in facts.items()
        if field in _ELIGIBILITY_FIELDS and not _is_missing(field, value)
    }
    lines = [
        "跨輪資料蒐集保護（不是資格或金額結論）：",
        "先前模型已送進資格工具的非空欄位如下："
        + json.dumps(visible_facts, ensure_ascii=False, sort_keys=True),
        f"本次必須使用的規則版本：{_desired_rule_version(messages)}。",
    ]
    cms_was_stated, cms_level = explicit_cms_intent(messages)
    if cms_was_stated and cms_level is None:
        lines.append(
            "使用者已明確表示尚未取得正式 CMS；official_cms_level 必須維持 null，"
            "不得呼叫 copay_estimate、不得從 CMS 2 至 8 級參考範圍猜個人等級。"
        )
    if payload and payload.get("status") == "INSUFFICIENT_INFORMATION":
        missing = [
            _FIELD_LABELS.get(str(field), str(field))
            for field in payload.get("missing_fields", [])
        ]
        lines.extend(
            [
                "上一次 eligibility_check 仍缺少：" + "、".join(missing) + "。",
                "若最新使用者訊息補了其中任何欄位，必須先重新呼叫 eligibility_check，"
                "並同時帶上先前非空欄位；不得先呼叫 copay_estimate 或 build_report_draft。",
                "若仍缺資料，只追問尚未提供的欄位。",
            ]
        )
    return "\n".join(lines)


def _missing_followup(messages: list[BaseMessage], payload: dict[str, Any]) -> str:
    missing_fields = [str(field) for field in payload.get("missing_fields", [])]
    if not missing_fields:
        return "請補充尚未提供的資格初篩資料。"

    # 工具回傳的 missing_fields 可能仍含使用者剛在同一輪補上的欄位。
    # 先以完整對話重新擷取明確事實，避免把已回答內容再次列入問題。
    explicit_facts = {
        **_explicit_eligibility_facts(messages),
        **_explicit_copay_facts(messages),
    }
    unanswered = [field for field in missing_fields if field not in explicit_facts]
    if not unanswered:
        return "我已記下這些資料，正在重新檢查資格初篩條件。"

    # 一次只追問一組相近資訊，避免把整張表單反覆丟回給使用者。
    question_groups = (
        ("age",),
        ("has_functional_impairment", "impairment_duration_months"),
        ("residence_status",),
        (
            "indigenous",
            "has_disability_certificate",
            "has_dementia_diagnosis",
            "is_pac_case",
        ),
        ("official_cms_level",),
    )
    selected: list[str] = []
    for group in question_groups:
        selected = [field for field in group if field in unanswered]
        if selected:
            break
    if not selected:
        selected = unanswered[:2]

    missing = [_FIELD_LABELS.get(field, field) for field in selected]
    return (
        "請先補充：" + "；".join(missing) + "。"
        "先回答這一組即可；不知道的項目可直接說不知道。"
    )


class CaseIntakeMiddleware(AgentMiddleware):
    """保留已抽取欄位、強制現制預設，並阻止跨階段工具跳躍。"""

    state_schema = CaseIntakeState

    def before_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        """在工具節點前保存該輪明確事實，避免不同節點的訊息視圖不一致。"""

        del runtime
        messages = _messages_from_state(state)
        if not messages:
            return None
        eligibility = state.get("case_explicit_eligibility_facts", {})
        copay = state.get("case_explicit_copay_facts", {})
        eligibility = dict(eligibility) if isinstance(eligibility, dict) else {}
        copay = dict(copay) if isinstance(copay, dict) else {}
        eligibility.update(_explicit_eligibility_facts(messages))
        copay.update(_explicit_copay_facts(messages))
        return {
            "case_explicit_eligibility_facts": eligibility,
            "case_explicit_copay_facts": copay,
        }

    def wrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], Any]) -> Any:
        prompt = _intake_prompt(request.messages)
        guarded_request = request
        if prompt:
            guarded_request = _request_with_added_system_prompt(request, prompt)
        response = handler(guarded_request)
        retry_prompt = (
            None
            if _response_has_tool_calls(response)
            else _initial_eligibility_retry_prompt(guarded_request)
        )
        if retry_prompt is not None:
            retry_request = _initial_retry_request(guarded_request, retry_prompt)
            response = handler(retry_request)
            response = _normalize_explicit_tool_call_content(
                response, allowed_tools={"eligibility_check"}
            )
            guarded_request = retry_request
        return _guard_model_response(guarded_request, response)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[Any]],
    ) -> Any:
        prompt = _intake_prompt(request.messages)
        guarded_request = request
        if prompt:
            guarded_request = _request_with_added_system_prompt(request, prompt)
        response = await handler(guarded_request)
        retry_prompt = (
            None
            if _response_has_tool_calls(response)
            else _initial_eligibility_retry_prompt(guarded_request)
        )
        if retry_prompt is not None:
            retry_request = _initial_retry_request(guarded_request, retry_prompt)
            response = await handler(retry_request)
            response = _normalize_explicit_tool_call_content(
                response, allowed_tools={"eligibility_check"}
            )
            guarded_request = retry_request
        return _guard_model_response(guarded_request, response)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        guarded = _guard_tool_call(request)
        if isinstance(guarded, ToolMessage):
            return guarded
        return _attach_validated_arguments(guarded, handler(guarded))

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        guarded = _guard_tool_call(request)
        if isinstance(guarded, ToolMessage):
            return guarded
        return _attach_validated_arguments(guarded, await handler(guarded))

    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        del runtime
        messages = _messages_from_state(state)
        if not messages or not isinstance(messages[-1], AIMessage):
            return None
        latest_response = messages[-1]
        if latest_response.tool_calls or _message_text(latest_response).strip():
            return None

        current = _current_turn(messages)
        eligibility = _latest_tool_message(current, "eligibility_check")
        payload = _tool_payload(eligibility[1]) if eligibility is not None else None
        if not payload or payload.get("status") != "INSUFFICIENT_INFORMATION":
            return None
        return {"messages": [AIMessage(content=_missing_followup(messages, payload))]}


__all__ = [
    "CaseIntakeMiddleware",
    "CaseIntakeState",
    "explicit_cms_intent",
    "merge_explicit_case_facts",
]
