"""託管平台進入點；不會自行啟動地端模型服務。"""

from pathlib import Path
import sys


SOURCE_ROOT = Path(__file__).resolve().parent / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from ltc_benefit_agent.ui.app import CSS, build_demo, configured_port, ensure_port_available


demo = build_demo()


if __name__ == "__main__":
    import os

    host = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0" if os.getenv("SPACE_ID") else "127.0.0.1")
    port = configured_port()
    ensure_port_available(host, port)
    demo.queue().launch(server_name=host, server_port=port, css=CSS, footer_links=[])
