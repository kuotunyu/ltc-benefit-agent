# 發布與公開驗收清單

本文件把專案完成後仍需由作者帳號操作的步驟集中在一處。Agent 不執行 Git、不建立託管應用，也不代填 Secrets。

## 目前公開狀態（2026-07-23）

- 功能驗收基準 `55e872f` 與最終文件同步 `85a9461` 均已推送至 GitHub 與 Hugging Face Space；Space 為 Running。
- GitHub Actions 對上述兩個 commit 均顯示成功。
- 公開 Space 已通過已知 CMS 試算、unknown CMS 參考表與單次 HITL 核准發布。
- 最終本機驗證為 `uv lock --check`、91 packages compatible、pytest **514 passed in 4.64s**、sdist／wheel build 與離線 CLI approve 成功。
- 功能與公開驗收文件均已完成；`phase-4` tag／Release 與同版雲端 20 題皆為可選事項。

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
- Actions 的 `CI` workflow 成功完成 lock check、514+ 項測試與 distribution build；後續新增測試時以退出碼 0 為準。
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

Release notes 至少列出：可驗證／可稽核設計、規則快照、514+ 項測試、地端固定集結果、雲端結果版本邊界、Space 操作方式與免責聲明。tag／Release 是發布里程碑，不是程式功能本身。

2026-07-23 完成紀錄：

- annotated tag：`phase-4`
- 指向 commit：`2669eec`
- Release：[`Phase 4：長照 2.0 資格初篩與補助試算 Agent`](https://github.com/kuotunyu/ltc-benefit-agent/releases/tag/phase-4)
- GitHub 狀態：`Latest`
