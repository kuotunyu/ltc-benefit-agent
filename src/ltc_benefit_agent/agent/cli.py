"""多輪 CLI；含不需 API 的確定性展示模式。"""

from __future__ import annotations

import argparse
import sys
from uuid import uuid4

from ltc_benefit_agent.tools.copay import WelfareCategory
from ltc_benefit_agent.tools.eligibility import EligibilityInput, ResidenceStatus
from ltc_benefit_agent.tools.rules import RuleVersion

from .config import AgentProvider, AgentSettings
from .factory import build_agent_runtime
from .reports import ReportRegistry, render_report
from .service import BenefitAgentService


def offline_demo(*, approve: bool) -> int:
    markdown = render_report(
        eligibility_input=EligibilityInput(
            age=70,
            indigenous=False,
            has_disability_certificate=False,
            has_dementia_diagnosis=False,
            is_pac_case=False,
            has_functional_impairment=True,
            impairment_duration_months=6,
            residence_status=ResidenceStatus.COMMUNITY,
            official_cms_level=4,
            rule_version=RuleVersion.CURRENT_2026_07,
        ),
        welfare_category=WelfareCategory.THIRD,
        has_foreign_caregiver=False,
        planned_spend=12_000,
    )
    registry = ReportRegistry()
    draft = registry.register(markdown)
    print("=== 待人工確認的完整預覽 ===")
    print(draft.markdown)
    if not approve:
        print("\n未核准：最終報告未發布。")
        return 2
    published = registry.verify_and_publish(draft.report_id, draft.markdown)
    print("\n=== 已核准最終報告 ===")
    print(published)
    return 0


def interactive(provider: AgentProvider) -> int:
    settings = AgentSettings.from_env(provider=provider)
    service = BenefitAgentService(build_agent_runtime(settings=settings))
    thread_id = str(uuid4())
    print("長照初步評估 CLI。請勿輸入姓名、身分證、電話或地址；輸入 /quit 結束。")
    while True:
        try:
            user_text = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        if user_text == "/quit":
            return 0
        turn = service.send_message(thread_id, user_text)
        if turn.awaiting_approval:
            print("\n=== 待人工確認的完整預覽 ===")
            print(turn.pending_report_preview or "（預覽缺失，請拒絕）")
            decision = input("輸入 approve 或 reject：").strip().lower()
            if decision not in {"approve", "reject"}:
                print("決策無效，本次保持暫停。")
                continue
            turn = service.decide(thread_id, decision)  # type: ignore[arg-type]
        if turn.latest_text:
            print(f"Agent：{turn.latest_text}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ltc-benefit-agent CLI")
    parser.add_argument(
        "--provider",
        choices=[item.value for item in AgentProvider],
        default=AgentProvider.GEMINI.value,
    )
    parser.add_argument("--offline-demo", action="store_true")
    parser.add_argument("--approve", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.offline_demo:
        return offline_demo(approve=args.approve)
    return interactive(AgentProvider(args.provider))


if __name__ == "__main__":
    sys.exit(main())
