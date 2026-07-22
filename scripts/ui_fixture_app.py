"""只供瀏覽器 smoke 使用的零模型 Gradio fixture。"""

from __future__ import annotations

import os
from types import SimpleNamespace

from langchain_core.messages import AIMessage
from ltc_benefit_agent.agent.service import AgentTurnResult
from ltc_benefit_agent.ui.app import CSS, build_demo
from ltc_benefit_agent.ui.controller import GradioController


class EmptyReplyService:
    def send_message(self, thread_id: str, text: str) -> AgentTurnResult:
        del text
        return AgentTurnResult(thread_id, {"messages": []}, ())


REPORT = """# 長照服務資格與補助初步建議書

## 估算額度表

| 項目 | 金額 |
|---|---:|
| 政府給付 | NT$ 15,120 |
| 合計自付 | NT$ 2,880 |

## 引用來源

- [現行辦法](https://law.moj.gov.tw/)
"""


class ReportService:
    """提供完整 HITL 流程，但不載入或呼叫任何模型。"""

    def send_message(self, thread_id: str, text: str) -> AgentTurnResult:
        del text
        interrupt = SimpleNamespace(
            value={
                "action_requests": [
                    {
                        "name": "publish_report",
                        "args": {
                            "report_id": "fixture-report",
                            "report_markdown": REPORT,
                        },
                    }
                ]
            }
        )
        return AgentTurnResult(thread_id, {"messages": []}, (interrupt,))

    def decide(self, thread_id: str, decision: str) -> AgentTurnResult:
        content = REPORT if decision == "approve" else "草稿已拒絕"
        metadata = (
            {"deterministic_published_report": True}
            if decision == "approve"
            else {}
        )
        return AgentTurnResult(
            thread_id,
            {"messages": [AIMessage(content=content, additional_kwargs=metadata)]},
            (),
        )


def main() -> None:
    port = int(os.environ["GRADIO_SERVER_PORT"])
    service_type = ReportService if os.getenv("UI_FIXTURE_REPORT") == "1" else EmptyReplyService
    controller = GradioController(
        service_factory=lambda provider: service_type()  # type: ignore[arg-type]
    )
    build_demo(controller).queue().launch(
        server_name="127.0.0.1",
        server_port=port,
        css=CSS,
        footer_links=[],
    )


if __name__ == "__main__":
    main()
