---
name: verify-external-api
description: 在 ltc-benefit-agent 撰寫或修改任何依賴外部套件 API 的程式前，使用 Context7 查證現行介面並比對 uv 鎖定版本。觸及 LangChain、LangGraph、Gradio、sentence-transformers、Ollama connector 或其他第三方套件時使用；也用於版本升級與相容性診斷。
---

# 查證外部套件 API

## 查證流程

1. 從 `pyproject.toml` 與 `uv.lock` 確認套件名稱、約束及實際鎖定版本。
2. 使用 Context7 `resolve-library-id` 選擇官方性高且符合語言／版本的 library ID；已知精確 ID 時可略過解析。
3. 用 `query-docs` 一次查一個具體 API；查詢不得包含金鑰、個資、原始對話或專案機密。
4. 記下 library ID、查詢主題、來源 URL、鎖定版本與 API 結論。Context7 查不到時改查官方文件，並標示 fallback。
5. 若文件可能比鎖定版本新，檢查已安裝物件的 signature 或最小離線 smoke；不得為套用新文件而靜默升級依賴。
6. 依證據做最小修改，執行相關 pytest；測試未跑不得宣稱相容。

## 留存證據

- 影響後續開發或 Phase gate 時，使用 `update-progress` 將查證日期、library ID、來源、版本、結論與測試結果追加到 `PROGRESS.md`。
- 只有架構、版本策略或驗收標準改變時才在 PLAN Decision Log 追加決策，避免複製整份文件。
- Context7 是開發期查證工具，不加入正式 Agent runtime，也不接觸民眾對話資料。

## 邊界

- 不讀出或記錄 `.env` 真值。
- 不執行 Git；只提供建議 commit 訊息。
- 文件與已安裝版本衝突時先回報，不降低測試或安全標準。
