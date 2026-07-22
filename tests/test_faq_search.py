from __future__ import annotations

from dataclasses import asdict, dataclass

import pytest

from ltc_benefit_agent.tools import faq_search
from ltc_benefit_agent.tools.faq_search import (
    FaqBackendUnavailable,
    FaqSearchResult,
    search_faq,
    search_faq_standalone,
)


@dataclass
class FakeChunk:
    text: str
    law_name: str
    article_no: str
    url: str


class FakeRetriever:
    def retrieve(self, query: str) -> list[FakeChunk]:
        assert query == "外籍看護可以用多少額度"
        return [
            FakeChunk(
                text="外籍家庭看護相關規定",
                law_name="長期照顧服務申請及給付辦法",
                article_no="10",
                url="https://example.test/law/10",
            )
        ]


@pytest.mark.parametrize(
    ("query", "expected_article"),
    [
        ("幾歲可以申請長照資格", "第 2 條"),
        ("失能要持續六個月嗎", "第 3 條"),
        ("CMS 失能等級和額度", "第 7 條及附表二"),
        ("外籍看護可以申請嗎", "第 10 條"),
        ("一般戶的部分負擔自付比例", "第 14 條及附表五"),
        ("怎麼打 1966 申請流程", "申請流程"),
    ],
)
def test_standalone_faq_hits_expected_rule(
    query: str, expected_article: str
) -> None:
    results = search_faq_standalone(query)
    assert results
    assert results[0].article == expected_article
    assert results[0].url.startswith("https://")


def test_standalone_faq_returns_empty_for_no_match() -> None:
    assert search_faq_standalone("火星天氣與潮汐") == []


def test_injected_twlongcare_adapter_returns_common_schema() -> None:
    results = search_faq(
        "外籍看護可以用多少額度", retriever=FakeRetriever(), limit=1
    )
    assert len(results) == 1
    assert isinstance(results[0], FaqSearchResult)
    assert set(asdict(results[0])) == {
        "title",
        "article",
        "excerpt",
        "url",
        "data_version",
    }
    assert results[0].article == "10"


def test_auto_mode_falls_back_when_twlongcare_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(faq_search, "_create_twlongcare_retriever", lambda: None)
    results = search_faq("申請流程")
    assert results[0].article == "申請流程"


def test_auto_mode_uses_available_twlongcare_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        faq_search, "_create_twlongcare_retriever", lambda: FakeRetriever()
    )
    results = search_faq("外籍看護可以用多少額度")
    assert results[0].data_version == "twlongcare external index"


def test_backend_initialization_error_is_not_silently_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail() -> None:
        raise FaqBackendUnavailable("broken index")

    monkeypatch.setattr(faq_search, "_create_twlongcare_retriever", fail)
    with pytest.raises(FaqBackendUnavailable):
        search_faq("申請流程")


@pytest.mark.parametrize("query", ["", "   ", "---"])
def test_empty_query_is_rejected(query: str) -> None:
    with pytest.raises(ValueError):
        search_faq_standalone(query)


@pytest.mark.parametrize("limit", [0, 21, -1])
def test_invalid_limit_is_rejected(limit: int) -> None:
    with pytest.raises(ValueError):
        search_faq_standalone("申請", limit=limit)


def test_limit_and_excerpt_bounds() -> None:
    results = search_faq_standalone("申請資格與申請流程", limit=1)
    assert len(results) == 1
    assert len(results[0].excerpt) <= 350


def test_prefer_twlongcare_must_be_boolean() -> None:
    with pytest.raises(TypeError):
        search_faq("申請流程", prefer_twlongcare="yes")  # type: ignore[arg-type]
