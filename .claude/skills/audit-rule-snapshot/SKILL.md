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

## P2 離線複核報告

P1 線上 JSON 證據已存在時，在專案根目錄以 PowerShell 執行：

```powershell
uv run --group audit ltc-rule-audit `
  --input artifacts/rule-audit/2026-07-23-online.json `
  --review-output artifacts/rule-audit/2026-07-23-review.md `
  --project-root .
```

此模式不連線、不呼叫 LLM，也不讀 `.env`。它會把 P1 證據轉成正體中文複核報告，並確定性比較 manifest、runtime metadata／業務常數、README、離線 fixtures 與測試斷言。若來源需要人工複核或跨檔一致性漂移，CLI 以 exit code `2` 結束；報告仍只提供證據，不會修改規則。

報告產生後須由作者檢查來源狀態、欄位差異、影響規則、建議測試、`project_consistency` 與 `writes_performed=false`。作者的 approve／reject 是人工 gate；兩種決定都不等於授權工具直接寫入規則。

## P3 排程與公開證據

- 排程只作為獨立的手動／低頻檢查入口，不得加入 Gradio 民眾請求路徑。
- 完整稽核 JSON 只放 runner 暫存目錄；公開 artifact 只能由 `build_public_audit_summary` 產生固定白名單摘要。
- 公開摘要必須由同一次新鮮的完整 manifest 線上稽核產生，恰好涵蓋全部來源，且 `source_id` 不得重複；`--source` 局部診斷與 `--input` 封存證據都不得搭配 `--public-output`。
- `--output`、`--public-output`、`--review-output` 必須使用不同檔案身分，且不得指向 `--input`、manifest、核准狀態、`.env` 或 `rules.py`／`eligibility.py`／`copay.py`；Windows 大小寫別名與既有 hard link 也視為同一檔案，不安全組合必須在讀檔與連線前拒絕。
- manifest、核准狀態與公開摘要都採 fail-closed schema：拒絕未知欄位、錯誤型別、空識別值與缺少時區的時間；不得以字串強制轉型掩蓋壞資料。
- 線上 timeout 必須是有限且大於零的秒數；HTTP 成功範圍內但不是 `200` 的回應仍記為 `CHECK_UNAVAILABLE`，不得交給 extractor 猜測。
- 公開摘要的每筆 `checked_at` 與整體 `generated_at` 都正規化為 UTC `Z`，並必須匹配非空 manifest 版本與完整來源集合。
- 公開排程執行 CLI 時必須使用 `--quiet`，避免完整 JSON 出現在 Actions log；log 只保留來源 ID、三態狀態與輸出位置。
- 公開摘要不得包含 canonical URL、raw／semantic hash、`changed_fields`、`errors`、HTTP 內容、原始附件、token、個資或對話。
- `REVIEW_REQUIRED` 與 `CHECK_UNAVAILABLE` 都必須讓 job 失敗；不可用來源的嚴重度不得被其他一致來源掩蓋。
- `approved-audit-status-v1.json` 是供開發與稽核使用的機器可讀人工核准狀態，不是最近一次排程結果，也不得呈現在公開 Gradio 民眾操作頁。只有 4／4 成功證據再經作者核准，才能另行更新；排程不得自動升格。
- 核准狀態檔必須與正式 manifest 版本相符；限制與非官方保證邊界留在 README／契約文件，民眾對話不即時抓取法規。
- 核准狀態或呈現邊界異動後，以受控 fixture 執行桌面、手機、多輪與 HITL 瀏覽器 smoke；確認民眾操作頁沒有 manifest 版本、稽核日期、來源計數、敏感證據欄位或水平溢出，並確認沒有向官方法規網站發出即時請求。

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
