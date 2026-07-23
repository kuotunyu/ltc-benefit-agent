# 法規來源 manifest 與稽核結果契約

版本：schema v1

正式 manifest：`2026-07-23.1`

建立日期：2026-07-23

狀態：v0.2-P1 已通過；v0.2-P2 工程完成，待作者檢閱離線複核報告。

## 目的

此契約讓專案能以確定性方式判斷「官方來源是否仍與核准快照一致」，並把真正的規則更新決策留給人工。checker 只讀取來源與產生證據，不會直接修改資格、額度、部分負擔或進位規則。

正式 manifest 位於 `src/ltc_benefit_agent/audit/data/rule-sources-v1.json`。manifest 是專案核准快照；單次線上結果是觀測證據，兩者不得混為一談。

## `RuleSourceManifestSet`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `schema_version` | string | manifest schema 版本，目前固定為 `1` |
| `manifest_version` | string | 整組核准來源的版本，目前為 `2026-07-23.1` |
| `sources` | `RuleSourceManifest[]` | 經人工核准的官方來源清單 |

## `RuleSourceManifest`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `schema_version` | string | 單一來源採用的 schema 版本 |
| `source_id` | string | 專案內穩定且唯一的來源 ID |
| `title` | string | 官方文件或附件名稱 |
| `canonical_url` | HTTPS URL | 經人工核准的 exact URL；checker 不接受任意 URL 或非白名單 redirect |
| `media_type` | string | `text/html` 或 `application/pdf` |
| `rule_version` | enum | `LEGACY_2022` 或 `CURRENT_2026_07` |
| `effective_date` | ISO date | 此來源對應內容的生效日或完整快照基準 |
| `verified_at` | ISO datetime | 上一次人工核准的查證時間 |
| `raw_sha256` | hex string | 核准檔案原始 bytes 的 SHA-256 |
| `semantic_fingerprint` | hex string | 必要結構化欄位正規化後的 SHA-256 |
| `extractor_id` | string | 對應的確定性 extractor ID |
| `extractor_version` | string | 產生結構化欄位的 extractor 版本 |
| `impacted_rule_ids` | string[] | 可能受影響的資格、額度或部分負擔規則 ID |
| `semantic_snapshot` | object | 經核准的必要語意欄位與數值；用來產生結構化差異 |

## 已核准來源白名單

| `source_id` | 規則版本 | 媒體 | extractor | 官方 canonical URL |
|---|---|---|---|---|
| `legacy-2022-regulation` | `LEGACY_2022` | HTML | `legacy-regulation-html-v1` | [2022-02-01 歷史條文](https://law.moj.gov.tw/LawClass/LawOldVer.aspx?lnndate=20220120&lser=001&pcode=L0070059) |
| `current-2026-07-regulation` | `CURRENT_2026_07` | HTML | `current-regulation-html-v1` | [現行辦法與附表](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0070059) |
| `current-care-professional-quota` | `CURRENT_2026_07` | PDF | `care-professional-quota-pdf-v1` | [附表二：給付額度](https://law.moj.gov.tw/LawClass/LawGetFile.ashx?FileId=0000398330&lan=C) |
| `current-copay-percentages` | `CURRENT_2026_07` | PDF | `copay-percentages-pdf-v1` | [附表五：部分負擔比率](https://law.moj.gov.tw/LawClass/LawGetFile.ashx?FileId=0000398333&lan=C) |

## `RuleAuditResult`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `source_id` | string | 對應 manifest 的來源 ID |
| `title` | string | 官方來源標題 |
| `canonical_url` | HTTPS URL | 實際核對的白名單 URL |
| `rule_version` | enum | 對應的規則版本 |
| `effective_date` | ISO date | 對應的生效日或完整快照基準 |
| `checked_at` | ISO datetime | 本次檢查時間 |
| `status` | enum | 三態之一 |
| `fetch_result` | string | 成功、逾時、拒絕、格式不可讀等可稽核結果 |
| `http_status` | integer/null | 線上檢查的 HTTP status；離線 fixture 可為 null |
| `raw_sha256_expected` | string | manifest 中核准的 raw SHA-256 |
| `raw_sha256_actual` | string/null | 本次原始內容的 SHA-256 |
| `semantic_fingerprint_expected` | string | manifest 中核准的 semantic fingerprint |
| `semantic_fingerprint_actual` | string/null | 本次必要語意的 fingerprint |
| `changed_fields` | object[] | 欄位路徑、核准值、本次值與受影響規則 ID |
| `errors` | string[] | 不含秘密或個資的錯誤摘要 |
| `writes_performed` | boolean | 必須固定為 `false` |

## 狀態判準

### `VERIFIED_SNAPSHOT`

- 官方來源或離線 fixture 可完整讀取。
- extractor 成功取得全部必要欄位。
- 必要結構化欄位與已核准 manifest 相同。
- raw SHA-256 可以不同；若差異只來自排版、動態欄位或網站 metadata，仍須由結構化比較證明規則內容一致。

### `REVIEW_REQUIRED`

- 資格門檻、額度、部分負擔、施行日或其他必要欄位不同。
- 必要欄位缺漏、表格結構改變，或 extractor 版本／行為漂移。
- checker 只列出差異與影響；不得自動更新 manifest 或規則常數。

### `CHECK_UNAVAILABLE`

- 官方來源無法連線、逾時、被拒絕、格式不可讀或檢查未完成。
- 此狀態表示「沒有得到結論」，不能視為快照仍有效。
- 已核准快照不因暫時的來源故障而自動改變。

## P2 跨檔一致性與人工決定

### `ConsistencyStatus`

- `CONSISTENT`：manifest、runtime metadata／業務常數、README、離線 fixtures 與測試斷言中的核准值一致。
- `DRIFT_DETECTED`：上述任一層出現缺漏或值不一致；此狀態必須阻擋通過並列出問題，不得自動修正。

### `ConsistencyCheckResult`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `status` | enum | `CONSISTENT` 或 `DRIFT_DETECTED` |
| `checked_targets` | string[] | 本次確定性比較的檔案與資料層 |
| `issues` | object[] | 漂移位置、預期值、實際值與說明 |
| `writes_performed` | boolean | 必須固定為 `false` |

### `ReviewDecision`

- `PENDING`：報告已產生，等待作者檢閱。
- `APPROVED`：作者接受證據結論；若未來確有規則異動，仍須另外開工作修改規則。
- `REJECTED`：作者拒絕本次差異或證據；現行 manifest 與規則保持不變。

決定欄位只記錄人工 gate，不是規則寫入 API。產生報告、approve 或 reject 都必須維持 `writes_performed=false`。

## 執行方式與 exit code

在專案根目錄使用 PowerShell：

```powershell
uv lock --check
uv run --group audit pytest -q tests/test_rule_audit.py
uv run --group audit ltc-rule-audit `
  --output artifacts/rule-audit/2026-07-23-online.json
```

已有 P1 JSON 證據時，可完全離線產生 P2 人工複核報告：

```powershell
uv run --group audit ltc-rule-audit `
  --input artifacts/rule-audit/2026-07-23-online.json `
  --review-output artifacts/rule-audit/2026-07-23-review.md `
  --project-root .
```

CLI exit code：

- `0`：全部來源為 `VERIFIED_SNAPSHOT`，且 P2 跨檔一致性為 `CONSISTENT`（若有執行 P2）。
- `2`：至少一個來源為 `REVIEW_REQUIRED`，或 P2 偵測到跨檔漂移。
- `3`：至少一個來源為 `CHECK_UNAVAILABLE`。

## v0.2-P1 第一次線上查證

查證日期：2026-07-23

| 來源 | HTTP | raw hash | semantic fingerprint | 狀態 |
|---|---:|---|---|---|
| 2022-02-01 歷史條文 | 200 | 與核准 bytes 不同 | 相同 | `VERIFIED_SNAPSHOT` |
| 2026-07-01 完整快照 | 200 | 與核准 bytes 不同 | 相同 | `VERIFIED_SNAPSHOT` |
| 附表二給付額度 | 200 | 相同 | 相同 | `VERIFIED_SNAPSHOT` |
| 附表五部分負擔比率 | 200 | 相同 | 相同 | `VERIFIED_SNAPSHOT` |

四個結果皆為 `changed_fields=[]`、`errors=[]`、`writes_performed=false`。兩個 HTML 頁面的原始 bytes 會受官方動態頁面內容影響，但必要法規語意完全相同；兩份 PDF 則 raw 與 semantic 證據都相同。

完整 artifact 位於忽略版控的 `artifacts/rule-audit/2026-07-23-online.json`，供本機人工檢閱，不作為公開規則資料。作者已於 2026-07-23 逐項確認四個官方來源、版本日期、附表二 CMS 2–8 額度與附表五三類部分負擔，並明確核准 v0.2-P1；現可進入 P2，但任何後續規則修改仍須獨立產生差異證據並另行核准。

## v0.2-P2 複核報告

P2 使用上述 P1 JSON 證據離線產生 `artifacts/rule-audit/2026-07-23-review.md`。報告逐來源列出核准值、本次值、差異、影響規則與建議測試，另附跨檔一致性結果及人工決定欄位。

此流程不使用 LLM、不呼叫網路、不讀 `.env`，也不修改 `rules.py`、`eligibility.py`、`copay.py`、manifest 或公開文件中的規則值。工程驗證完成後，仍須作者明確核准 P2 才能進入排程與公開透明度工作。

## 執行與人工 gate

1. 核心 pytest 一律使用離線 fixture，不依賴外部網站。
2. 線上 checker 是獨立操作，不放進 Gradio 民眾請求路徑。
3. 稽核 artifact 預設放在忽略版控的位置；公開摘要不得含 token、個資、原始對話或不允許再散布的附件。
4. 只有作者檢查 `changed_fields` 並明確核准後，才能另外修改規則、測試、metadata、README 與正式 manifest。
5. 規則修改、人工核准、Git commit／tag／Release 都是分開的步驟；Agent 不執行 Git。
