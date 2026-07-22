"""帶人工校閱台的 Gradio Blocks 介面。"""

from __future__ import annotations

import os
import socket
from pathlib import Path

import gradio as gr

from .controller import GradioController, UiResponse, provider_choices


CSS = """
:root {
  --rice: #f2ecdf;
  --paper: #fffaf0;
  --ink: #18342c;
  --ink-soft: #49645c;
  --seal: #b9482d;
  --brass: #b08a45;
  --line: rgba(24, 52, 44, .18);
}
.gradio-container {
  background:
    radial-gradient(circle at 15% 10%, rgba(176,138,69,.12) 0 1px, transparent 2px) 0 0/22px 22px,
    linear-gradient(110deg, var(--rice), #e9e0cf 68%, #ded2bd);
  color: var(--ink);
  font-family: "Noto Serif TC", "PMingLiU", serif !important;
}
.app-shell { max-width: 1420px; margin: 0 auto; }
.hero-ledger {
  position: relative; overflow: hidden; padding: 32px 36px 27px;
  border: 1px solid var(--line); border-bottom: 4px solid var(--ink);
  background: rgba(255,250,240,.88); box-shadow: 0 16px 55px rgba(53,42,24,.12);
}
.hero-ledger::after {
  content: "可稽核"; position: absolute; right: 40px; top: 24px;
  width: 74px; height: 74px; display: grid; place-items: center;
  border: 3px double var(--seal); color: var(--seal); border-radius: 50%;
  font-weight: 800; letter-spacing: .18em; transform: rotate(-8deg); opacity: .86;
}
.eyebrow { color: var(--seal); letter-spacing: .22em; font-size: 12px; font-weight: 800; }
.hero-ledger h1 { margin: 8px 100px 6px 0; font-size: clamp(30px,4vw,54px); line-height: 1.05; letter-spacing: -.025em; }
.hero-ledger p { max-width: 780px; color: var(--ink-soft); margin: 0; font-size: 16px; }
.sidebar-card, .workbench {
  border: 1px solid var(--line); background: rgba(255,250,240,.9);
  box-shadow: 0 12px 38px rgba(48,42,31,.09); padding: 18px;
}
.sidebar-card { border-top: 5px solid var(--seal); }
.workbench { border-top: 5px solid var(--brass); }
.notice { padding: 13px 14px; background: #efe1ca; border-left: 3px solid var(--seal); line-height: 1.7; }
#conversation { border: 0 !important; background: transparent !important; }
#conversation .message { border-radius: 2px !important; box-shadow: none !important; }
#report-preview {
  max-height: 620px; overflow: auto; padding: 24px; background: var(--paper);
  border: 1px solid var(--line); border-left: 4px solid var(--brass);
}
#report-preview table, #details-panel table { width: 100%; }
#approval-row button { min-height: 48px; letter-spacing: .08em; font-weight: 800; }
#send-button {
  --button-primary-background-fill: var(--ink);
  --button-primary-background-fill-hover: #10271f;
  --button-primary-border-color: var(--ink);
  --button-primary-text-color: #fffaf0;
  background: var(--ink) !important; color: #fffaf0 !important; border-color: var(--ink) !important;
}
footer { display: none !important; }
input[type="checkbox"] { accent-color: var(--seal) !important; }
#approve-button { background: var(--ink) !important; color: #fffaf0 !important; }
#reject-button { background: transparent !important; color: var(--seal) !important; border-color: var(--seal) !important; }
.status-strip { border: 1px dashed var(--line); padding: 8px 12px; background: rgba(255,255,255,.35); }
@media (max-width: 780px) {
  .hero-ledger { padding: 24px 20px; }
  .hero-ledger::after { right: 16px; top: 18px; width: 58px; height: 58px; font-size: 12px; }
  .hero-ledger .eyebrow { padding-right: 76px; }
  #conversation { height: 350px !important; min-height: 350px !important; }
}
"""


HEADER = """
<div class="app-shell hero-ledger">
  <div class="eyebrow">LONG-TERM CARE · BENEFIT LEDGER</div>
  <h1>長照額度，算清楚再決定。</h1>
  <p>對話負責問對問題，Python 負責每一塊錢。CMS 未知不猜級；報告發布前由你親自校閱。</p>
</div>
"""


def _updates(response: UiResponse):
    return (
        response.history,
        response.preview,
        response.details,
        response.sources,
        gr.update(visible=response.approval_visible),
        gr.update(visible=response.approval_visible),
        response.status,
    )


def build_demo(controller: GradioController | None = None) -> gr.Blocks:
    controller = controller or GradioController()
    choices = provider_choices()
    default_provider = choices[0][1]

    def submit_message(text, history, provider, compare_legacy, request: gr.Request):
        response = controller.submit(
            session_id=request.session_hash or "",
            provider_value=provider,
            compare_legacy=compare_legacy,
            text=text,
            history=history,
        )
        return ("", *_updates(response))

    def decide_report(decision: str, history, provider, request: gr.Request):
        response = controller.decide(
            session_id=request.session_hash or "",
            provider_value=provider,
            decision=decision,
            history=history,
        )
        return _updates(response)

    def approve_report(history, provider, request: gr.Request):
        return decide_report("approve", history, provider, request)

    def reject_report(history, provider, request: gr.Request):
        return decide_report("reject", history, provider, request)

    def clear_session(request: gr.Request):
        controller.clear(request.session_hash or "")
        return [], "", "", "", gr.update(visible=False), gr.update(visible=False), "已清除本次 session。"

    with gr.Blocks(
        title="長照額度初步試算",
        fill_width=True,
    ) as demo:
        gr.HTML(HEADER)
        with gr.Row(elem_classes="app-shell"):
            with gr.Column(scale=1, min_width=280, elem_classes="sidebar-card"):
                gr.Markdown("### 評估設定")
                provider = gr.Dropdown(
                    choices=choices,
                    value=default_provider,
                    label="模型模式",
                    interactive=True,
                )
                compare_legacy = gr.Checkbox(
                    label="並列 2022 舊制比較",
                    value=False,
                )
                gr.HTML(
                    "<div class='notice'><strong>先說清楚</strong><br>"
                    "請不要輸入姓名、身分證、電話或地址。這是初步試算，正式結果仍以照管中心為準。</div>"
                )
                clear = gr.Button("清除此 session", variant="secondary")
                gr.Markdown(
                    "**建議先準備**  \n年齡、服務對象身分、住宿狀態、正式 CMS、福利類別、外籍看護與預計服務費。"
                )

            with gr.Column(scale=3, min_width=520):
                with gr.Column(elem_classes="workbench"):
                    chatbot = gr.Chatbot(
                        label="對話紀錄",
                        elem_id="conversation",
                        height=470,
                        layout="panel",
                        buttons=["copy"],
                        feedback_options=None,
                        placeholder="從家人的年齡與目前需要哪些協助開始。",
                    )
                    text = gr.Textbox(
                        label="補充情況",
                        placeholder="例如：家人 70 歲，生活協助已持續 8 個月……",
                        lines=3,
                    )
                    send = gr.Button(
                        "送出並檢查缺漏", variant="primary", elem_id="send-button"
                    )
                    status = gr.Markdown(
                        "🟢 尚未開始；資料只應包含試算必要欄位。",
                        elem_classes="status-strip",
                    )

        with gr.Row(elem_classes="app-shell"):
            with gr.Column(scale=2, elem_classes="workbench"):
                gr.Markdown("## 人工校閱台")
                report_preview = gr.Markdown(
                    "尚未產生報告草稿。",
                    elem_id="report-preview",
                )
                with gr.Row(elem_id="approval-row"):
                    approve = gr.Button("核准並發布", visible=False, elem_id="approve-button")
                    reject = gr.Button("拒絕，回去修正", visible=False, elem_id="reject-button")
            with gr.Column(scale=1, elem_classes="sidebar-card"):
                with gr.Accordion("試算明細", open=True):
                    details = gr.Markdown("尚無明細。", elem_id="details-panel")
                with gr.Accordion("法源與申請來源", open=False):
                    sources = gr.Markdown("尚無引用來源。")

        submit_outputs = [
            text,
            chatbot,
            report_preview,
            details,
            sources,
            approve,
            reject,
            status,
        ]
        text.submit(
            submit_message,
            [text, chatbot, provider, compare_legacy],
            submit_outputs,
        )
        send.click(
            submit_message,
            [text, chatbot, provider, compare_legacy],
            submit_outputs,
        )
        decision_outputs = [
            chatbot,
            report_preview,
            details,
            sources,
            approve,
            reject,
            status,
        ]
        approve.click(
            approve_report,
            [chatbot, provider],
            decision_outputs,
        )
        reject.click(
            reject_report,
            [chatbot, provider],
            decision_outputs,
        )
        clear.click(
            clear_session,
            inputs=None,
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
