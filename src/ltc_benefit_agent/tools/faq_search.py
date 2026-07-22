"""法源 FAQ 搜尋：可選姊妹作 adapter，否則使用零依賴 fallback。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from .rules import (
    APPLICATION_GUIDE_URL,
    CURRENT_COPAY_URL,
    CURRENT_REGULATION_URL,
    LONG_TERM_CARE_ACT_URL,
)


@dataclass(frozen=True, slots=True)
class FaqSearchResult:
    title: str
    article: str
    excerpt: str
    url: str
    data_version: str


@dataclass(frozen=True, slots=True)
class _FaqEntry:
    result: FaqSearchResult
    keywords: tuple[str, ...]


class _Retriever(Protocol):
    def retrieve(self, query: str) -> Sequence[Any]: ...


class FaqBackendUnavailable(RuntimeError):
    """姊妹作已存在但無法初始化時，避免靜默掩蓋環境問題。"""


_CURRENT_DATA_VERSION = "CURRENT_2026_07；查證日 2026-07-22"
_FAQ_CORPUS = (
    _FaqEntry(
        FaqSearchResult(
            title="長期照顧服務申請及給付辦法",
            article="第 2 條",
            excerpt=(
                "因身心失能，且符合六十五歲以上、五十五歲以上原住民、"
                "領有身心障礙證明、失智症或 PAC 收案對象之一者，可提出申請；"
                "全日住宿式服務與團體家屋使用者不適用本辦法。"
            ),
            url=CURRENT_REGULATION_URL,
            data_version=_CURRENT_DATA_VERSION,
        ),
        ("申請", "資格", "幾歲", "65歲", "55歲", "原住民", "身心障礙", "失智", "PAC"),
    ),
    _FaqEntry(
        FaqSearchResult(
            title="長期照顧服務法",
            article="第 3 條",
            excerpt="長照是針對身心失能持續已達或預期達六個月以上者提供的支持與照顧。",
            url=LONG_TERM_CARE_ACT_URL,
            data_version="長期照顧服務法；查證日 2026-07-22",
        ),
        ("六個月", "6個月", "長期", "失能多久", "持續期間"),
    ),
    _FaqEntry(
        FaqSearchResult(
            title="長期照顧服務申請及給付辦法",
            article="第 7 條及附表二",
            excerpt=(
                "正式評估分為第一至第八級；第一級不納入給付，第二至第八級"
                "依附表二取得各服務項目額度。"
            ),
            url=CURRENT_REGULATION_URL,
            data_version=_CURRENT_DATA_VERSION,
        ),
        ("CMS", "長照等級", "失能等級", "2級", "8級", "額度"),
    ),
    _FaqEntry(
        FaqSearchResult(
            title="長期照顧服務申請及給付辦法",
            article="第 10 條",
            excerpt=(
                "聘僱外國家庭幫傭、家庭看護或中階技術家庭看護等情形，"
                "照顧及專業服務額度為附表二額度的百分之三十，並受服務組合限制。"
            ),
            url=CURRENT_REGULATION_URL,
            data_version=_CURRENT_DATA_VERSION,
        ),
        ("外籍看護", "外看", "家庭看護", "家庭幫傭", "30%", "百分之三十"),
    ),
    _FaqEntry(
        FaqSearchResult(
            title="長期照顧服務申請及給付辦法",
            article="第 14 條及附表五",
            excerpt=(
                "照顧及專業服務部分負擔比率依第一、第二、第三類為 0%、5%、16%；"
                "部分負擔費用小數點後無條件捨去。"
            ),
            url=CURRENT_COPAY_URL,
            data_version=_CURRENT_DATA_VERSION,
        ),
        ("部分負擔", "自付", "低收入", "中低收入", "一般戶", "第一類", "第二類", "第三類"),
    ),
    _FaqEntry(
        FaqSearchResult(
            title="1966 長照專區申請指引",
            article="申請流程",
            excerpt=(
                "可撥打 1966、聯絡所在地照管中心、透過出院準備小組或線上申請；"
                "後續由照管專員評估並擬定照顧計畫。"
            ),
            url=APPLICATION_GUIDE_URL,
            data_version="1966 長照專區；查證日 2026-07-22",
        ),
        ("1966", "怎麼申請", "申請流程", "照管中心", "到府評估", "照管專員"),
    ),
)


def _normalize(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.casefold())


def _validate_query(query: str, limit: int) -> str:
    if not isinstance(query, str):
        raise TypeError("query 必須是字串")
    normalized = _normalize(query)
    if not normalized:
        raise ValueError("query 不得為空")
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError("limit 必須是整數")
    if not 1 <= limit <= 20:
        raise ValueError("limit 必須介於 1 與 20")
    return normalized


def search_faq_standalone(query: str, *, limit: int = 5) -> list[FaqSearchResult]:
    """用關鍵詞做可重現的本地搜尋；查無結果回空 list。"""

    normalized_query = _validate_query(query, limit)
    scored: list[tuple[int, int, FaqSearchResult]] = []
    for index, entry in enumerate(_FAQ_CORPUS):
        score = sum(
            len(normalized_keyword)
            for keyword in entry.keywords
            if (normalized_keyword := _normalize(keyword)) in normalized_query
        )
        if score:
            scored.append((score, -index, entry.result))
    scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
    return [item[2] for item in scored[:limit]]


def _create_twlongcare_retriever() -> _Retriever | None:
    try:
        from twlongcare.retriever import HybridRetriever
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.split(".")[0] == "twlongcare":
            return None
        raise FaqBackendUnavailable("twlongcare 的相依套件不完整") from exc
    try:
        return HybridRetriever()
    except Exception as exc:  # pragma: no cover - 真實模型／索引環境才會觸發
        raise FaqBackendUnavailable("twlongcare 已安裝但 HybridRetriever 初始化失敗") from exc


def _search_with_retriever(
    query: str, retriever: _Retriever, limit: int
) -> list[FaqSearchResult]:
    normalized_query = _validate_query(query, limit)
    del normalized_query
    chunks = retriever.retrieve(query)
    results: list[FaqSearchResult] = []
    for chunk in chunks[:limit]:
        text = str(getattr(chunk, "text", "")).strip()
        if not text:
            continue
        results.append(
            FaqSearchResult(
                title=str(getattr(chunk, "law_name", "法規資料")),
                article=str(getattr(chunk, "article_no", "")),
                excerpt=text[:350],
                url=str(getattr(chunk, "url", "")),
                data_version="twlongcare external index",
            )
        )
    return results


def search_faq(
    query: str,
    *,
    limit: int = 5,
    retriever: _Retriever | None = None,
    prefer_twlongcare: bool = True,
) -> list[FaqSearchResult]:
    """搜尋法源；注入 retriever 時可直接重用姊妹作而不綁定其安裝路徑。"""

    if not isinstance(prefer_twlongcare, bool):
        raise TypeError("prefer_twlongcare 必須是 bool")
    selected_retriever = retriever
    if selected_retriever is None and prefer_twlongcare:
        selected_retriever = _create_twlongcare_retriever()
    if selected_retriever is not None:
        return _search_with_retriever(query, selected_retriever, limit)
    return search_faq_standalone(query, limit=limit)
