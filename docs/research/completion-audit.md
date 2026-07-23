# Phase 0–4 完成度稽核

查證日期：2026-07-23
範圍：`PLAN.md`、原始四階段交付、公開介面、測試與發布邊界。
方法：只以目前檔案、可重跑命令、raw／public evaluation artifacts 與實際 runtime 結果判定；不以開發意圖或 README 自述代替證據。

## 結論

Phase 0–4、GitHub 公開倉庫與 Hugging Face Space 均已完成並通過公開驗收。資格與金額規則、Agent／PII／HITL、三模式評估基礎、Gradio、三份對話範例、公開 CI、已知 CMS 試算、unknown CMS 防誤判與單次核准發布都有可重跑或公開端到端證據。剩餘事項只有可選的同版雲端 20 題重跑，以及作者自行決定是否建立 `phase-4` tag／Release；兩者都不是功能或發布缺口。

## Requirement matrix

| 範圍 | 原始要求 | 當前證據 | 判定 |
|---|---|---|---|
| 核心原則 | LLM 只理解、追問、選工具與彙整；資格與金額由 Python | `tools/` 不依賴 Agent framework；service 會攔截未核准幣值；336 組規則／金額主矩陣 | 完成 |
| Phase 0 | PLAN、append-only PROGRESS、三個基礎 project skills | [PLAN](../../PLAN.md)、[PROGRESS](../../PROGRESS.md)、project skills 目錄；目前六支 skills 在 `PYTHONUTF8=1` 下均由 `quick_validate.py` 驗證通過 | 完成 |
| Phase 1 | eligibility、copay、FAQ adapter／fallback、版本 metadata、uv／MIT／env 範本 | [tools](../../src/ltc_benefit_agent/tools)、[規則校對表](rules-audit.md)、`uv.lock`、`LICENSE`、`.env.example`；人工規則簽核 5／5 | 完成 |
| Phase 1 金額 | CMS 2–8、三福利類別、外籍看護 30%、整數捨去、超額 | `tests/test_copay.py` 與 336 組主矩陣；所有輸出為整數 | 完成 |
| Phase 2 | LangChain 1.x `create_agent`、provider factory、多輪 CLI | `agent/factory.py`、`service.py`、`cli.py`；Context7 與鎖定版本 API 已交叉查證 | 完成 |
| Phase 2 PII | model、tools、log、輸出前遮蔽；不保存 raw 對話 log | `privacy.py`、PII middleware／audit tests；公開掃描無 token、私密路徑或作者信箱 | 完成 |
| Phase 2 HITL | 確定性建稿、完整預覽、approve／reject；核准後逐字一致 | `reports.py`、`toolset.py`、service／HITL tests；12B adapter 換行回歸也鎖回 registry 原文 | 完成 |
| Phase 3 F1 | gated 原始權重、自轉 F16／Q4_K_M、Ollama 匯入 | [地端模型文件](../local-models.md)記錄 revision、GGUF SHA-256、正式 alias 與可重建命令 | 完成 |
| Phase 3 評估 | 固定 20 題、七項確定性指標、三模式背景比較 | [情境集](../../eval/scenarios.json)、evaluator、歷史雲端 artifact 紀錄與[公開地端摘要](../../eval/results/local-models-v3.json) | 完成；雲端最新 workflow 尚未同版重跑 |
| Phase 3 地端最終結果 | F1 與 12B 相容模式重跑 | 兩份 v3 raw artifacts 各 20 traces；公開摘要重新計分為端到端 20／20、金額題 13／13、PII 0 | 完成；只代表固定診斷集 |
| Phase 4 Gradio | 多輪聊天、provider、舊制、來源、明細、approve／reject | `ui/`、`app.py`、11 項 UI tests；桌機／390 px 手機多輪 smoke 為 `UI_SMOKE_OK`、console 0 error；常駐聊天面板不需另行展開歷史 | 完成 |
| Phase 4 文件 | 繁中 README、動機、Mermaid、快速開始、模型表、評估、成本、PII、授權、三份完整對話 | [README](../../README.md)與[三份範例](../examples) | 完成 |
| Phase 4 Space-ready | 根目錄 app、metadata、相依安裝、Space 僅雲端 | README YAML、由 `uv.lock` 匯出的 runtime constraints、[hosting 指引](../hosting.md)；公開 CPU Basic Space 已成功 Build 並 Running，頁面只提供雲端模式 | 完成並公開部署 |
| Phase 4 公開端到端 | 已知 CMS、unknown CMS、HITL 與完成狀態 | 已知 CMS 4 一般戶試算為政府給付 15,120 元、自付 2,880 元；unknown CMS 只顯示 2–8 參考表與 1966；單次 approve 後顯示「已核准並發布」 | 完成 |
| 打包 | 專案不只在現有 `.venv` 可用 | `uv build` 成功產生 sdist／wheel；全新 Python 3.11 venv 安裝 wheel 後，`ltc-benefit-agent --offline-demo --approve` 成功；wheel 無 `.env`／artifacts／models | 完成 |
| 公開 CI | Push／PR 後自動檢查，不使用模型或 Secrets | Windows runner、Python 3.11、uv 0.11.18；功能驗收基準 `55e872f` 與最終文件同步 `85a9461` 的 Actions 均為 `completed / success` | 完成 |
| 整體回歸 | lock、相依、tests、build、CLI、公開掃描 | `uv lock --check`、`uv pip check`（91 packages compatible）、完整 pytest **514 passed in 4.64s**、sdist／wheel build、離線 CLI approve 與公開文案掃描均通過 | 完成 |

## 尚待作者或另行核准

1. 若要公平比較目前三模式，新版雲端固定 20 題已按 8 calls／題、12k input／3k output 與當日單價重估為 **US$1.776** 上限；必須取得明確核准後才執行。現有雲端 `7 / 20` 僅是舊 workflow 歷史基線。
2. 作者可自行決定是否建立 `phase-4` tag／Release；這是發布里程碑，不是程式功能缺口。

## 可重跑的核心命令

```powershell
uv lock --check
uv sync --locked --all-groups
uv run pytest -q
uv run python scripts\export_public_evaluation.py
uv run ltc-benefit-agent --offline-demo --approve
```
