# Windows 地端模型準備

本專案只使用 Ollama，不使用 vLLM。所有模型字串由 `.env` 設定，模型權重、GGUF、轉檔工具與 trace 不進版控。

## 12B 基準 adapter

既有 `gemma3:12b` 的 Ollama manifest 只有 completion／vision，直接傳 tools 會回應 400。專案因此提供明示的相容模板；它不是原模型原生 tool-calling 能力。

```powershell
ollama create ltc-gemma3-tools:12b -f deploy\ollama\gemma3-tools.Modelfile
ollama show ltc-gemma3-tools:12b
```

`Capabilities` 必須列出 `tools`，再跑單題：

```powershell
uv run python -m ltc_benefit_agent.evaluation `
  --provider gemma3_baseline `
  --scenario S14_THIRD_CATEGORY `
  --output artifacts\eval\gemma3-smoke.json
```

## F1 3B 自轉 Q4_K_M

原始 `twinkle-ai/Llama-3.2-3B-F1-Instruct` 是 gated repository，必須由作者本人登入模型頁、閱讀並接受授權。先只做 dry-run：

```powershell
uv run --group model python scripts\prepare_f1_ollama.py
```

只有在輸出 `CHECK_ONLY_OK`、資源足夠且作者已接受條款時才執行：

```powershell
uv run --group model python scripts\prepare_f1_ollama.py `
  --execute --accepted-license
```

腳本固定使用官方原始權重與 llama.cpp `b9637` source archive，先轉 F16 GGUF，再用 Windows CUDA release binary 量化 Q4_K_M，最後以 Hermes tool template 匯入 `ltc-f1:q4_k_m`。實際 revision、兩個 GGUF SHA-256 與 capabilities 寫在 repo 外的 `build-manifest.json`。

2026-07-22 已在作者明確核准後完成：

- 原始 revision：`32e8791e9446e92b3513551201c11f9119652fd5`
- F16 SHA-256：`03b7ebeca3b12a588b84ccdf07c22e4bb4f9afb2b11dbcb0dfd71ce1161effb9`
- Q4_K_M SHA-256：`e17cf199a458cffa617073cb71df2bce02867e7622b685a7bef1c4dcec32035a`
- Ollama alias：`ltc-f1:q4_k_m`；capabilities 為 `completion`、`tools`
- 最終 20 題 trace：`artifacts/eval/f1-20-final.json`（ignored，不進版控）

Windows 轉檔時必須明確使用 uv-managed Python 3.11，且 converter subprocess 要移除繼承的 `VIRTUAL_ENV`；CUDA DLL 搜尋只限已下載的 llama.cpp binary 目錄，避免遞迴掃到 Windows 不可讀路徑。這兩項已寫入準備腳本與回歸測試。

本次 3B 診斷能連續呼叫資格與金額工具，但沒有完成報告草稿與人工核准，端到端為 0 / 20。它目前只適合作為研究對照，不應作為完整 Agent 的預設模型。
