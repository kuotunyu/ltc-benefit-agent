# 法規來源 manifest 與稽核結果契約

版本：schema v1

建立日期：2026-07-23

狀態：v0.2-P0 契約，尚未建立正式核准 manifest。

## 目的

此契約讓專案能以確定性方式判斷「官方來源是否仍與核准快照一致」，並把真正的規則更新決策留給人工。checker 只產生證據，不會直接修改資格、額度、部分負擔或進位規則。

## `RuleSourceManifest`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `schema_version` | string | 固定 schema 版本，例如 `1` |
| `source_id` | string | 專案內穩定且唯一的來源 ID |
| `title` | string | 官方文件或附件名稱 |
| `canonical_url` | HTTPS URL | 經人工核准的官方來源；checker 不接受任意 URL |
| `rule_version` | enum | `LEGACY_2022` 或 `CURRENT_2026_07` |
| `effective_date` | ISO date | 此來源對應內容的生效日或完整快照基準 |
| `verified_at` | ISO datetime | 上一次人工核准的查證時間 |
| `raw_sha256` | hex string | 核准檔案原始 bytes 的 SHA-256 |
| `semantic_fingerprint` | hex string | 必要結構化欄位正規化後的 SHA-256 |
| `extractor_version` | string | 產生結構化欄位的 extractor 版本 |
| `impacted_rule_ids` | string[] | 可能受影響的資格、額度或部分負擔規則 ID |

正式 manifest 會在 v0.2-P1 完成官方來源實跑與人工核對後建立；P0 不填入推測的雜湊。

## `RuleAuditResult`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `source_id` | string | 對應 manifest 的來源 ID |
| `checked_at` | ISO datetime | 本次檢查時間 |
| `status` | enum | 三態之一 |
| `fetch_result` | string | 成功、逾時、拒絕、格式不可讀等可稽核結果 |
| `http_status` | integer/null | 線上檢查的 HTTP status；離線 fixture 可為 null |
| `raw_sha256_actual` | string/null | 本次原始內容雜湊 |
| `semantic_fingerprint_actual` | string/null | 本次結構化內容雜湊 |
| `changed_fields` | object[] | 欄位路徑、核准值、本次值與影響說明 |
| `errors` | string[] | 不含秘密或個資的錯誤摘要 |
| `writes_performed` | boolean | 必須固定為 `false` |

## 狀態判準

### `VERIFIED_SNAPSHOT`

- 官方來源或離線 fixture 可完整讀取。
- extractor 成功取得全部必要欄位。
- 必要結構化欄位與已核准 manifest 相同。
- raw SHA-256 可以不同；若差異只來自排版或 metadata，仍須由結構化比較證明規則內容一致。

### `REVIEW_REQUIRED`

- 資格門檻、額度、部分負擔、施行日或其他必要欄位不同。
- 必要欄位缺漏、表格結構改變，或 extractor 版本／行為漂移。
- checker 只列出差異與影響；不得自動更新 manifest 或規則常數。

### `CHECK_UNAVAILABLE`

- 官方來源無法連線、逾時、被拒絕、格式不可讀或檢查未完成。
- 此狀態表示「沒有得到結論」，不能視為快照仍有效。
- 已核准快照不因暫時的來源故障而自動改變。

## 執行與人工 gate

1. 核心 pytest 一律使用離線 fixture，不依賴外部網站。
2. 線上 checker 是獨立操作，不放進 Gradio 民眾請求路徑。
3. 稽核 artifact 預設放在忽略版控的位置；公開摘要不得含 token、個資、原始對話或不允許再散布的附件。
4. 只有作者檢查 `changed_fields` 並明確核准後，才能另外修改規則、測試、metadata、README 與正式 manifest。
5. 規則修改、人工核准、Git commit／tag／Release 都是分開的步驟；Agent 不執行 Git。
