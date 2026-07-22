"""只供瀏覽器 smoke 使用的零模型 Gradio fixture。"""

from __future__ import annotations

import os

from ltc_benefit_agent.agent.service import AgentTurnResult
from ltc_benefit_agent.ui.app import CSS, build_demo
from ltc_benefit_agent.ui.controller import GradioController


class EmptyReplyService:
    def send_message(self, thread_id: str, text: str) -> AgentTurnResult:
        del text
        return AgentTurnResult(thread_id, {"messages": []}, ())


def main() -> None:
    port = int(os.environ["GRADIO_SERVER_PORT"])
    controller = GradioController(
        service_factory=lambda provider: EmptyReplyService()  # type: ignore[arg-type]
    )
    build_demo(controller).queue().launch(
        server_name="127.0.0.1",
        server_port=port,
        css=CSS,
        footer_links=[],
    )


if __name__ == "__main__":
    main()
