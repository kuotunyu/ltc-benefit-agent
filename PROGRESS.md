# PROGRESS — ltc-benefit-agent 進度日誌

## 🧭 快速回憶區（上次收工：2026-07-22）

- **現在做到哪**：Phase 2／Phase 4 與三模式固定 20 題工程均完成；Phase 3 已通過工程 review，並補上一般讀者可理解的評估口徑，停在作者驗收閘門。作者已建立空的公開遠端 repo並初始化本機 `main`；尚未 commit／Push，公開前仍有五項法規人工校對待作者完成。
- **實跑總證據**：`uv lock --check`、locked sync、compileall 通過；pytest **476 passed in 2.91s**。六支 project skills、公開文案與秘密掃描均通過。
- **Context7**：全域 MCP 已啟用 OAuth；已用 `/websites/langchain_oss` 查證 `create_agent`／HITL、PII、`init_chat_model`。新增 `verify-external-api` project skill，驗證通過。
- **本機 20 題**：12B adapter 為追問 12、選工具 5、參數 17、金額 19、PII 0、HITL 4、端到端 3；F1 為 18、0、12、14、0、0、0。
- **雲端 20 題**：追問 10、選工具 12、參數 19、金額 19、PII 0、HITL 10、端到端 7；S08／S15 的不合法報告發布被 registry 擋下並誠實計為失敗。
- **金額口徑**：20 題中 13 題應試算、7 題不得試算；真正金額一致為雲端 12／13、F1 7／13、12B adapter 12／13，README 已避免把 19／20 誤讀為算了 20 題。
- **下一步**：
  1. 作者依建議檔案群組建立小型 Conventional Commits；先不 Push。
  2. 作者檢視三模式結果並確認 Phase 3；確認後才建議建立 `phase-3` tag。
  3. 作者依 `docs/research/rules-audit.md` 人工複核五項規則；Agent 不得代勾。
  4. 人工規則簽核後再跑一次整體 release review，接著由作者自行 Push／建立 tag。
- **成本**：兩次 S14 保守上限合計 US$0.09；本次 20 題批次核准上限 US$0.90、實際帳單未知且尚未跑完，累計保守授權上限 US$0.99。
- **待使用者 Git 操作**：Agent 未執行任何 Git 指令；小功能 commit 與 Phase tag 仍由作者自行處理。
- **⚠️ 已知坑**：雲端專案有 15 requests/minute 限制，診斷固定共用 12/min limiter；3B 不可靠地進入建稿／HITL。合併 artifact 保留四段 partial run 的中止原因；`.env` 真值從未印出、覆寫或提交。

## 📜 Phase 日誌（append-only）

### Phase 0 — 文件與 project skills（作者已驗收）

- **2026-07-22（開始）**：
  - 完成內容：唯讀盤點 workspace、姊妹作、官方法規、LangChain middleware、Gemini 模型與 F1 模型來源；與作者鎖定兩版規則、unknown CMS、試算基礎、地端模型、20 題評估、文件／skill 結構及 Space-ready 邊界。
  - 驗證證據：workspace 起始只有 `AGENTS.md`、`CLAUDE.md` 與既有 `.env`；`.env` 未讀取。確認 Ollama 0.32.0 正在服務、`gemma3:12b` 已安裝；GPU／磁碟僅做唯讀盤點。
  - 初始化狀態：`skill-creator/init_skill.py` 已建立三個 SKILL.md 骨架；首次 metadata 產生因三段 `short_description` 各少於 25 字元而停止，未產生錯誤內容，待正式文案完成後重跑 generator。
  - 決策變更：建立 `PLAN.md` D1–D12；沒有偏離作者核准的正式計畫。
  - Git：Agent 未執行任何 Git 指令；待 Phase 0 驗收後提供建議 commit 訊息。
  - 實際成本：$0，沒有 API 呼叫。

- **2026-07-22（工程驗證）**：
  - 完成內容：建立 `PLAN.md`、`PROGRESS.md`，以及 `resume-context`、`update-progress`、`review-phase` 的 `SKILL.md` 與 `agents/openai.yaml`，共 8 個 Phase 0 產物。
  - 實跑證據：三支 skill 分別執行 `quick_validate.py`，退出碼皆為 0 且輸出 `Skill is valid!`；快速回憶區實測 9 行；`pyproject.toml`、`uv.lock`、`src/`、`tests/` 均不存在，確認未跨入 Phase 1。
  - Windows 相容性：metadata generator 由於系統 Python 的 CP950／使用者 site 編碼先失敗，改以不載入 user site 的 UTF-8 模式 `python -s -X utf8` 後，三份 metadata 全數產生並驗證成功；未修改全域設定。
  - Phase gate：PLAN 的前四項 Phase 0 DoD 已有證據；最後一項「作者驗收」仍未完成，因此沒有把 Phase 0 標成已核准。
  - 決策變更：無，維持 PLAN D1–D12。
  - Git：Agent 未執行任何 Git 指令。建議 commit 訊息為 `docs: 建立專案藍圖與 Phase 0 skills`；建議 tag 為 `phase-0`，僅在作者驗收後自行處理，commit hash 待作者回填。
  - 實際成本：$0；沒有 API 呼叫、模型下載、套件安裝或 GPU 工作。

### Phase 1 — 確定性工具層（工程完成，待作者驗收）

- **2026-07-22（開工與查證）**：
  - 作者明確核准進入 Phase 1；Phase 0 gate 完成。
  - 環境：uv 0.11.18 已有 managed CPython 3.11.15，無需下載 Python；用 `uv init --lib --vcs none` 建立專案，沒有初始化或操作 Git。
  - 外部 API 文件：目前環境沒有 Context7 callable tool，依 CLAUDE fallback 改查 pytest 與 uv 官方文件。
  - 官方規則：核對 2022 歷史條文、現行條文、附表二、附表五、1966 指引及 2025 修法對照表。新增 PLAN D13：PAC 為短期需求例外；團體家屋在舊制已依 2020 函釋排除、現制明文化。

- **2026-07-22（實作與工程驗證）**：
  - 完成內容：`rules.py` 兩版 metadata；`eligibility.py` 保守初篩；`copay.py` 全整數試算與 unknown CMS 參考表；`faq_search.py` 的 HybridRetriever adapter／standalone fallback；`.gitignore`、空白金鑰 `.env.example`、MIT LICENSE、uv lock、繁中 README 與規則人工校對表。
  - 個資處理：uv 產生器曾從全域設定帶入作者 email，已在首次公開 metadata 檢查時移除；公開檔案掃描未發現該 email、秘密或佔位文字。既有 `.env` 未讀取或覆寫。
  - 實跑證據：`uv lock --check` 與 `uv sync --locked` 成功；CPython 3.11.15；`compileall` 通過；pytest **442 passed in 0.32s**。其中金額主矩陣 336 組，另含資格邊界、PAC 短期例外、非法輸入、FAQ schema 與架構限制。
  - smoke 證據：49 歲失智者在舊制為 `PRELIMINARY_CRITERIA_NOT_MET`、現制為 `POTENTIALLY_ELIGIBLE_TO_APPLY`；CMS 4 第三類、預計 12,000 元算得政府給付 10,080、自付 1,920；有外看且預計 7,000 元算得調整額度 5,574、政府給付 4,683、超額 1,426、總自付 2,317；FAQ fallback 命中申請流程且 URL 為 HTTPS。
  - 已知非產品錯誤：第一次展示 smoke 的 PowerShell 巢狀引號被吃掉而退出 1；改用相容引號後同一案例退出 0。中文標籤在 CP950 console 顯示亂碼，因此最終 FAQ smoke 改以布林斷言輸出 `faq_ok True True`。
  - Phase gate：PLAN 的前四項 Phase 1 DoD 已有證據；最後一項需本次展示與作者確認，因此仍未標成已驗收。人工規則簽核表保持未勾選，沒有冒稱人工複核完成。
  - 決策變更：新增 PLAN D13，沒有其他偏離核准計畫。
  - Git：Agent 未執行任何 Git 指令。建議依功能拆分 commit，Phase 驗收後建議 tag `phase-1`；commit hash 待作者回填。
  - 實際成本：$0；沒有 API 呼叫、模型下載、GPU 工作或 server 啟動。

### Phase 2 — Agent、middleware 與 CLI（工程完成；雲端 smoke 待核准）

- **2026-07-22（官方 API 與實作）**：
  - 作者睡前授權本次夜間工作跨 Phase 接續；PLAN 新增 D14，付費、gated 授權與帳號操作仍維持原 gate。
  - Context7 在本環境沒有 callable tool，依守則 fallback 查官方現行文件與已安裝 signature；鎖定 Agent framework 1.3.14、graph runtime 1.2.9、雲端 connector 4.3.0、地端 connector 1.1.0。
  - 完成 provider factory、多輪 checkpointer、`eligibility_check`／`copay_estimate`／`faq_search`、確定性 `build_report_draft`、逐字 registry、受 HITL 攔截的 `publish_report`、CLI 與離線 demo。
  - PII：框架 middleware 加台灣身分證、電話、標籤式姓名偵測；入口、tool、output 與 audit 另防禦遮蔽，log 不保存 raw message。真實 trace 發現官方 FileId 被市話 regex 誤判，依 D17 收窄區碼並補回歸測試。
  - 真實本機模型會在 publish 後摘要 tool result，依 D16 由 service 對外鎖定人工預覽；approve 完全一致、reject 不執行發布，registry 會拒絕一字不同的報告。

- **2026-07-22（驗證與成本 gate）**：
  - Phase 2 專屬 pytest 10 passed：多輪追問／thread 隔離、錯誤 tool args、unknown CMS、舊現制比較、PII 進 model／log 前遮蔽、approve／reject 與報告 schema。
  - CLI 實跑 `uv run python -m ltc_benefit_agent.agent --offline-demo --approve`，CMS 4 第三類、服務費 12,000 的預覽與最終報告逐字相同：政府 10,080、自付 1,920。
  - 官方 2026-07-22 標準文字單價下，保守 6 calls × 12k input／3k output：單題上限 US$0.045、20 題 US$0.90。未取得作者費用確認，沒有雲端 smoke 或批次。
  - Git：Agent 未執行任何 Git 指令。建議 commit：`feat(agent): 加入多輪工具與人工核准流程`；Phase 2 tag 待作者驗收。
  - 實際 API 成本：US$0。

### Phase 3 — 地端模式與固定診斷集（兩個地端模式完成；雲端待成本 gate）

- **2026-07-22（資源、F1 gate 與可重現腳本）**：
  - 重查 RTX 4090 24 GB、磁碟約 247 GiB 可用、既有模型與程序；未停止任何服務。官方模型頁確認 F1 repo 需接受條款。
  - 建立 `scripts/prepare_f1_ollama.py`：預設只做資源與 gated access dry-run；真正下載需 `--execute --accepted-license`。固定官方權重 revision、llama.cpp `b9637` source archive、F16 → Q4_K_M、Windows CUDA binary、Hermes template、SHA-256 manifest，產物留在 repo 外。
  - check-only 實跑：GPU／磁碟通過；HF dry-run 回報尚未取得 gated 權重。沒有下載模型、source archive 或 GGUF，也沒有自行接受條款。

- **2026-07-22（20 題與本機基準）**：
  - 建立 `eval/scenarios.json` 固定 20 題與確定性 evaluator，分開計追問、工具選擇、參數、金額、PII、HITL、端到端；雲端 runner 沒有 `--allow-cloud` 會硬拒絕。
  - 原始 `gemma3:12b` 實測回 400「不支援 tools」。依 D15 建立 `ltc-gemma3-tools:12b` 明示相容模板，重用既有權重 layer；`ollama show` 確認新增 tools capability。
  - 單題 S14 實跑 7 指標全通過；完整 20 題結果：12／5／17／19／0 leaks／4／3。主要失敗是小模型建稿後未發布、追問不足與一題惡意指令拒絕工具；S08 的竄改報告被 registry 正確擋下。
  - 完整 trace 存於 ignored `artifacts/eval/gemma3-20.json`。README 明示 adapter 與 20 題小樣本限制，不借用原模型卡成績。
  - 新增 project skill `run-diagnostic-eval`，依 skill-creator 初始化並由 `quick_validate.py` 驗證 `Skill is valid!`。
  - Git：Agent 未執行。建議 commit：`test(eval): 建立固定二十題 trace 評估`；F1 與雲端未完成，因此不建議把 Phase 3 標為完整 tag。
  - 實際 API 成本：US$0；只使用本機 GPU。

- **2026-07-22（F1 授權重新驗證）**：
  - 作者提供模型頁畫面，顯示 gated access 已核發；腳本按用途載入既有 `.env`，沒有印出或修改 token。
  - check-only 實跑成功：revision `32e8791e9446e92b3513551201c11f9119652fd5`、待下載 7,230,836,867 bytes；RTX 4090 24 GB、磁碟約 246.3 GiB 可用。
  - 輸出 `CHECK_ONLY_OK` 且退出碼 0，確認權限 gate 已解除；仍未下載權重、轉檔或匯入模型，等待作者明確核准執行。
  - 決策變更：無；沿用 D14 的外部授權 gate 與既有下載流程。Git 未執行，API 成本 US$0。

- **2026-07-22（F1 下載、轉檔與匯入）**：
  - 作者明確核准下載與匯入；腳本從既有 `.env` 按用途載入 `HF_TOKEN`，沒有印出、覆寫或提交秘密。下載官方 revision `32e8791e9446e92b3513551201c11f9119652fd5`，原始下載量 7,230,836,867 bytes。
  - F16 GGUF 為 7,221,693,984 bytes、SHA-256 `03b7ebeca3b12a588b84ccdf07c22e4bb4f9afb2b11dbcb0dfd71ce1161effb9`；Q4_K_M 為 2,241,005,088 bytes、SHA-256 `e17cf199a458cffa617073cb71df2bce02867e7622b685a7bef1c4dcec32035a`。匯入 `ltc-f1:q4_k_m` 後實查 capabilities 為 completion／tools。
  - Windows 修正：首次 converter subprocess 誤繼承另一個 Python 3.10 環境，僅停止本次 converter PID；腳本改為強制 `uv run --python 3.11 --managed-python` 並移除 `VIRTUAL_ENV`。量化後 DLL 掃描原本範圍過大，改只掃 llama.cpp binary 目錄。兩項均有回歸測試。
  - 內嵌 Jinja template 在目前地端服務對 `tools` request 回 500，依官方 Modelfile／tool calling 文件與公開 issue，保留專案 Go/Hermes adapter。診斷用 `ltc-f1-embedded:q4_k_m` alias 與單一臨時 Modelfile 已精確移除；正式模型與 GGUF 均保留，C 槽尚餘約 223.2 GiB。

- **2026-07-22（F1 固定 20 題與安全閘門）**：
  - 先以 S14 smoke 證實能連續正確呼叫 `eligibility_check` 與 `copay_estimate`，但隨後跳過建稿／HITL 並自行生成錯誤金額。依 PLAN D18 新增服務層硬閘門：未經 renderer 與人工核准的 AI 文字若含幣值或百分比，一律不對外顯示；核准報告仍逐字通過。
  - 最終相同 20 題實跑無 runtime error：追問 18／20、工具選擇 0／20、參數 12／20、金額一致 14／20、PII 洩漏 0、HITL 0／20、端到端 0／20；7 題有資格→金額連續工具，7 段未核准金額輸出被硬閘門攔截。trace 存於 ignored `artifacts/eval/f1-20-final.json`。
  - 實跑驗證：`uv lock --check`、`uv sync --locked --all-groups`、compileall 成功；修正 UI FakeService 契約後全套 pytest **467 passed in 3.08s**。新增 project skill `prepare-f1-ollama`，依 skill-creator 初始化且 `quick_validate.py` 輸出 `Skill is valid!`。F1 本機下載與推論沒有 API 費用；雲端呼叫仍為 0，未越過 US$0.045／US$0.90 成本 gate。
  - Phase 狀態：F1 轉檔、真實連續工具與地端評估已有證據；雲端 smoke／20 題尚待作者費用核准，因此 Phase 3 不標成完成。Agent 未執行 Git；建議 commit `feat(local): 加入量化地端模型與金額安全閘門`，Phase 3 tag 暫不建議建立。

- **2026-07-22（review-phase 部分驗收）**：
  - F1 子交付通過：ignored trace 讀回 20 筆且 metrics 與 README 完全一致；正式 alias 實查為 3.6B Q4_K_M 並具 completion／tools；README 本機連結全數存在。
  - 公開 README 特定供應商／產品名掃描無命中；排除 `.env`、`.venv` 與 ignored artifacts 後，token-shaped 值掃描無命中、repo 無超過 50 MiB 檔案。五支 project skills 全數通過 `quick_validate.py`。
  - `.env` 只做不揭露值的布林檢查：`HF_TOKEN_CONFIGURED=True`、`OLLAMA_F1_MODEL_READY=False`；Agent 沒有修改使用者檔案，作者需自行把模型 alias 設為 `ltc-f1:q4_k_m`。
  - Gate 結論：F1 下載／轉檔／匯入／診斷工程完成，Phase 3 整體仍未通過，唯一外部 gate 是作者尚未核准付費雲端 smoke／批次；人工規則複核另保持未完成。沒有 Git 或付費 API 操作。

- **2026-07-22（作者完成 `.env` 模型設定）**：
  - 依作者通知做不揭露值的布林檢查：`HF_TOKEN_CONFIGURED=True`、`OLLAMA_F1_MODEL_READY=True`。GPU 當時 0% 使用、約 1.9／24 GiB VRAM，C 槽約 223.1 GiB 可用。
  - 未加臨時環境覆寫，透過正式 evaluation CLI 跑 S14；trace 確認實際選到 `ltc-f1:q4_k_m`、4.11 秒完成、無 runtime error／PII 洩漏。該次只正確呼叫 `eligibility_check` 後停止，未進入 copay／建稿／HITL，再次顯示小模型多步不穩定，不改寫既有 20 題正式成績。
  - `.env` 串接 gate 已解除；付費雲端 gate 與人工規則複核仍待作者決定。Agent 未執行 Git，API 成本仍為 US$0。

- **2026-07-22（雲端單題核准後設定 gate）**：
  - 作者明確核准 S14 單題雲端 smoke，費用上限 US$0.045；此核准不包含固定 20 題批次。Context7 仍無 callable tool，依守則改查官方模型、function calling 與 pricing 文件。
  - 官方資料確認 `gemini-3.1-flash-lite` 為現行 stable model 且支援 function calling；標準文字單價仍為 input US$0.25／1M、output US$1.50／1M。估算腳本重跑 6 calls、72k input、18k output，總上限仍為 US$0.045。
  - API 前只做不揭露值的布林檢查，結果為 `GOOGLE_API_KEY_CONFIGURED=False`、`GEMINI_MODEL_VERIFIED=False`；因此在 provider 初始化前停止，沒有雲端請求、trace 或費用，也沒有修改 `.env`。
  - 待作者自行補好兩項設定後沿用本次單題核准重跑。Agent 未執行 Git；實際 API 成本維持 US$0，完整 20 題仍待另行核准。

- **2026-07-22（雲端 key 命名釐清）**：
  - 唯讀檢查已安裝 connector 的 `api_key` default factory，確認會依序接受 `GOOGLE_API_KEY` 或 `GEMINI_API_KEY`；前一筆 preflight 對 key 名稱的判斷過嚴，並非金鑰缺失。
  - 不揭露值的 `.env` 檢查結果：主要 `GEMINI_API_KEY` 已設定、三個 backup 名稱也都有值，但 `GEMINI_MODEL` 尚未等於核准與已查證的 `gemini-3.1-flash-lite`。backup 不會由 connector 自動輪替，本次也未授權額外失敗重試，因此不使用。
  - 目前只待作者設定模型字串；沒有發出 API 請求，實際成本仍為 US$0，既有單題 US$0.045 核准繼續有效。

- **2026-07-22（雲端 S14 單題 smoke）**：
  - 作者完成模型字串設定並說明三把 backup 僅供額度不足時替換。布林 gate 為主要 key、3 把 backup 與指定模型全部就緒；PLAN 新增 D19，限定只有 quota／rate-limit 才按 slot 切換，其他錯誤不得換 key，且總成本不得超過當次核准。本題主 key 成功，backup 全部未使用。
  - 依已核准的 6 calls、72k input、18k output 上限執行 S14，6.35 秒完成且無 runtime error。七項指標全數 1／1；工具序列為 `eligibility_check` → `copay_estimate` → `build_report_draft` → `publish_report`。
  - 金額 trace 與確定性工具完全一致：政府給付 10,080、額度內自付 1,920、超額 0、合計自付 1,920；PII 洩漏 0，HITL 已觸發，核准後內容與預覽逐字相同。ignored trace 為 `artifacts/eval/gemini-smoke-s14.json`。
  - `uv lock --check` 通過，Phase 2／evaluation 相關 pytest **20 passed in 0.58s**。evaluator 沒有回傳實際帳單值；依事前估算，本次不超過 US$0.045，不冒稱精確成本。
  - Phase 3 尚未完成：雲端固定 20 題需要作者另行核准 US$0.90 上限。Agent 未執行 Git；建議 commit `test(eval): 記錄雲端單題完整流程證據`，Phase 3 tag 暫不建立。

- **2026-07-22（更換 key 後再次驗證 S14）**：
  - 作者明確要求用新主要 key 再跑 S14，另行核准單題上限 US$0.045。為先驗證新 key，第一輪未自動切換；主要 slot 在零工具、零模型輸出時回 `429 RESOURCE_EXHAUSTED`，訊息明示 prepaid credits depleted。
  - 依 D19 quota-only 規則接續：backup slot 1 回相同 429；backup slot 2 在 6.41 秒完成端到端 1／1，backup slot 3 未使用。所有輸出只記 slot，不記 key 值；`.env` 未修改。
  - backup2 trace 的離線 evaluator 重算七項全通過、notes 空白；工具序列為資格 → 金額 → 建稿 → 發布，政府給付 10,080、額度內自付 1,920、超額 0、合計自付 1,920。HITL 為 true，預覽與最終報告 SHA-256 同為 `870f4dca7919968b4026a3d46211a2dfa2b1fed26635b5f62a8819e85ac0f54d`。
  - 新成功 trace 為 ignored `artifacts/eval/gemini-smoke-s14-backup2.json`；兩個 429 trace 亦分開保留。`uv lock --check` 通過，相關 pytest **20 passed in 0.60s**。
  - evaluator 不回傳帳單值；兩次成功 smoke 各自上限 US$0.045，因此截至目前累計保守上限 US$0.09。429 均未產生模型或工具結果，但不冒稱精確帳務。完整 20 題仍未授權，Agent 未執行 Git。

- **2026-07-22（雲端固定集 partial run 與限速）**：
  - 作者明確核准固定 20 題雲端診斷，最壞 120 calls、1.44M input、360k output、上限 US$0.90。主要與三個 backup slot 全數以 `SecretStr` 載入、雜湊去重，trace 只保留 slot 名稱；零進度 429 才允許切換，已有輸出或工具後禁止重跑。
  - 第一段 artifact `gemini-20-final.json` 請求 20 題、記錄 S01–S04；S01–S03 完成，S04 在已有工具進度後遇每分鐘 15 次限制，依規則以 `quota_after_progress` 中止。依 PLAN D21 加入整批共用 12 requests/minute 限速器與 `max_retries=0`。
  - 第二段 artifact `gemini-17-paced.json` 請求 S04–S20、記錄 S04–S08；S04–S07 無 runtime error，S08 的 `publish_report` 因模型竄改確定性草稿而被 registry 拒絕。這是應計入失敗的安全行為，但 runner 目前分類為 `cloud_runtime_error`，因此 S09–S20 尚未呼叫。
  - 兩份 ignored trace 均保留；後續不得重跑 S01–S08。實際帳單值無法由 evaluator取得，本批仍以已核准 US$0.90 為保守上限；發生 S08 後沒有再送付費請求。Agent 未執行 Git。

- **2026-07-22（Context7 恢復與 project skill）**：
  - 作者完成 Context7 遠端 MCP OAuth；端到端實跑 `resolve-library-id` 與三個 `query-docs`，選用 `/websites/langchain_oss`，來源涵蓋 LangChain 1.x built-in middleware、HITL／Command resume、PII detector 與 model initialization。
  - 對照鎖定 Agent framework 1.3.14：現有 `create_agent`＋checkpointer、同 thread `Command(resume=...)`、自訂 PII regex 及 `init_chat_model` kwargs 符合文件；Context7 只作開發查證，不加入 runtime。PLAN 新增 D20、D21。
  - 依 `skill-creator` 初始化 `.claude/skills/verify-external-api`，修正 Windows CP950 造成的 metadata 編碼後，以 UTF-8 產生；新 skill 與更新後的 `review-phase` 都由 `quick_validate.py` 驗證為 `Skill is valid!`。
  - 免費驗證：`uv lock --check`、compileall 成功，全套 pytest **473 passed in 7.95s**。本小步沒有模型 API 呼叫，新增成本 US$0；Agent 未執行 Git。建議 commit：`chore(skills): 加入外部 API 查證流程`。

- **2026-07-22（雲端 20 題完成與 Phase 3 review）**：
  - 新增 `ReportPublicationRejected` 專用安全例外；未知 `report_id` 或草稿遭竄改時記為 scenario failure 並繼續，其他未知 runtime error 與 quota-after-progress 仍立即中止。相關測試覆蓋安全拒絕、failover、共享 limiter 與 secret-free trace。
  - S09–S15 續跑後，S15 因未知 report ID 被 registry 擋下；保留該失敗、不重跑，再完成 S16–S20。新增確定性 merge 模組，以較晚 partial 覆蓋同題 rate-limit trace、驗證 provider／model／scenario 完整性並保留四段 source run 的中止原因。
  - `gemini-20-complete.json` 含固定 S01–S20 各一筆；從 raw trace 重新執行 evaluator，與 artifact metrics 完全一致：追問 10／20、工具選擇 12／20、參數 19／20、金額 19／20、PII 洩漏 0、HITL 10／20、端到端 7／20。通過題為 S12、S13、S14、S16、S17、S18、S19。
  - README 主表與八項 metrics 自動比對全數相同。最終 `uv lock --check`、`uv sync --locked --all-groups`、compileall 成功，pytest **476 passed in 2.91s**；六支 skills 驗證通過，公開 README 禁詞、私密路徑、疑似 token 與 50 MiB 大檔掃描均無命中。
  - 成本：兩次 smoke 保守上限合計 US$0.09；20 題批次實際帳單未知、未冒稱精確值，仍以事前核准 US$0.90 為上限，累計保守授權上限 US$0.99。S15 後只執行尚未跑過的 S16–S20，沒有為提高分數重跑失敗題。
  - Phase gate：Phase 3 工程 DoD 通過，待作者確認；規則人工校對仍有 5 個未勾項，阻擋整體公開 release。Agent 未執行 Git。建議 commits：`feat(eval): 加入雲端限速與安全失敗分類`、`test(eval): 完成固定二十題雲端診斷`、`docs: 更新三模式評估結果`；`phase-3` tag 僅在作者驗收後自行建立。

- **2026-07-22（評估表可讀性修正）**：
  - 依作者驗收回饋重寫 README 的 20 題診斷說明：新增逐關流程、七項指標白話定義、三模式解讀，以及「程式測試」與「模型工作流評估」的差異。
  - 對照 evaluator 定義確認 20 題中只有 13 題設定金額標準答案，另外 7 題本來就不得試算；公開文件新增真正金額題成績：雲端 12／13、F1 7／13、12B adapter 12／13，並保留原始 20 題口徑供稽核。
  - 實跑證據：`uv lock --check` 通過，全套 pytest **476 passed in 2.98s**；更新後 README 已逐段讀回核對。決策變更：無；只改善既有 Phase 3 證據的呈現，不改 evaluator、artifact、模型成績或 Phase DoD。
  - 成本與 Git：API 成本 US$0；Agent 未執行任何 Git 指令。建議 commit：`docs: 說明二十題診斷指標與金額口徑`。

### Phase 4 — UI、範例與 Space-ready 文件（工程完成）

- **2026-07-22（介面與測試）**：
  - 依 frontend-design skill 採「長照額度帳冊／人工校閱台」視覺：米紙、墨綠、朱印，將草稿、金額明細、法源與 approve／reject 分區；手機自適應。
  - 完成 session store、provider 切換隔離、舊制比較開關、PII 遮蔽回顯、來源／明細面板、Space 僅雲端模式、環境 port 與 occupied-port 拒絕。
  - UI pytest 5 passed；依 webapp-testing skill 用受控 helper 啟動 7860，桌機／手機瀏覽器 smoke `UI_SMOKE_OK`、console 0 error，helper 隨後只停止自己啟動的 server。
  - 三份完整對話截錄涵蓋 65 歲一般戶、55 歲原住民第二類、49 歲失智的舊現制差異與 unknown CMS；README 補齊 Mermaid、模型對照、成本、PII、資料授權與免責。
  - 全專案最終實跑：`uv lock --check`、`uv sync --locked --all-groups`、compileall 通過，pytest **462 passed in 2.56s**。
  - Git：Agent 未執行。建議 commit：`feat(ui): 加入聊天與報告校閱介面`、`docs: 完成模型評估與操作指南`；建議 tag `phase-4` 僅在作者驗收後自行建立。
  - 實際 API 成本：US$0。

- **2026-07-22（夜間 review-phase 收尾）**：
  - 最終重跑 `uv lock --check`、`uv sync --locked --all-groups`、compileall 與全套 pytest，結果 **462 passed in 2.52s**；UTF-8 CLI smoke 再次核對 CMS 4 的政府給付 10,080、自付 1,920。
  - 受控瀏覽器再次驗收桌機與 390 px 手機版，輸出 `UI_SMOKE_OK`、console 0 error；測試 helper 隨即停止自己啟動的 7860 server，沒有停止其他程序。
  - 四支 project skills 全部以 UTF-8 模式通過 `quick_validate.py`；Windows 預設 CP950 直接執行驗證器會解碼失敗，已保留為環境注意事項，skill 內容本身合法。
  - 公開 README 的特定供應商／產品名掃描通過；疑似 API key pattern 掃描無命中；repo 內（排除 `.venv` 與 ignored artifacts）沒有超過 50 MB 的檔案。
  - F1 check-only 再次確認 RTX 4090 24 GB、約 246.7 GiB 可用；gated dry-run 以預期的非零碼停止，沒有下載權重。20 題 artifact 重新讀回為 20 筆，指標與快速回憶區一致。
  - Git：Agent 全程未執行任何 Git 指令；API 成本仍為 US$0。

- **2026-07-22（review 後規範修正）**：
  - 公開設定稽核發現 Python 設定類別仍留有模型名稱 fallback；已移除所有模型字串的程式碼預設，只驗證當前 provider 所需的 `.env` 變數，託管雲端模式不必設定無用的地端模型。
  - 新增回歸測試確認模型名稱只存在 `.env.example`／部署模板，不存在設定模組；最終 compileall 通過、Phase 2 專屬 **11 passed**、全套 **463 passed in 2.39s**。

- **2026-07-22（GitHub 公開前檢查）**：
  - 作者在 `kuotunyu` 帳號建立空的 Public repo `ltc-benefit-agent`，沒有由遠端初始化 README、LICENSE 或 gitignore。本機 `.git` 不存在，因此沒有舊 commit 作者，也沒有把 `tun0000`、Claude 或其他帳號帶入 Contributors 的既有歷史。
  - 唯讀 release preflight（不讀 `.env`）：疑似 API token 0 檔、私密絕對路徑 0 檔、排除既定 ignored 目錄後超過 50 MB 大檔 0 個；README 公開禁詞掃描 0 命中。`.gitignore` 已排除 `.env`、`.venv`、`artifacts/`、`models/` 與權重格式。
  - Release gate：`docs/research/rules-audit.md` 五項作者人工簽核仍未完成，所以目前只允許初始化本機 Git 與準備 commits，不應將程式碼 Push 到 Public repo。
  - 成本與 Git：API 成本 US$0；Agent 未執行任何 Git 指令。下一步由作者將本 repo 的 local author／committer 設為 `kuotunyu` 帳號綁定的 noreply email。

- **2026-07-22（作者初始化本機 Git）**：
  - 作者提供實跑輸出：以空白歷史初始化本機 repository、主分支設為 `main`，local `user.name` 為 `kuotunyu`，local `user.email` 為該帳號的 GitHub noreply email。
  - `git check-ignore -v .env` 命中 `.gitignore:2:.env`，確認既有秘密檔不會被一般 `git add` 納入。因為初始化前沒有 `.git`，目前不存在 `tun0000`、Claude 或其他舊作者歷史。
  - Git 邊界：以上 Git 指令均由作者自行執行；Agent 未執行 Git。尚未 add／commit／Push，下一步先按功能群組建立小型 Conventional Commits。
