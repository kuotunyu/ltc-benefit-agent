"""不依賴 LLM 的長照規則工具。"""

from .copay import (
    CalculationBasis,
    CopayInput,
    CopayResult,
    QuotaReferenceRow,
    WelfareCategory,
    calculate_copay,
    get_quota_reference_table,
)
from .eligibility import (
    EligibilityBasis,
    EligibilityInput,
    EligibilityResult,
    EligibilityStatus,
    ResidenceStatus,
    assess_eligibility,
)
from .faq_search import FaqSearchResult, search_faq, search_faq_standalone
from .rules import RuleSnapshot, RuleVersion, get_rule_snapshot

__all__ = [
    "CalculationBasis",
    "CopayInput",
    "CopayResult",
    "EligibilityBasis",
    "EligibilityInput",
    "EligibilityResult",
    "EligibilityStatus",
    "FaqSearchResult",
    "QuotaReferenceRow",
    "ResidenceStatus",
    "RuleSnapshot",
    "RuleVersion",
    "WelfareCategory",
    "assess_eligibility",
    "calculate_copay",
    "get_quota_reference_table",
    "get_rule_snapshot",
    "search_faq",
    "search_faq_standalone",
]
