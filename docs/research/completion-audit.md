# Final Portfolio Closure Audit

查證日期：2026-08-20

狀態：`Frozen / Portfolio Complete`

範圍：Git、CI、`v0.2.0` Release、公開展示環境、`CURRENT_2026_07` provenance、official-source hashes、deterministic calculations、PII、HITL 與 branch protection。

## 結論

`v0.2.0` 的產品與發布範圍已封存。2026-08-20 current-truth audit 沒有發現 2026-07 snapshot 後會改變本專案資格、照顧及專業服務月額或部分負擔語意的官方來源差異，因此沒有啟動 rule engine 更新。最終 closure 只更新稽核日期、公開文件、展示環境同步與 GitHub branch protection。

這個狀態不代表正式資格核定，也不把固定測試集結果延伸為公開環境的零風險保證。最終資格、CMS、福利類別與核定金額仍由照管中心、地方主管機關與 1966 確認。

## Current-truth matrix

| Gate | Fresh evidence | 結果 |
|---|---|---|
| Git | closure 前 `main=origin/main=79fa210`、worktree clean；closure 以 feature branch／PR 交付 | 通過 |
| CI | 最新 `main` CI success；closure PR 與 merge commit 另以同一 Windows workflow 驗證 | 通過 |
| Release | `v0.2.0` annotated tag 指向 `2d53856`；Release 非 draft、非 prerelease | 通過；不移動 |
| 官方來源 | 4／4 `VERIFIED_SNAPSHOT`、`changed_fields=[]`、`writes_performed=false` | 通過 |
| Raw／semantic hash | 兩個 HTML raw hash 因網站 bytes 改變，但 semantic fingerprint 相同；附表二與附表五 raw／semantic hash 均相同 | 通過 |
| 跨檔一致性 | manifest、runtime constants、README、fixtures、tests 為 `CONSISTENT` | 通過 |
| 相依 | `uv lock --check`、92 packages compatible | 通過 |
| 完整測試 | pytest **585 passed** | 通過 |
| 金額契約 | 兩版 × CMS 2–8 × 三類 × 外籍看護 × 四種支出情境的 336 組矩陣，加上無條件捨去測試 | 通過 |
| PII | 支援的臺灣身分證、電話、標示姓名遮蔽；public inputs 不接受 PII 欄位；固定診斷集洩漏 0 | 通過；不宣稱零風險 |
| HITL | 未核准金額阻擋、approve／reject、registry 防竄改、adapter 換行回歸、發布內容與預覽逐字一致 | 通過 |
| Unknown CMS | 只提供 CMS 2–8 參考，不產生個人化金額 | 通過 |
| Build／CLI | sdist、wheel 與 `--offline-demo --approve` exit 0 | 通過 |
| UI | 桌機、390 px、設定與 approve smoke 為 `UI_SMOKE_OK` | 通過 |
| 公開展示 | CPU Basic runtime 可喚醒至 `RUNNING`、domain `READY`、僅雲端模式、console error 0 | 通過 |
| Branch protection | final closure 合併後要求 CI、線性歷史與對話解決，禁止 force push／刪除並鎖定 `main` | 通過 |

## 安全契約

### 確定性金額

照顧及專業服務額度、外籍看護 30% 調整、部分負擔、超額自費與合計自付全部由 Python 整數運算產生。外籍看護額度與部分負擔都使用整數乘法後除以 100，符合無條件捨去；模型輸出的未核准幣值不能取代工具結果。

### PII 邊界

PII middleware 與 service boundary 會遮蔽已支援的臺灣身分證、電話及標示姓名模式，工具與公開輸入 schema 也不接受不必要的 PII 欄位。這是 defense-in-depth，不是收集真實個資的授權；公開頁面仍明確要求不要輸入姓名、身分證、電話或地址。

### HITL verbatim lock

確定性 renderer 先建立完整 Markdown 草稿與 content-derived report ID。只有 registry 中相同 ID 與逐字相同內容能發布；approve 回傳人工看到的 preview 原文，reject 不發布，重複 approve 只回傳既有發布內容。

## Frozen boundary

- 不新增 Agent framework。
- 不新增或重跑模型 benchmark。
- 不自動核准資格。
- 不擴大醫療或法律主張。
- 不因新法規資訊自動修改 rule engine。
- 不移動或覆寫 `v0.2.0` tag／Release。
- 每月 rule-source audit 保留唯讀監測；任何 `REVIEW_REQUIRED` 或 `CHECK_UNAVAILABLE` 都只產生差異證據並停止。

## 可重跑命令

```powershell
uv lock --check
uv sync --locked --all-groups
uv pip check
uv run python scripts\export_public_evaluation.py
uv run pytest -q
uv build
uv run ltc-benefit-agent --offline-demo --approve
```
