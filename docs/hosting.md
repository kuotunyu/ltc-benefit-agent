# 託管環境操作指南

本專案提供根目錄 `app.py`、README YAML Space metadata 與 `requirements.txt`。偵測到 `SPACE_ID` 時，介面只顯示雲端 provider，不嘗試啟動或連線 Windows 地端模型服務。

作者自行建立託管應用、設定 secret 與推送；Agent 不執行 Git 或帳號操作。

從本機驗證、GitHub Push、Space Settings 到公開頁面 smoke 的逐項流程，見[發布與公開驗收清單](release-checklist.md)。

必要設定：

- Python 3.11。
- App file：`app.py`。
- Secret：`GEMINI_API_KEY` 或 connector 支援的 `GOOGLE_API_KEY`，二選一即可；不要同時填入 README 或一般 Variable。
- Variable：`GEMINI_MODEL`（模型字串由環境設定）。
- Variable：`GEMINI_THINKING_LEVEL=medium`（可省略，程式預設 medium）。
- Space runtime 依根目錄 `requirements.txt` 安裝外部套件：檔案直接內嵌由 `uv.lock` 匯出的完整 constraints，不引用相鄰檔案，也不在這個階段安裝本專案。Space builder 會先執行此步驟，之後才把 repository 複製到 `/app`；根目錄 `app.py` 啟動時再以 `pathlib` 將 `src/` 加入 module path。這同時避免建置順序造成 include／editable install 失敗，也避免 transitive dependency 漂移；本機仍直接使用 `uv.lock`。
- Space 會額外安裝 `gradio[oauth,mcp]`。[Gradio 6.20.0 package metadata](https://pypi.org/pypi/gradio/6.20.0/json) 的 MCP extra 限制 Pydantic 2.11.10–2.12.x，而公開 builder 的 resolver 實際拒絕 2.12.5，因此專案把 Pydantic 明確限制為 `>=2.11.10,<2.12.5`，目前 lock 為 2.12.4。此限制會讓 `google-genai` 鎖在 2.8.0；本機已確認 LangChain connector 仍接受 `gemini-3.5-flash-lite` 與 medium thinking，但公開部署後仍須另做經核准的真實 API smoke。更新 Gradio SDK 或 lock 時，必須以 Build log 中的完整 Space 安裝命令重新驗證 extras。

更新 `uv.lock` 後必須同步重建 Space constraints；測試會逐字比對 exporter 輸出，漏做時直接失敗：

```powershell
uv export --locked --format requirements.txt --no-dev --no-emit-project `
  --no-hashes --no-annotate --no-header --output-file requirements.txt
```

根目錄 README metadata 已指定：

- SDK：Gradio 6.20.0。
- Python：3.11。
- App file：`app.py`。
- `fullWidth: true`、`header: mini`。

部署前先在本機執行：

```powershell
uv sync --locked
uv run pytest
uv run python app.py
```

本機連接埠由 `GRADIO_SERVER_PORT` 指定；若被占用，程式會停止啟動並要求換 port，不會關閉既有服務。

Space Build 完成後，至少確認：只顯示雲端 provider、CMS 未知時不產生個人化金額、完整報告會先進入 approve／reject，以及手機寬度下可完成兩輪對話。完整驗收案例列在發布清單；請使用虛構資料，不要把真實個資當 smoke input。
