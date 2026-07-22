# 託管環境操作指南

本專案提供根目錄 `app.py`。偵測到 `SPACE_ID` 時，介面只顯示雲端 provider，不嘗試啟動或連線 Windows 地端模型服務。

作者自行建立託管應用、設定 secret 與推送；Agent 不執行 Git 或帳號操作。

必要設定：

- Python 3.11。
- App file：`app.py`。
- Secret：`GOOGLE_API_KEY`。
- Variable：`GEMINI_MODEL`（模型字串由環境設定）。
- 依 lock 安裝相依套件。

部署前先在本機執行：

```powershell
uv sync --locked
uv run pytest
uv run python app.py
```

本機連接埠由 `GRADIO_SERVER_PORT` 指定；若被占用，程式會停止啟動並要求換 port，不會關閉既有服務。
