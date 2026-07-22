"""帶人工校閱台的 Gradio Blocks 介面。"""

from __future__ import annotations

import os
import socket
from uuid import uuid4

import gradio as gr

from .controller import GradioController, UiResponse, provider_choices


CSS = """
:root {
  --page: #eef3f1;
  --surface: #ffffff;
  --surface-muted: #e5efeb;
  --surface-tint: #f7faf8;
  --ink: #17211d;
  --ink-soft: #4b5d55;
  --accent: #185a45;
  --accent-hover: #114735;
  --accent-soft: #dcebe5;
  --accent-ink: #0d4634;
  --line: #cddbd5;
  --line-strong: #aabfb6;
  --focus: #1d7256;
  --radius-control: 10px;
  --radius-panel: 12px;
  --shadow-raised: 0 2px 7px rgba(23, 33, 29, .08);
  --checkbox-background-color-selected: var(--accent);
  --checkbox-border-color-selected: var(--accent);
  --checkbox-label-background-fill-selected: transparent;
  --checkbox-label-border-color-selected: transparent;
  --checkbox-label-text-color-selected: var(--ink);
}
.gradio-container {
  min-height: 100vh;
  gap: 0 !important;
  background: var(--page);
  color: var(--ink);
  font-family: "Noto Sans TC", "Microsoft JhengHei", system-ui, sans-serif !important;
  font-size: 19px !important;
}
.gradio-container main.contain > .column { gap: 0 !important; }
.app-shell {
  width: min(1180px, calc(100% - 32px));
  margin-inline: auto !important;
}
.header-wrap {
  margin: 0 !important;
  padding: 0 !important;
}
.header-wrap .html-container,
.main-surface > .block:first-child .html-container {
  padding: 0 !important;
}
.app-header {
  padding: 24px 2px 14px;
  border-bottom: 1px solid var(--line);
}
.app-header h1 {
  margin: 0;
  color: var(--accent-ink);
  font-size: 34px;
  line-height: 1.2;
  letter-spacing: -.02em;
  text-wrap: balance;
}
.main-surface {
  gap: 12px !important;
  margin-bottom: 18px !important;
  padding: 10px 0 0 !important;
}
#onboarding-section {
  gap: 12px !important;
}
.how-to {
  margin: 0;
  padding: 16px 18px;
  border: 1px solid var(--line);
  border-radius: var(--radius-panel);
  background: var(--surface-muted);
}
.how-to h2 {
  margin: 0 0 8px;
  font-size: 22px !important;
}
.how-to ol {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 24px;
  margin: 0;
  padding-left: 24px;
}
.how-to li {
  padding-left: 3px;
  color: var(--ink);
  font-size: 19px;
  line-height: 1.55;
}
.how-to li::marker {
  color: var(--accent);
  font-weight: 700;
}
.how-to .privacy-line {
  margin: 10px 0 0;
  color: var(--ink-soft);
  font-size: 18px;
  line-height: 1.5;
}
.report-section {
  gap: 20px !important;
  margin-bottom: 28px !important;
  padding: 20px 0 0 !important;
  border-top: 1px solid var(--line);
}
.control-bar {
  align-items: center;
  gap: 14px;
}
.control-bar .form {
  border: 0 !important;
  background: transparent !important;
}
.control-bar .block {
  margin: 0 !important;
}
#provider-select,
#legacy-toggle {
  padding: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}
#provider-select input,
#provider-select [role="combobox"],
body [role="option"],
body .options li {
  font-size: 19px !important;
  line-height: 1.5 !important;
}
#provider-select [role="combobox"] {
  min-height: 52px !important;
}
#legacy-toggle label {
  display: flex !important;
  align-items: center !important;
  gap: 10px !important;
  min-height: 52px;
  margin: 0 !important;
}
#legacy-toggle label,
#legacy-toggle label span,
#legacy-toggle [data-testid="block-info"] {
  color: var(--ink) !important;
  font-size: 1.25rem !important;
  font-weight: 700 !important;
  line-height: 1.4 !important;
}
#legacy-toggle input[type="checkbox"] {
  flex: 0 0 22px;
  width: 22px !important;
  height: 22px !important;
  min-height: 22px !important;
  margin: 0 !important;
}
#restart-button {
  flex: 0 0 auto !important;
  width: auto !important;
  min-height: 48px;
  padding-inline: 18px !important;
  background: var(--surface) !important;
  border: 2px solid var(--accent) !important;
  border-radius: var(--radius-control) !important;
  color: var(--accent-ink) !important;
  font-weight: 700 !important;
  transition: background-color 180ms cubic-bezier(.22, 1, .36, 1),
    color 180ms cubic-bezier(.22, 1, .36, 1),
    transform 180ms cubic-bezier(.22, 1, .36, 1);
}
#restart-button:hover {
  background: var(--accent-soft) !important;
}
#restart-button:active {
  transform: translateY(1px);
}
#advanced-settings {
  margin: 0 !important;
  overflow: hidden !important;
  background: transparent !important;
}
.conversation-panel {
  gap: 10px !important;
  margin-top: 2px !important;
}
.conversation-panel h3 { margin-bottom: 0 !important; }
.conversation-header {
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.conversation-header .prose { flex: 1 1 auto; }
#current-question {
  overflow: visible !important;
  padding: 20px 22px !important;
  border: 1px solid var(--line-strong) !important;
  border-radius: var(--radius-panel) !important;
  background: var(--surface-tint) !important;
  box-shadow: var(--shadow-raised) !important;
}
#current-question .prose {
  max-width: none;
  color: var(--ink) !important;
  opacity: 1 !important;
}
#current-question .prose * { color: var(--ink) !important; opacity: 1 !important; }
#current-question p,
#current-question li {
  margin-block: 0 10px !important;
  color: var(--ink) !important;
  font-size: 20px !important;
  line-height: 1.75 !important;
  text-wrap: pretty;
}
#current-question p:last-child,
#current-question li:last-child { margin-bottom: 0 !important; }
.followup-helper {
  margin: 0 !important;
  padding: 0 2px !important;
  color: var(--ink-soft);
}
.followup-helper p {
  margin: 0 !important;
  font-size: 18px !important;
  line-height: 1.5 !important;
}
.followup-composer {
  align-items: flex-end;
  gap: 10px;
  margin-top: 0 !important;
  padding: 0;
  border: 0;
  background: transparent;
}
#current-question,
.followup-helper,
.followup-composer,
#history-section,
.status-strip {
  width: 100% !important;
  max-width: 920px !important;
  align-self: flex-start !important;
}
.gradio-container .gr-accordion > button.label-wrap,
.gradio-container .gr-accordion > button.label-wrap * {
  color: var(--ink) !important;
  font-size: 19px !important;
  line-height: 1.45 !important;
}
.gradio-container .gr-accordion > button.label-wrap {
  min-height: 50px;
  padding: 12px 14px !important;
}
#history-section {
  margin: 0 !important;
  overflow: hidden !important;
  border: 1px solid var(--line) !important;
  border-radius: var(--radius-control) !important;
  background: var(--surface) !important;
}
#history-section .gr-accordion {
  overflow: hidden !important;
  border: 0 !important;
  border-radius: 0 !important;
  background: var(--surface) !important;
}
#history-section .gr-accordion > button.label-wrap,
#history-section .gr-accordion > button.label-wrap * {
  color: var(--accent-ink) !important;
  font-size: 20px !important;
  font-weight: 700 !important;
  line-height: 1.4 !important;
}
#history-section .gr-accordion > button.label-wrap {
  min-height: 54px;
  padding: 13px 16px !important;
  transition: background-color 180ms cubic-bezier(.22, 1, .36, 1);
}
#history-section .gr-accordion > button.label-wrap:hover {
  background: var(--accent-soft) !important;
}
#conversation {
  border: 0 !important;
  border-radius: 0 !important;
  background: var(--surface-tint) !important;
}
#conversation .message {
  border-radius: var(--radius-control) !important;
  box-shadow: none !important;
  font-size: 19px !important;
  line-height: 1.65 !important;
}
#conversation .message-row,
#conversation .message-wrap {
  padding-block: 6px !important;
}
#conversation .placeholder {
  color: var(--ink-soft) !important;
  font-size: 19px !important;
}
.composer-row {
  align-items: flex-end;
  gap: 10px;
}
#start-input textarea,
#followup-input textarea {
  border-radius: var(--radius-control) !important;
}
#start-input [data-testid="block-info"],
#followup-input [data-testid="block-info"] {
  color: var(--ink) !important;
  font-size: 20px !important;
  font-weight: 700 !important;
}
#report-preview {
  min-height: 90px;
  max-height: 600px;
  overflow: auto;
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
}
#report-preview table, #details-panel table { width: 100%; }
#report-preview p,
#report-preview li,
#report-preview td,
#report-preview th,
#details-panel,
.gradio-container .prose p,
.gradio-container .prose li {
  font-size: 19px !important;
  line-height: 1.65 !important;
}
.gradio-container h2 { font-size: 26px !important; line-height: 1.3; }
.gradio-container h3 { font-size: 21px !important; line-height: 1.35; }
.gradio-container label,
.gradio-container input,
.gradio-container textarea,
.gradio-container button,
.gradio-container select {
  font-size: 19px !important;
}
.gradio-container [data-testid="block-info"],
.gradio-container summary {
  font-size: 19px !important;
}
.gradio-container input:not([type="checkbox"]),
.gradio-container textarea,
.gradio-container button {
  min-height: 46px;
}
.gradio-container textarea::placeholder,
.gradio-container input::placeholder {
  color: #60736b !important;
  opacity: 1 !important;
}
.gradio-container button:focus-visible,
.gradio-container input:focus-visible,
.gradio-container textarea:focus-visible,
.gradio-container [role="listbox"]:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--focus) 35%, transparent) !important;
  outline-offset: 2px;
}
#approval-row button { min-height: 50px; font-weight: 700; }
#start-button,
#followup-button {
  --button-primary-background-fill: var(--ink);
  --button-primary-background-fill-hover: var(--accent-hover);
  --button-primary-border-color: var(--accent);
  --button-primary-text-color: #ffffff;
  min-height: 52px;
  background: var(--accent) !important;
  color: #ffffff !important;
  border-color: var(--accent) !important;
  border-radius: var(--radius-control) !important;
  font-weight: 700;
  transition: background-color 180ms cubic-bezier(.22, 1, .36, 1),
    transform 180ms cubic-bezier(.22, 1, .36, 1);
}
#start-button:hover,
#followup-button:hover {
  background: var(--accent-hover) !important;
}
#start-button:active,
#followup-button:active {
  transform: translateY(1px);
}
footer { display: none !important; }
input[type="checkbox"] { accent-color: var(--accent) !important; }
#approve-button { background: var(--accent) !important; color: #ffffff !important; }
#approve-button:disabled {
  opacity: 1 !important;
  border-color: var(--line-strong) !important;
  background: var(--accent-soft) !important;
  color: var(--accent-ink) !important;
}
#reject-button:disabled { display: none !important; }
#reject-button { background: transparent !important; color: #8b2f2f !important; border-color: #b65a5a !important; }
.status-strip {
  margin: 0;
  padding: 0 2px;
  color: var(--ink-soft);
}
.status-strip p { margin: 0; font-size: 19px !important; }
@media (max-width: 900px) {
  .gradio-container { padding-inline: 12px !important; }
  .app-shell { width: 100%; }
  .app-header { padding: 14px 2px 8px; }
  .app-header { border-bottom: 0; }
  .app-header h1 { font-size: 30px; }
  .main-surface { padding: 0 !important; }
  .report-section { padding: 16px 0 0 !important; }
  .control-bar { flex-wrap: wrap; gap: 8px; }
  .how-to ol { grid-template-columns: 1fr; }
  #current-question { padding: 16px !important; }
  #current-question p, #current-question li { font-size: 19px !important; }
  #conversation { height: 300px !important; min-height: 300px !important; }
  #start-button, #followup-button { min-height: 52px; }
  .followup-composer { padding: 0; }
  .conversation-header {
    flex-direction: column !important;
    align-items: stretch !important;
  }
  .conversation-header .prose {
    width: 100% !important;
  }
  #restart-button {
    width: 100% !important;
    margin-top: 2px;
  }
  #history-section .gr-accordion > button.label-wrap { padding: 14px !important; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    transition-duration: .01ms !important;
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
  }
}
"""


HEADER = """
<div class="app-shell app-header">
  <h1>長照 2.0 資格與補助初步試算</h1>
</div>
"""


HOW_TO = """
<div class="how-to">
  <h2>照這 4 步操作</h2>
  <ol>
    <li><strong>一次選一位家人</strong>；多人請分開評估。</li>
    <li><strong>在下方欄位打字</strong>；先寫年齡和需要協助的事情。</li>
    <li><strong>按「開始資格初篩」</strong>；系統一次問一輪，直接在問題下方回答。</li>
    <li><strong>檢查試算報告</strong>；資料足夠後才會顯示金額與核准按鈕。</li>
  </ol>
  <p class="privacy-line"><strong>請勿輸入</strong>姓名、身分證、電話或地址；正式結果仍以照管中心為準。</p>
</div>
"""


def _updates(response: UiResponse):
    has_conversation = bool(response.history)
    has_report = bool(response.preview or response.details or response.sources)
    has_status = bool(response.status.strip())
    current_question = next(
        (
            item.get("content", "")
            for item in reversed(response.history)
            if item.get("role") == "assistant"
        ),
        "",
    )
    if has_report:
        current_question = response.status or "報告已完成，請查看下方報告校閱區。"
    return (
        response.history,
        current_question,
        response.preview,
        response.details,
        response.sources,
        gr.Button(
            value=(
                "核准並發布"
                if response.approval_visible
                else "已核准並發布"
            ),
            visible=has_report,
            interactive=response.approval_visible,
        ),
        gr.Button(
            visible=response.approval_visible,
            interactive=response.approval_visible,
        ),
        gr.update(value=response.status, visible=has_status),
        gr.update(visible=not has_conversation),
        gr.update(visible=has_conversation and not has_report),
        gr.update(visible=has_conversation),
        gr.update(visible=has_report),
    )


def build_demo(controller: GradioController | None = None) -> gr.Blocks:
    controller = controller or GradioController()
    choices = provider_choices()
    default_provider = choices[0][1]

    def submit_message(text, history, provider, compare_legacy, session_id):
        response = controller.submit(
            session_id=session_id,
            provider_value=provider,
            compare_legacy=compare_legacy,
            text=text,
            history=history,
        )
        return ("", "", *_updates(response))

    def decide_report(decision: str, history, provider, session_id):
        response = controller.decide(
            session_id=session_id,
            provider_value=provider,
            decision=decision,
            history=history,
        )
        return _updates(response)

    def approve_report(history, provider, session_id):
        return decide_report("approve", history, provider, session_id)

    def reject_report(history, provider, session_id):
        return decide_report("reject", history, provider, session_id)

    def clear_session(session_id):
        controller.clear(session_id)
        return (
            [],
            "",
            "",
            "",
            "",
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(value="", visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
        )

    with gr.Blocks(
        title="長照額度初步試算",
        fill_width=True,
    ) as demo:
        # request.session_hash 在部分 Space SSR 事件間可能不一致；State 的 callable
        # 會為每個瀏覽器 session 建立穩定且不可猜測的 thread id。
        session_id = gr.State(lambda: uuid4().hex)
        gr.HTML(HEADER, elem_classes="header-wrap")
        with gr.Column(elem_classes=["app-shell", "main-surface"]):
            with gr.Column(visible=True, elem_id="onboarding-section") as onboarding_section:
                gr.HTML(HOW_TO)

                with gr.Row(elem_classes="composer-row"):
                    start_text = gr.Textbox(
                        label="先描述這位家人的情況",
                        placeholder="例如：家人 82 歲，洗澡與穿衣需要協助，已持續 8 個月",
                        lines=2,
                        scale=6,
                        min_width=320,
                        elem_id="start-input",
                    )
                    start_send = gr.Button(
                        "開始資格初篩",
                        variant="primary",
                        elem_id="start-button",
                        scale=1,
                        min_width=180,
                    )

                with gr.Accordion(
                    "進階設定（一般不用調整）",
                    open=False,
                    elem_id="advanced-settings",
                ):
                    with gr.Row(elem_classes="control-bar"):
                        with gr.Column(scale=4, min_width=260):
                            provider = gr.Dropdown(
                                choices=choices,
                                value=default_provider,
                                label="模型模式",
                                interactive=True,
                                elem_id="provider-select",
                            )
                        with gr.Column(scale=3, min_width=230):
                            compare_legacy = gr.Checkbox(
                                label="同時顯示 2022 舊制",
                                value=False,
                                elem_id="legacy-toggle",
                            )

            status = gr.Markdown(
                "",
                visible=False,
                elem_classes="status-strip",
            )

            with gr.Column(
                visible=False,
                elem_id="conversation-section",
                elem_classes="conversation-panel",
            ) as conversation_section:
                with gr.Row(elem_classes="conversation-header"):
                    gr.Markdown("### 系統現在想問你")
                    clear = gr.Button(
                        "重新評估另一位家人",
                        variant="secondary",
                        elem_id="restart-button",
                        min_width=240,
                    )
                current_question = gr.Markdown("", elem_id="current-question")
                gr.Markdown(
                    "系統會根據你的回答繼續追問，直到資料足夠產生報告。",
                    elem_classes="followup-helper",
                )
                with gr.Row(elem_classes=["composer-row", "followup-composer"]):
                    followup_text = gr.Textbox(
                        label="直接回答上面的問題",
                        placeholder="把你知道的情況寫在這裡；不知道也可以直接說不知道",
                        lines=2,
                        scale=6,
                        min_width=320,
                        elem_id="followup-input",
                    )
                    followup_send = gr.Button(
                        "送出回答",
                        variant="primary",
                        elem_id="followup-button",
                        scale=1,
                        min_width=180,
                    )

            with gr.Column(visible=False, elem_id="history-section") as history_section:
                with gr.Accordion("查看完整對話紀錄", open=False):
                    chatbot = gr.Chatbot(
                        label="對話紀錄",
                        show_label=False,
                        elem_id="conversation",
                        height=320,
                        layout="panel",
                        buttons=["copy_all"],
                        feedback_options=None,
                        placeholder="尚無對話紀錄。",
                    )

        with gr.Row(
            visible=False,
            elem_id="report-section",
            elem_classes=["app-shell", "report-section"],
        ) as report_section:
            with gr.Column(scale=2, min_width=520):
                gr.Markdown("## 報告校閱")
                report_preview = gr.Markdown(
                    "完成資料蒐集後，報告草稿會顯示在這裡。",
                    elem_id="report-preview",
                )
                with gr.Row(elem_id="approval-row"):
                    approve = gr.Button("核准並發布", visible=False, elem_id="approve-button")
                    reject = gr.Button("拒絕並繼續修正", visible=False, elem_id="reject-button")
            with gr.Column(scale=1, min_width=300):
                with gr.Accordion("試算明細", open=True):
                    details = gr.Markdown("尚無明細。", elem_id="details-panel")
                with gr.Accordion("法源與申請來源", open=False):
                    sources = gr.Markdown("尚無引用來源。")

        submit_outputs = [
            start_text,
            followup_text,
            chatbot,
            current_question,
            report_preview,
            details,
            sources,
            approve,
            reject,
            status,
            onboarding_section,
            conversation_section,
            history_section,
            report_section,
        ]
        start_text.submit(
            submit_message,
            [start_text, chatbot, provider, compare_legacy, session_id],
            submit_outputs,
        )
        start_send.click(
            submit_message,
            [start_text, chatbot, provider, compare_legacy, session_id],
            submit_outputs,
        )
        followup_text.submit(
            submit_message,
            [followup_text, chatbot, provider, compare_legacy, session_id],
            submit_outputs,
        )
        followup_send.click(
            submit_message,
            [followup_text, chatbot, provider, compare_legacy, session_id],
            submit_outputs,
        )
        decision_outputs = [
            chatbot,
            current_question,
            report_preview,
            details,
            sources,
            approve,
            reject,
            status,
            onboarding_section,
            conversation_section,
            history_section,
            report_section,
        ]
        approve.click(
            approve_report,
            [chatbot, provider, session_id],
            decision_outputs,
        )
        reject.click(
            reject_report,
            [chatbot, provider, session_id],
            decision_outputs,
        )
        clear.click(
            clear_session,
            inputs=[session_id],
            outputs=decision_outputs,
            queue=False,
        )
    return demo


def configured_port() -> int:
    raw = os.getenv("GRADIO_SERVER_PORT", "7860")
    port = int(raw)
    if not 1 <= port <= 65535:
        raise ValueError("GRADIO_SERVER_PORT 必須介於 1 與 65535")
    return port


def ensure_port_available(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError as exc:
            raise RuntimeError(
                f"{host}:{port} 已被占用；不會停止既有程式，請改 GRADIO_SERVER_PORT"
            ) from exc


def main() -> None:
    host = os.getenv("GRADIO_SERVER_NAME", "127.0.0.1")
    port = configured_port()
    ensure_port_available(host, port)
    build_demo().queue().launch(
        server_name=host, server_port=port, css=CSS, footer_links=[]
    )


if __name__ == "__main__":
    main()
