# Windows 地端模型準備

本專案只使用 Ollama，不使用 vLLM。所有模型字串由 `.env` 設定，模型權重、GGUF、轉檔工具與 trace 不進版控。

## 12B 基準 adapter

既有 `gemma3:12b` 的 Ollama manifest 只有 completion／vision，直接傳 tools 會回應 400。專案因此提供明示的相容模板；它不是原模型原生 tool-calling 能力。

若一般回合已有至少兩個可逐字核對的資格欄位，但模型仍漏掉第一個資格工具，runtime 最多進行一次隔離重試。重試不包含原始使用者文字，只暴露 `eligibility_check` 與 PII 遮蔽後的明確欄位；Modelfile 在只收到這一個工具時要求輸出該工具呼叫。相容 parser 只接受完整 fenced JSON、已註冊的工具名稱與物件型參數，不解析散文、不猜工具、不補值。這仍是相容 adapter，不是原模型 native function calling。

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

最終固定集 trace 為 `artifacts/eval/gemma3-20-intake-final-v3.json`（ignored，不進版控）：端到端 20 / 20、需試算題金額 13 / 13、PII 洩漏 0。這是相容 adapter 與專案 middleware 的整體成績，不得改寫成基礎模型原生 function-calling 成績。

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
- 初始 20 題 trace：`artifacts/eval/f1-20-final.json`（ignored，不進版控）
- workflow／template 強化後 trace：`artifacts/eval/f1-20-workflow-complete.json`（ignored，不進版控）
- intake／有限重試最終 trace：`artifacts/eval/f1-20-intake-final-v3.json`（ignored，不進版控）

Windows 轉檔時必須明確使用 uv-managed Python 3.11，且 converter subprocess 要移除繼承的 `VIRTUAL_ENV`；CUDA DLL 搜尋只限已下載的 llama.cpp binary 目錄，避免遞迴掃到 Windows 不可讀路徑。這兩項已寫入準備腳本與回歸測試。

官方 tokenizer chat template 會把工具結果包成 `{"name": 工具名, "content": 結果}`；Ollama Modelfile 因此必須在 `<tool_response>` 同時輸出 `.ToolName` 與 `.Content`。舊模板只放內容時，實測會在第一個工具結果後產生空白回覆。修正模板、加入確定性 workflow 接續與保守 intake 後，最終固定集端到端為 20 / 20、需試算題金額 13 / 13、PII 洩漏為 0；這只是 20 題固定診斷結果，仍只適合作為研究／可選地端模式，不應宣稱已可無人監督。
