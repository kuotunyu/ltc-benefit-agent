"""Deterministic semantic extractors for approved HTML and PDF sources."""

from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser
from io import BytesIO
from typing import Any, Callable, Final, Mapping

from .models import RuleSourceManifest


class ExtractionUnavailableError(RuntimeError):
    """The supplied document cannot be read as its declared format."""


class ExtractionReviewRequiredError(RuntimeError):
    """The document is readable but required semantic structure has drifted."""


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._suppressed_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._suppressed_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._suppressed_depth = max(0, self._suppressed_depth - 1)

    def handle_data(self, data: str) -> None:
        if not self._suppressed_depth:
            self.parts.append(data)


def _normalise_text(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def _html_text(content: bytes) -> str:
    try:
        decoded = content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ExtractionUnavailableError("HTML is not valid UTF-8") from exc
    parser = _VisibleTextParser()
    try:
        parser.feed(decoded)
    except Exception as exc:  # HTMLParser can surface malformed declarations.
        raise ExtractionUnavailableError("HTML parser could not read source") from exc
    text = _normalise_text(" ".join(parser.parts))
    if not text:
        raise ExtractionUnavailableError("HTML source contains no readable text")
    return text


_CHINESE_DIGITS: Final[Mapping[str, int]] = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_CHINESE_UNITS: Final[Mapping[str, int]] = {"十": 10, "百": 100, "千": 1000}


def chinese_numeral_to_int(value: str) -> int:
    """Parse the small Chinese numerals used by these regulations."""

    if not value:
        raise ValueError("Chinese numeral cannot be empty")
    total = 0
    current = 0
    for character in value:
        if character in _CHINESE_DIGITS:
            current = _CHINESE_DIGITS[character]
            continue
        unit = _CHINESE_UNITS.get(character)
        if unit is None:
            raise ValueError(f"Unsupported Chinese numeral character: {character}")
        total += (current or 1) * unit
        current = 0
    return total + current


def _article(text: str, number: int) -> str:
    match = re.search(
        rf"第\s*{number}\s*條(.*?)(?=第\s*{number + 1}\s*條|$)",
        text,
    )
    if match is None:
        raise ExtractionReviewRequiredError(f"Missing Article {number}")
    return match.group(1)


def _amended_on(text: str) -> str:
    match = re.search(
        r"修正日期\s*[:：]\s*民國\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日",
        text,
    )
    if match is None:
        raise ExtractionReviewRequiredError("Missing regulation amendment date")
    year, month, day = (int(part) for part in match.groups())
    return f"{year + 1911:04d}-{month:02d}-{day:02d}"


def _age_thresholds(article_two: str) -> list[int]:
    values = re.findall(r"([〇零一二三四五六七八九十百]+)歲以上", article_two)
    try:
        return [chinese_numeral_to_int(value) for value in values]
    except ValueError as exc:
        raise ExtractionReviewRequiredError("Unrecognised age threshold") from exc


def _percentage(article_ten: str) -> int:
    match = re.search(r"百分之([〇零一二三四五六七八九十百]+)", article_ten)
    if match is None:
        raise ExtractionReviewRequiredError("Missing foreign-caregiver percentage")
    return chinese_numeral_to_int(match.group(1))


def _require(text: str, phrase: str, field: str) -> None:
    if phrase not in text:
        raise ExtractionReviewRequiredError(f"Missing required field: {field}")


def extract_current_regulation(content: bytes) -> dict[str, Any]:
    text = _html_text(content)
    _require(text, "長期照顧服務申請及給付辦法", "regulation title")
    article_two = _article(text, 2)
    article_ten = _article(text, 10)
    article_twenty_two = _article(text, 22)
    ages = _age_thresholds(article_two)
    if len(ages) < 2:
        raise ExtractionReviewRequiredError("Eligibility age table is incomplete")
    _require(article_two, "領有身心障礙證明", "disability eligibility")
    _require(article_two, "失智症", "dementia eligibility")
    _require(article_two, "急性後期整合照護計畫", "PAC eligibility")
    _require(article_two, "全日住宿式服務", "full-day residential exclusion")
    _require(article_two, "團體家屋服務", "group-home exclusion")
    _require(article_ten, "居家照顧服務以外", "foreign-caregiver usage scope")
    for phrase, field in (
        ("一百十四年九月一日", "general effective date"),
        ("一百十五年一月一日", "dementia/PAC effective date"),
        ("一百十五年七月一日", "final attachment effective date"),
    ):
        _require(article_twenty_two, phrase, field)
    return {
        "amended_on": _amended_on(text),
        "eligibility": {
            "minimum_age": ages[0],
            "indigenous_minimum_age": ages[1],
            "disability_certificate": True,
            "dementia_minimum_age": None,
            "pac_eligible": True,
        },
        "excluded_residences": ["FULL_DAY_RESIDENTIAL", "GROUP_HOME"],
        "foreign_caregiver": {
            "quota_percent": _percentage(article_ten),
            "usage_scope": "NON_HOME_CARE_COMBINATIONS",
        },
        "staged_effective_dates": {
            "general": "2025-09-01",
            "dementia_pac_foreign": "2026-01-01",
            "final_attachments": "2026-07-01",
        },
    }


def extract_legacy_regulation(content: bytes) -> dict[str, Any]:
    text = _html_text(content)
    _require(text, "長期照顧服務申請及給付辦法", "regulation title")
    article_two = _article(text, 2)
    article_ten = _article(text, 10)
    ages = _age_thresholds(article_two)
    if len(ages) < 3:
        raise ExtractionReviewRequiredError("Legacy eligibility age table is incomplete")
    _require(article_two, "領有身心障礙證明", "disability eligibility")
    _require(article_two, "失智症", "dementia eligibility")
    _require(article_two, "住宿式機構", "residential exclusion")
    _require(article_ten, "專業服務照顧組合", "foreign-caregiver usage scope")
    _require(text, "一百十一年二月一日", "snapshot effective date")
    return {
        "amended_on": _amended_on(text),
        "eligibility": {
            "minimum_age": ages[0],
            "indigenous_minimum_age": ages[1],
            "disability_certificate": True,
            "dementia_minimum_age": ages[2],
            "pac_eligible": False,
        },
        "excluded_residences": ["RESIDENTIAL_INSTITUTION"],
        "foreign_caregiver": {
            "quota_percent": _percentage(article_ten),
            "usage_scope": "PROFESSIONAL_SERVICE_ONLY",
        },
        "snapshot_effective_date": "2022-02-01",
    }


def extract_quota_numbers_from_text(text: str) -> dict[str, Any]:
    """Extract the official Attachment 2 amount vector from PDF text."""

    tokens = [
        int(value.replace(",", ""))
        for value in re.findall(r"(?<!\d)\d{1,3}(?:,\d{3})+(?!\d)", text)
    ]
    if len(tokens) != 15:
        raise ExtractionReviewRequiredError(
            f"Quota table shape changed: expected 15 amounts, found {len(tokens)}"
        )
    quota_positions = (0, 8, 9, 10, 11, 12, 14)
    quotas = {str(level): tokens[index] for level, index in zip(range(2, 9), quota_positions)}
    return {
        "all_amounts_in_table_order": tokens,
        "care_and_professional_monthly": quotas,
    }


def extract_copay_numbers_from_text(text: str) -> dict[str, Any]:
    """Extract the official Attachment 5 percentage matrix from PDF text."""

    tokens = [
        int(value)
        for value in re.findall(r"(?<![\d,])\d{1,2}(?![\d,])", text)
    ]
    if len(tokens) != 21:
        raise ExtractionReviewRequiredError(
            f"Copay table shape changed: expected 21 percentages, found {len(tokens)}"
        )
    labels = (
        "care_and_professional",
        "transport_region_1",
        "transport_region_2",
        "transport_region_3",
        "transport_region_4",
        "assistive_and_home_accessibility",
        "respite",
    )
    matrix = {
        label: tokens[index : index + 3]
        for label, index in zip(labels, range(0, len(tokens), 3))
    }
    return {"percentage_matrix": matrix, "all_percentages_in_table_order": tokens}


def _pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ExtractionUnavailableError(
            "PDF audit dependency is unavailable; install the audit dependency group"
        ) from exc
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            decrypted = reader.decrypt("")
            if not decrypted:
                raise ExtractionUnavailableError("PDF is encrypted")
        pages = [page.extract_text() or "" for page in reader.pages]
    except ExtractionUnavailableError:
        raise
    except Exception as exc:
        raise ExtractionUnavailableError("PDF parser could not read source") from exc
    text = "\n".join(pages)
    if not text.strip():
        raise ExtractionUnavailableError("PDF contains no extractable text")
    return text


def extract_quota_pdf(content: bytes) -> dict[str, Any]:
    return extract_quota_numbers_from_text(_pdf_text(content))


def extract_copay_pdf(content: bytes) -> dict[str, Any]:
    return extract_copay_numbers_from_text(_pdf_text(content))


EXTRACTORS: Final[
    Mapping[str, tuple[str, Callable[[bytes], dict[str, Any]]]]
] = {
    "legacy-regulation-html": ("legacy-regulation-html-v1", extract_legacy_regulation),
    "current-regulation-html": ("current-regulation-html-v1", extract_current_regulation),
    "care-professional-quota-pdf": ("care-professional-quota-pdf-v1", extract_quota_pdf),
    "copay-percentages-pdf": ("copay-percentages-pdf-v1", extract_copay_pdf),
}


def extract_semantics(
    manifest: RuleSourceManifest,
    content: bytes,
) -> dict[str, Any]:
    registered = EXTRACTORS.get(manifest.extractor_id)
    if registered is None:
        raise ExtractionReviewRequiredError(
            f"Unknown extractor_id: {manifest.extractor_id}"
        )
    extractor_version, extractor = registered
    if extractor_version != manifest.extractor_version:
        raise ExtractionReviewRequiredError(
            "Extractor version differs from the approved manifest"
        )
    return extractor(content)
