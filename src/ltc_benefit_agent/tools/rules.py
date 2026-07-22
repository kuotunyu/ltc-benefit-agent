"""長照規則快照與共同常數。

只保存兩個明確版本，不依目前日期自動切換，避免同一輸入在不同日期得到
無法重現的結果。所有 URL 與查證日都隨結果回傳。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Mapping


class RuleVersion(StrEnum):
    """本專案支援的固定法規快照。"""

    LEGACY_2022 = "LEGACY_2022"
    CURRENT_2026_07 = "CURRENT_2026_07"


@dataclass(frozen=True, slots=True)
class RuleSnapshot:
    version: RuleVersion
    label: str
    effective_date: date
    verified_on: date
    regulation_url: str
    quota_url: str
    copay_url: str
    notes: tuple[str, ...]


LEGACY_REGULATION_URL: Final = (
    "https://law.moj.gov.tw/LawClass/LawOldVer.aspx?"
    "lnndate=20220120&lser=001&pcode=L0070059"
)
CURRENT_REGULATION_URL: Final = (
    "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0070059"
)
CURRENT_QUOTA_URL: Final = (
    "https://law.moj.gov.tw/LawClass/LawGetFile.ashx?"
    "FileId=0000398330&lan=C"
)
CURRENT_COPAY_URL: Final = (
    "https://law.moj.gov.tw/LawClass/LawGetFile.ashx?"
    "FileId=0000398333&lan=C"
)
LONG_TERM_CARE_ACT_URL: Final = (
    "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0070040"
)
APPLICATION_GUIDE_URL: Final = (
    "https://1966.gov.tw/ltc/cp-6533-70777-207.html"
)

_VERIFIED_ON: Final = date(2026, 7, 22)

RULE_SNAPSHOTS: Final[Mapping[RuleVersion, RuleSnapshot]] = MappingProxyType(
    {
        RuleVersion.LEGACY_2022: RuleSnapshot(
            version=RuleVersion.LEGACY_2022,
            label="長期照顧服務申請及給付辦法（2022-02-01 快照）",
            effective_date=date(2022, 2, 1),
            verified_on=_VERIFIED_ON,
            regulation_url=LEGACY_REGULATION_URL,
            quota_url=LEGACY_REGULATION_URL,
            copay_url=LEGACY_REGULATION_URL,
            notes=(
                "失智症申請身分門檻為五十歲以上。",
                "不含急性後期整合照護計畫（PAC）收案對象。",
                "團體家屋依 2020 年主管機關函釋不列入給付對象。",
            ),
        ),
        RuleVersion.CURRENT_2026_07: RuleSnapshot(
            version=RuleVersion.CURRENT_2026_07,
            label="長期照顧服務申請及給付辦法（2026-07-01 完整快照）",
            effective_date=date(2026, 7, 1),
            verified_on=_VERIFIED_ON,
            regulation_url=CURRENT_REGULATION_URL,
            quota_url=CURRENT_QUOTA_URL,
            copay_url=CURRENT_COPAY_URL,
            notes=(
                "2025-06-19 修正內容原則自 2025-09-01 施行。",
                "失智症取消五十歲年齡門檻及 PAC 資格自 2026-01-01 施行。",
                "PAC 是短期照顧需求的明文擴充，不適用一般六個月門檻。",
                "最後一批附表修正自 2026-07-01 施行；版本名稱代表完整快照，"
                "不代表所有規則都在該日才生效。",
            ),
        ),
    }
)

# 來源：申請及給付辦法第 7 條附表二；2022 舊制與 2026-07 現制
# 的照顧及專業服務（B、C 碼）月額相同。查證日：2026-07-22。
_CARE_AND_PROFESSIONAL_QUOTAS: Final[Mapping[int, int]] = MappingProxyType(
    {2: 10_020, 3: 15_460, 4: 18_580, 5: 24_100, 6: 28_070, 7: 32_090, 8: 36_180}
)
CARE_AND_PROFESSIONAL_QUOTAS: Final[Mapping[RuleVersion, Mapping[int, int]]] = (
    MappingProxyType(
        {
            RuleVersion.LEGACY_2022: _CARE_AND_PROFESSIONAL_QUOTAS,
            RuleVersion.CURRENT_2026_07: _CARE_AND_PROFESSIONAL_QUOTAS,
        }
    )
)

# 來源：申請及給付辦法第 14 條附表五「照顧及專業服務」欄；
# 第一／第二／第三類依序為 0%、5%、16%，小數點後無條件捨去。
COPAY_PERCENTAGES: Final[Mapping[str, int]] = MappingProxyType(
    {"FIRST": 0, "SECOND": 5, "THIRD": 16}
)

# 來源：申請及給付辦法第 10 條。聘僱外國家庭幫傭、家庭看護或中階
# 技術家庭看護等情形，照顧及專業服務額度為附表二額度的 30%；該額度
# 僅能用於附表四居家照顧服務以外之照顧組合。
FOREIGN_CAREGIVER_QUOTA_PERCENT: Final = 30
FOREIGN_CAREGIVER_USAGE_NOTE: Final = (
    "外籍家庭看護等情形的 30% 額度依法僅能用於附表四居家照顧服務以外"
    "之照顧組合；本工具只試算額度與部分負擔，不判定個別服務碼是否適用。"
)

# 來源：長期照顧服務法第 3 條第 1 款；長照指失能已達或預期達六個月以上。
MIN_LONG_TERM_MONTHS: Final = 6


def get_rule_snapshot(version: RuleVersion) -> RuleSnapshot:
    if not isinstance(version, RuleVersion):
        raise TypeError("version 必須是 RuleVersion")
    return RULE_SNAPSHOTS[version]
