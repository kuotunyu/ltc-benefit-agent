---
name: audit-rule-snapshot
description: 稽核長照規則快照與官方來源是否一致，產生可供人工校對的結構化證據。當需要檢查法規更新、來源異動、快照新鮮度、解析器漂移，或準備調整 eligibility、copay、rules 常數前使用；不得自動修改規則或把無法連線視為通過。
---

# 稽核法規快照

## 開始前

1. 先讀 `AGENTS.md`、`CLAUDE.md`、`PLAN.md`、`PROGRESS.md` 與現有規則來源文件。
2. 不讀 `.env`、不輸出秘密、不執行任何 Git 指令。
3. 明確區分本次是離線 fixture、線上來源檢查或人工複核；沒有實跑的項目不得寫成通過。

## 不可破壞的邊界

- 只接受 manifest 白名單中的官方 canonical URL，不把搜尋摘要或第三方轉載當真值。
- LLM 不判定法規是否改變，不推導資格或金額，也不重寫數字。
- 不得自動修改 `rules.py`、`eligibility.py`、`copay.py` 或任何規則常數。
- 原始 bytes 改變不等於規則語意改變；必須比較結構化欄位。
- `CHECK_UNAVAILABLE` 不得記成驗證成功；連線失敗與內容相符是不同狀態。
- 稽核紀錄只留來源、雜湊、結構化差異與錯誤，不保存個資、token 或原始對話。

## 工作流程

1. 載入版本化 manifest，核對 schema、來源 ID、規則版本與受影響規則 ID。
2. 離線模式使用固定 fixture；線上模式才讀官方來源，並記錄查證時間、HTTP 結果與原始 SHA-256。
3. 以確定性 extractor 正規化相關條文、表格與數值，產生 semantic fingerprint。
4. 與已核准 manifest 比較，僅使用以下狀態：
   - `VERIFIED_SNAPSHOT`：必要結構化欄位與已核准快照一致。
   - `REVIEW_REQUIRED`：規則欄位改變、必要內容缺漏或 extractor 行為漂移。
   - `CHECK_UNAVAILABLE`：來源無法取得、格式不可讀、逾時或檢查未完成。
5. 將報告寫入忽略版控的 artifact；報告必須聲明 `writes_performed=false`。
6. 由人工逐項確認差異。只有作者明確核准後，才另開工作修改規則、測試、metadata 與公開文件。
7. 依 `update-progress` 把實跑證據、限制與待人工處理事項同步至 `PLAN.md`／`PROGRESS.md`。

## 必要證據

- `source_id`、標題、canonical URL、規則版本與來源生效日。
- `checked_at`、取得結果、HTTP status（若適用）與錯誤類型。
- 預期／實際 raw SHA-256 與 semantic fingerprint。
- `changed_fields`、可能受影響的規則與應補的測試。
- 明確的狀態與「未自動寫入規則」聲明。

## 停止條件

- 發現 `REVIEW_REQUIRED` 時，先交付差異與影響範圍，等待作者決定，不自行改常數。
- 需要付費 API 或模型判讀時，先列成本上限並取得核准；預設流程不需要模型。
- 官方來源不可用時，回報 `CHECK_UNAVAILABLE` 並停止對該來源下「已驗證」結論。
- 要發布新版快照、改資格／金額或更新 public release 時，必須另行取得作者確認。
