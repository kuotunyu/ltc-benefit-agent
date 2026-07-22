---
name: prepare-f1-ollama
description: 安全檢查、下載、轉換、量化、匯入或重建 ltc-benefit-agent 的 gated F1 Ollama 模型。作者要求準備 F1、重跑 GGUF 轉檔、驗證 manifest／capabilities，或排查 Windows 轉檔失敗時使用。
---

# 準備 F1 Ollama 模型

## 執行邊界

- 先讀 `PLAN.md` Phase 3、`PROGRESS.md` 快速回憶區、`docs/local-models.md` 與 `scripts/prepare_f1_ollama.py`。
- 不印出 `.env` 或 token；只允許腳本按用途載入 `HF_TOKEN`。
- 預設只執行 check-only。只有作者已接受 gated license 且明確核准下載／轉檔，才可加入 `--execute --accepted-license`。
- 執行前唯讀檢查 GPU、C 槽空間與執行中程序；不停止既有服務。若必須終止故障 converter，只能先確認並停止本次腳本建立的確切 PID。
- 不執行 Git。權重、GGUF、llama.cpp 與 manifest 必須留在 repo 外或 ignored 路徑。

## 工作流程

1. 先執行：

   ```powershell
   uv run --group model python scripts\prepare_f1_ollama.py
   ```

   記錄 gated access、固定 revision、下載 bytes、GPU 與磁碟；任一 gate 失敗就停止並回報。

2. 取得作者核准後執行：

   ```powershell
   uv run --group model python scripts\prepare_f1_ollama.py --execute --accepted-license
   ```

3. 完成後驗證 `build-manifest.json` 的 revision、F16／Q4_K_M SHA-256、alias 與 capabilities；再執行一題與固定 20 題 trace evaluator。保留失敗案例，不改 expected data 美化分數。
4. 執行 `uv lock --check`、locked sync、compileall 與 pytest；依 `update-progress` 同步實跑數字、成本與待作者操作。

## Windows 已知修正

- converter 必須由 `uv run --python 3.11 --managed-python` 啟動，且 subprocess 移除繼承的 `VIRTUAL_ENV`；不要退回全域 Python 3.10。
- CUDA DLL 搜尋只限下載的 llama.cpp binary 目錄，不得遞迴掃整個工作區。
- 原始嵌入 Jinja template 若在 tools request 回 server error，使用 repo 的 Go/Hermes Modelfile template；不可把不同社群量化版冒充官方 F1。
- 所有模型 HTTP 呼叫必須保留 `OLLAMA_TIMEOUT_SECONDS`，避免單題無限等待。

## 完成回報

- 回報模型 alias／capabilities、檔案大小與 SHA、磁碟餘量、實測指標、API 成本、清理內容與尚未通過的 gate。
- 絕不回報 token 值，也不把未跑項目寫成通過。
