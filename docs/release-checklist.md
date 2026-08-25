# 發布與公開驗收清單

本文件把專案完成後仍需由作者帳號操作的步驟集中在一處。Agent 不執行 Git、不建立託管應用，也不代填 Secrets。

目前 GitHub、local main 與 Hugging Face Space 的部署真相及安全更新順序，以 [Deployment lineage](deployment-lineage.md) 為準；以下清單保留各階段的歷史驗收紀錄，不重寫其時間順序。

## 目前公開狀態（2026-08-20）

- 狀態：`Frozen / Portfolio Complete`；最終產品版本維持 `v0.2.0`，annotated tag 與正式 Release 不移動。
- 2026-08-20 current-truth audit 為 4／4 `VERIFIED_SNAPSHOT`、`changed_fields=[]`、跨檔 `CONSISTENT`，沒有規則寫入。
- 本機 fresh gates：92 packages compatible、公開評估重建成功、pytest **585 passed**、sdist／wheel、離線 CLI 與 UI smoke 全部通過。
- 確定性金額主矩陣、PII 遮蔽、unknown CMS fail-closed、HITL approve／reject 與逐字發布契約的 343 項專項測試通過。
- 最新 `main` CI 與排程法規來源稽核成功；final closure 合併後以 branch protection 鎖定 `main`。
- 公開展示環境可喚醒至 Running，domain Ready，頁面只提供雲端模式，唯讀 smoke 的 browser console error 為 0。
- 同版雲端 20 題仍不重跑；既有雲端數字只保留為歷史基線，不是 closure blocker。

## 1. 本機最後驗證

在專案根目錄執行：

```powershell
uv lock --check
uv sync --locked --all-groups
uv pip check
uv run python scripts\export_public_evaluation.py
uv run pytest -q
uv build
```

預期結果：

- lock 沒有變動，所有已安裝套件相容。
- public evaluation exporter 顯示 `PUBLIC_EVAL_OK runs=2`。
- 完整測試通過；測試數若因後續新增測試而增加，以退出碼 0 為準。
- `dist/` 產生 sdist 與 wheel；`dist/` 已忽略，不需提交。

## 2. 作者自行整理 Git 變更

先確認 `.env` 仍被忽略，再檢查變更內容：

```powershell
git check-ignore -v .env
git status --short
git diff --check
```

既有功能與修正已分成小型 Conventional Commits 公開。本次只需提交最終驗收文件，建議訊息：

`docs: 完成 Phase 4 公開驗收紀錄`

每筆 commit 後可核對作者身分：

```powershell
git show -s --format="Commit: %h%nAuthor: %aN <%aE>%nCommitter: %cN <%cE>%nMessage: %s"
```

全部完成後由作者自行 Push：

```powershell
git push origin main
git status -sb
```

預期 `git status -sb` 顯示 `main...origin/main`，且沒有待提交檔案。

## 3. GitHub 公開驗收

Push 後檢查：

- 首頁最新 commit 與本機一致，README 圖片、Mermaid、連結及 badge 正常顯示。
- Actions 的 `CI` workflow 成功完成 lock check、585 項測試與 distribution build；後續測試數若增加，以退出碼 0 為準。
- Contributors 只顯示作者預期的帳號；commit 不含額外 `Co-authored-by`。
- repo 中沒有 `.env`、`artifacts/`、模型權重、GGUF 或 `dist/`。
- [公開評估摘要](../eval/results/local-models-v3.json)可開啟，且只有去識別化的確定性評分。

## 4. Hugging Face Space 建立與設定

建立 Gradio Space 後，使用此 repo 的根目錄內容。根目錄 README metadata 已指定 Python 3.11、Gradio 6.20.0 與 `app.py`。

在 Space Settings 設定：

- Secret：`GEMINI_API_KEY` 或 `GOOGLE_API_KEY`，二選一即可。
- Variable：`GEMINI_MODEL=gemini-3.5-flash-lite`。
- Variable：`GEMINI_THINKING_LEVEL=medium`；未填時程式也會使用 medium。

不要把金鑰寫進 README、一般 Variable、commit 或討論串。Space 會先透過 `requirements.txt` 安裝由 `uv.lock` 匯出的完整外部套件版本，之後才把 repository 複製到 `/app`；根目錄 `app.py` 會在啟動時載入 `src/`。因此 requirements 不可引用相鄰檔案，也不可使用 `-e .`。

Space 另會自動加入 `gradio[oauth,mcp]`、`uvicorn`、`websockets` 與 `spaces`。本專案已依 Gradio 6.20.0 MCP extra 把 Pydantic 限制在 `<2.12.5`；若調整 SDK 版本，發布前必須重新執行 extras resolver 模擬並確認公開 Build。

## 5. Space 公開頁面驗收

Build 完成後，以無痕視窗實際走一次：

1. 頁面只有雲端模式，沒有 F1／12B 地端選項，也不嘗試啟動 Ollama。
2. 以一位虛構家人開始，完成至少兩輪追問；不要輸入真實姓名、身分證、電話或地址。
3. CMS 未知時不出現個人化金額，只顯示 CMS 2–8 參考與 1966 指引。
4. 已知正式 CMS 時，試算明細由確定性工具產生。
5. 最終報告先停在完整預覽；approve 後內容逐字相同，reject 後不發布。
6. 手機寬度下輸入、追問、明細、來源與核准按鈕都可操作。

2026-07-23 公開驗收紀錄：

- 已知 CMS 4、一般戶、無外籍看護、服務費 18,000 元：政府給付 15,120 元、額度內部分負擔／合計自付 2,880 元、超額 0 元。
- unknown CMS：只顯示 CMS 2–8 額度參考、1966 與申請流程，沒有個人化給付或自付金額。
- approve 單次完成並顯示「已核准並發布」，沒有重複事件錯誤。

若 Build 失敗，先讀 Build logs；不要用放寬相依版本或刪除測試來掩蓋錯誤。

## 6. 可選：同版雲端 20 題

這不是公開上線的阻擋條件。現有雲端 `7 / 20` 是舊 workflow 歷史基線；若要和目前地端 v3 同版比較，必須另行核准 **US$1.776** 的最壞成本上限後再執行。沒有重跑前，不得把歷史雲端數字寫成最新三模型排名。

## 7. 已完成：`phase-4` tag 與 Release

只在 GitHub CI 與 Space 公開驗收都通過後建立：

```powershell
git tag -a phase-4 -m "release: 完成 Phase 4 公開驗收"
git push origin phase-4
```

Release notes 至少列出：可驗證／可稽核設計、規則快照、585 項測試、地端固定集結果、雲端結果版本邊界、Space 操作方式與免責聲明。tag／Release 是發布里程碑，不是程式功能本身。

2026-07-23 完成紀錄：

- annotated tag：`phase-4`
- 指向 commit：`2669eec`
- Release：[`Phase 4：長照 2.0 資格初篩與補助試算 Agent`](https://github.com/kuotunyu/ltc-benefit-agent/releases/tag/phase-4)
- GitHub 狀態：`Latest`

## 8. v0.2-P4 收尾

發布 `v0.2.0` 前依序確認：

- [x] 公開 smoke 時 GitHub 與公開 Space 指向同一核准 commit `de6777d`。
- [x] Windows CI 與手動法規來源稽核成功。
- [x] 本機 lock、相依、585 項測試、公開評估、離線 CLI 與 distribution build 通過。
- [x] 公開 Space 桌面與 390 px 手機版可載入，沒有水平溢位或 browser console error。
- [x] 以虛構資料重跑 known CMS 與 approve：CMS 4、第三類、政府給付 NT$15,120、合計自付 NT$2,880；核准後內容逐字一致，完成按鈕 disabled。
- [x] 以虛構資料重跑 unknown CMS 與 reject：只顯示 CMS 2–8 參考表，沒有個人化給付或自付；拒絕後顯示「草稿未發布」。
- [x] 公開驗收證據已同步至發布清單與 completion audit。
- [x] 最新 release candidate 已同步至公開原始碼倉庫與展示環境，CI／Build 通過。
- [x] 已建立不可變的 `v0.2.0` annotated tag／Release。
- [x] final closure 合併後已啟用 branch protection，禁止 force push／刪除並鎖定 `main`。

公開對話會使用雲端模型。執行前須用 `scripts/estimate_cloud_cost.py` 列出最壞成本，取得作者明確核准；不同意費用時不得以舊版公開 smoke 冒充 v0.2 證據。
