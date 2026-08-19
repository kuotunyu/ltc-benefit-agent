# Portfolio Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將已通過 current-truth audit 的 v0.2.0 專案收斂為 GitHub、Space 與公開文件一致的 `Frozen / Portfolio Complete` 狀態。

**Architecture:** 不修改產品 runtime；只更新既有 audit evidence metadata 與公開 closure 文件。發布沿用 GitHub PR／CI，Space 使用專用 README metadata 建立部署 commit，最後以 GitHub branch protection 鎖定 `main`。

**Tech Stack:** Python 3.11、uv 0.11.18、pytest、GitHub Actions／CLI、Hugging Face Space、Playwright。

## Global Constraints

- Windows 11 原生，以 uv 管理虛擬環境。
- 禁止新增 agent framework。
- 禁止新增模型 benchmark 或付費模型呼叫。
- 禁止自動核准資格。
- 禁止擴大醫療／法律 claim。
- 禁止因新法規自行修改 rule engine。
- 只在官方來源沒有 snapshot 後實質語意差異時繼續。
- commit 使用 Conventional Commits 與正體中文。

---

### Task 1: 同步 current-truth 與 portfolio closure 文件

**Files:**
- Modify: `README.md`
- Modify: `docs/release-checklist.md`
- Modify: `docs/research/completion-audit.md`
- Modify: `docs/research/rule-source-manifest.md`
- Modify: `docs/research/rules-audit.md`
- Modify: `src/ltc_benefit_agent/audit/data/approved-audit-status-v1.json`
- Modify: `tests/test_rule_audit.py`

**Interfaces:**
- Consumes: 2026-08-20 4/4 `VERIFIED_SNAPSHOT`、`CONSISTENT`、585 tests、GitHub／Space live evidence。
- Produces: 與 manifest 語意不變、可由現有 consistency checker 驗證的公開 closure 狀態。

- [x] **Step 1: 更新 audit evidence 日期**

將 `approved-audit-status-v1.json` 的 `last_successful_audit_date` 從 `2026-07-23` 改為 `2026-08-20`，並同步 packaged status 的真實輸出斷言；保留 `manifest_version`、source counts 與 `writes_performed=false` 不變。

- [x] **Step 2: 更新 README 首段與狀態**

在 README 標題與 badges 後加入第一人稱家庭照護／高齡社會動機，以及：

```markdown
> **狀態：Frozen / Portfolio Complete（2026-08-20）**
```

保留非正式核定免責聲明，不新增任何醫療或法律結論。

- [x] **Step 3: 修正 release 與 research 文件的舊狀態**

把「v0.2.0 尚待建立」、514 tests、91 packages、缺失的 `PLAN.md`／`PROGRESS.md` 連結改為 fresh evidence；加入 GitHub protection 與 Space 同步在發布後核對的明確 gate。

- [x] **Step 4: 執行文件與 consistency 驗證**

Run:

```powershell
uv run pytest -q tests/test_rule_audit.py tests/test_rules_and_architecture.py
uv run --locked --group audit ltc-rule-audit --input "$env:TEMP\ltc-benefit-agent-current-truth\audit-2026-08-20.json" --project-root . --quiet
git diff --check
```

Expected: pytest exit 0、`project_consistency: CONSISTENT`、diff check exit 0。

- [x] **Step 5: Commit**

```powershell
git add README.md docs/release-checklist.md docs/research/completion-audit.md docs/research/rule-source-manifest.md docs/research/rules-audit.md src/ltc_benefit_agent/audit/data/approved-audit-status-v1.json tests/test_rule_audit.py
git commit -m "docs: 完成作品集封存驗收"
```

### Task 2: 重跑全部 gates 並發布 GitHub PR

**Files:**
- Verify: repository-wide

**Interfaces:**
- Consumes: Task 1 closure commit。
- Produces: 可合併的 GitHub PR 與完整 fresh verification evidence。

- [x] **Step 1: 執行完整本機 gates**

Run:

```powershell
uv lock --check
uv sync --locked --all-groups
uv pip check
uv run python scripts\export_public_evaluation.py
uv run pytest -q
uv build
uv run ltc-benefit-agent --offline-demo --approve
```

Expected: 92 packages compatible、`PUBLIC_EVAL_OK runs=2`、585 passed、sdist／wheel 成功、offline demo exit 0。

- [x] **Step 2: 執行桌機／行動版／approve smoke**

Run:

```powershell
$env:GRADIO_SERVER_PORT = "7861"
$env:UI_FIXTURE_REPORT = "1"
$env:UI_SMOKE_TEST_APPROVAL = "1"
$env:UI_SMOKE_URL = "http://127.0.0.1:7861"
uv run python "$env:USERPROFILE\.codex\skills\webapp-testing\scripts\with_server.py" --server "uv run python scripts\ui_fixture_app.py" --port 7861 --timeout 60 -- uv run python scripts\ui_smoke.py
```

Expected: `UI_SMOKE_OK`。

- [ ] **Step 3: Push branch 並建立 PR**

```powershell
git push -u origin codex/portfolio-closure
```

PR title：`docs: 完成作品集封存驗收`；base `main`、head `codex/portfolio-closure`。

- [ ] **Step 4: 等待 PR CI 後合併**

Expected: PR workflow `CI / test` success；以 squash 或 merge 保留 Conventional Commit 意義，合併後 `origin/main` 包含 closure 文件。

### Task 3: 同步並驗證 Hugging Face Space

**Files:**
- Deploy-only: Space root `README.md` 由 `deploy/space/README.md` front matter 加 GitHub `README.md` body 組成。

**Interfaces:**
- Consumes: 已合併且 CI 成功的 GitHub `main`。
- Produces: Space source 與 GitHub closure tree 對齊，唯一預期差異為 root README front matter。

- [ ] **Step 1: 產生 Space 部署 branch**

以 GitHub merge commit 建立暫時部署 branch，使用 `deploy/space/README.md` 的 YAML front matter 加上 GitHub README body，避免遺失 Space SDK metadata。

- [ ] **Step 2: 驗證部署 tree**

確認 `.claude/`、`PLAN.md`、`PROGRESS.md` 不再存在於部署 tree，`app.py`、`requirements.txt` 與 runtime source 與 GitHub `main` 相同。

- [ ] **Step 3: Push Space 並等待 Build**

推送部署 branch 至 `space/main`，等待 runtime API 回報 `RUNNING`、domain `READY`、sha 等於新部署 commit。

- [ ] **Step 4: 公開唯讀 smoke**

以瀏覽器載入公開 Space，不送出對話；確認標題存在、模型選項只有「雲端模式」、console error 0。

### Task 4: 啟用並鎖定 GitHub main

**Files:**
- External configuration: GitHub branch protection for `main`

**Interfaces:**
- Consumes: GitHub closure merge CI success、Space deployment success。
- Produces: protected and read-only `main`。

- [ ] **Step 1: 取得實際 required status context**

Run:

```powershell
gh api repos/kuotunyu/ltc-benefit-agent/commits/main/check-runs --jq ".check_runs[].name"
```

Expected: `test`。

- [ ] **Step 2: 設定 branch protection**

使用 GitHub REST branch protection：strict required status `test`、linear history、conversation resolution、禁止 force push、禁止刪除，並設定 `lock_branch=true`。

- [ ] **Step 3: 最終 read-only 驗證**

Run:

```powershell
gh api repos/kuotunyu/ltc-benefit-agent/branches/main
gh api repos/kuotunyu/ltc-benefit-agent/branches/main/protection
gh release view v0.2.0 --repo kuotunyu/ltc-benefit-agent
git status -sb
```

Expected: `protected=true`、branch locked、`v0.2.0` tag／Release 不變、本機無未提交變更。
