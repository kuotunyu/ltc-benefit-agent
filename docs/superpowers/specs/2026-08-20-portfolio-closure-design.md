# Portfolio Closure Design

## 目標

在不修改資格規則、金額規則、Agent framework 或模型評測的前提下，將目前已通過 current-truth audit 的 `v0.2.0` 專案收斂為 `Frozen / Portfolio Complete`，並讓 GitHub、Hugging Face Space 與公開文件的狀態一致。

## 已核准事實

- `CURRENT_2026_07` 四個白名單官方來源在 2026-08-20 的唯讀稽核均為 `VERIFIED_SNAPSHOT`，沒有語意差異。
- 跨檔一致性為 `CONSISTENT`，稽核沒有執行規則寫入。
- `v0.2.0` annotated tag 與正式 Release 已存在。
- `main` 最新 CI 成功，完整本機測試為 585 passed。
- 公開 Space 可喚醒至 `RUNNING`，頁面僅提供雲端模式且 console error 為 0。
- GitHub `main` 尚未啟用 branch protection；Space 內容落後 GitHub 且仍含已從 GitHub 移除的內部規劃檔。

## 變更範圍

1. 更新封裝 audit status 的最後成功日期，不修改 manifest、semantic snapshot、hash、extractor 或 runtime rule constant。
2. 更新 README、release checklist、rules audit、source manifest 與 completion audit，使其反映 2026-08-20 的可重跑證據，並加入自然的第一人稱動機與 `Frozen / Portfolio Complete` 狀態。
3. 經由小型 PR 讓 GitHub CI 驗證 closure commit，合併後以 Space 專用 README metadata 建立部署 commit並同步至 Space。
4. 對 GitHub `main` 啟用保護：要求最新 CI、禁止 force push、禁止刪除、要求對話解決與線性歷史；最後將 branch 設為唯讀鎖定。

## 明確禁止

- 不新增 Agent framework。
- 不新增或重跑模型 benchmark。
- 不自動核准長照資格。
- 不擴大醫療或法律主張。
- 不因外部法規資訊自行改動 rule engine。
- 不移動或覆寫 `v0.2.0` tag／Release。
- 不執行付費模型 API 呼叫。

## 發布與錯誤處理

- 任一驗證 gate 失敗即停止發布，保留 branch 與證據供檢查，不降低 gate。
- Space 必須保留專用 YAML front matter；不得直接把無 metadata 的 GitHub README 推成 Space root README。
- branch protection 只在 closure PR 合併且 GitHub CI 成功後啟用，避免在交付完成前鎖住 `main`。
- 最終以 GitHub API、Space runtime API、公開頁面 smoke 與本機 fresh gates 共同確認狀態。

## 驗收條件

- current-truth audit：4/4 `VERIFIED_SNAPSHOT`、`changed_fields=[]`、`CONSISTENT`。
- 本機：lock、92 packages compatible、public evaluation、585 tests、build、offline CLI、desktop／390 px／approve smoke 全部成功。
- GitHub：closure PR 已合併、合併 commit CI 成功、`main` protected 且 locked、`v0.2.0` 不變。
- Space：內容與 closure commit 對齊（僅保留部署 metadata 差異）、runtime `RUNNING`、domain `READY`、僅雲端模式、console error 0。
- 公開文件明確標示 `Frozen / Portfolio Complete`，且不宣稱正式資格核定、醫療建議或法律意見。
