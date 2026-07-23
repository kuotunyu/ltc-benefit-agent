# PROGRESS — ltc-benefit-agent 進度日誌

## 🧭 快速回憶區（上次收工：2026-07-23）

- **現在做到哪**：Phase 0–4、規則人工校對 5／5、GitHub 公開倉庫與 Hugging Face Space 均完成；常駐多輪聊天、CMS 白話說明、unknown CMS 防誤判、已知 CMS 金額試算與 HITL 核准都已通過公開端到端驗收。
- **本次完成**：公開 Space 以 unknown CMS 情境複驗，畫面只顯示 CMS 2–8 額度參考表、1966 與申請流程，沒有猜個人 CMS、政府給付或合計自付；單次核准後顯示「已核准並發布」。
- **實跑總證據**：`uv lock --check`、`uv pip check`、完整 pytest **514 passed in 4.64s**、sdist／wheel build 與離線 CLI approve 均成功；功能驗收基準 `55e872f` 與最終文件同步 `85a9461` 的 GitHub Actions 均成功。
- **Context7**：以 `/websites/langchain_oss_python` 再確認 `AgentMiddleware.state_schema`、`ModelRequest.override` 與 `wrap_tool_call` 的現行介面後實作雙層 guard；既有 Gradio 查證仍見 Phase 日誌。
- **本機 20 題最終結果**：F1 與 12B adapter 的追問、選工具、參數、金額、HITL、端到端均 20／20，PII 洩漏均 0。
- **本機舊基線**：F1 端到端 0／20、12B adapter 3／20；README 保留初始表，不用最終結果覆蓋歷史證據。
- **雲端 20 題舊基線**：追問 10、選工具 12、參數 19、金額 19、PII 0、HITL 10、端到端 7；S08／S15 的不合法發布被 registry 擋下。
- **金額口徑**：20 題中 13 題應試算；最終 F1 與 12B adapter 均為 13／13。雲端 12／13 是舊 workflow 基線，尚未重跑。
- **下一步**：
  1. 可由作者自行建立 `phase-4` tag／Release，作為公開里程碑。
  2. 若要取得新版雲端固定 20 題成績，另行核准 US$1.776 上限；這是可選評估，不阻擋 Phase 4 完成。
- **成本**：作者手動 Space 對話已呼叫 Gemini，但目前沒有可取得的 usage metadata，實際成本以帳單為準；Agent 本輪沒有另發付費請求。既有 connector smoke 約 US$0.0001583；新版 20 題上限 US$1.776，尚未核准或執行。
- **待使用者人工處理**：Space 已保存 `GEMINI_MODEL`、`GEMINI_THINKING_LEVEL` 與遮蔽的 `GEMINI_API_KEY`；目前不要新增 backup key。任何後續雲端 20 題仍需另行核准成本。
- **待使用者 Git 操作**：只剩可選的 `phase-4` tag／Release；Agent 未執行任何 Git 指令。
- **⚠️ 已知坑**：CMS 範圍文字不能用單一等級 regex 截取；Space SSR 不宜用 `request.session_hash` 作跨事件唯一鍵；Gradio 6 對事件來源 Button 的 `visible=False` 不可靠；福利類別與版本比較仍須走確定性正規化；20／20 不代表統計泛化；`.env` 真值從未印出、覆寫或提交。

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
  - 作者在 `kuotunyu` 帳號建立空的 Public repo `ltc-benefit-agent`，沒有由遠端初始化 README、LICENSE 或 gitignore。本機 `.git` 不存在，因此沒有舊 commit 作者，也沒有把其他測試帳號或共同作者帶入 Contributors 的既有歷史。
  - 唯讀 release preflight（不讀 `.env`）：疑似 API token 0 檔、私密絕對路徑 0 檔、排除既定 ignored 目錄後超過 50 MB 大檔 0 個；README 公開禁詞掃描 0 命中。`.gitignore` 已排除 `.env`、`.venv`、`artifacts/`、`models/` 與權重格式。
  - Release gate：`docs/research/rules-audit.md` 五項作者人工簽核仍未完成，所以目前只允許初始化本機 Git 與準備 commits，不應將程式碼 Push 到 Public repo。
  - 成本與 Git：API 成本 US$0；Agent 未執行任何 Git 指令。下一步由作者將本 repo 的 local author／committer 設為 `kuotunyu` 帳號綁定的 noreply email。

- **2026-07-22（作者初始化本機 Git）**：
  - 作者提供實跑輸出：以空白歷史初始化本機 repository、主分支設為 `main`，local `user.name` 為 `kuotunyu`，local `user.email` 為該帳號的 GitHub noreply email。
  - `git check-ignore -v .env` 命中 `.gitignore:2:.env`，確認既有秘密檔不會被一般 `git add` 納入。因為初始化前沒有 `.git`，目前不存在其他舊作者歷史。
  - Git 邊界：以上 Git 指令均由作者自行執行；Agent 未執行 Git。尚未 add／commit／Push，下一步先按功能群組建立小型 Conventional Commits。

- **2026-07-22（作者建立第一筆 commit）**：
  - 作者提供實跑證據：root commit `31d00a2`，訊息 `chore: initialize project structure`，共 24 個專案骨架、規範與 project skill 檔案。
  - `git show` 證實 Author 與 Committer 都是 `kuotunyu`，並使用該帳號 GitHub noreply email；commit message 沒有共同作者 trailer。
  - Agent 未執行 Git；尚未 Push。下一筆預定為確定性資格／金額／FAQ 工具及其測試。

- **2026-07-22（作者建立工具層 commit）**：
  - 作者先實跑工具層 pytest，結果 **442 passed in 0.34s**；接著建立 commit `91fc3bd`，訊息 `feat(tools): 加入確定性資格、補助試算與 FAQ 檢索`，共 10 個規則、工具、校對表與測試檔案。
  - `git show` 證實 Author 與 Committer 都是 `kuotunyu` 的 GitHub noreply email，沒有共同作者 trailer；尚未 Push。
  - 作者新增慣例：後續 Conventional Commit 主旨與內文以正體中文（zh-TW）為主，Agent／PII／HITL／FAQ 等專有名詞保留原文；已同步至 `AGENTS.md`。
  - Agent 未執行 Git。下一筆預定為多輪 Agent、PII 遮蔽、HITL 與 CLI。

- **2026-07-22（作者建立 Agent commit）**：
  - 作者實跑 `tests/test_agent_phase2.py`，結果 **14 passed in 0.59s**；接著建立 commit `98260fd`，訊息 `feat(agent): 加入多輪 Agent、PII 遮蔽與 HITL`，共 10 個 Agent／CLI／安全與測試檔案。
  - `git show` 證實 Author 與 Committer 都是 `kuotunyu` 的 GitHub noreply email，沒有共同作者 trailer；尚未 Push。
  - Agent 未執行 Git。為維持小型 commit，後續將診斷 evaluator 與 F1／Ollama 準備工具拆成兩筆。

- **2026-07-22（作者建立診斷 evaluator commit）**：
  - 作者實跑 `tests/test_evaluation.py`，結果 **15 passed in 0.34s**；接著建立 commit `4edfb27`，訊息 `feat(eval): 加入 20 題確定性診斷與雲端執行保護`，共 11 個 evaluator、固定情境、成本／合併腳本與測試檔案。
  - `git show` 證實 Author 與 Committer 都是 `kuotunyu` 的 GitHub noreply email，沒有共同作者 trailer；尚未 Push。
  - Agent 未執行 Git。下一筆只納入 F1 轉檔工具、Ollama 模板及地端準備說明，不混入 UI。

- **2026-07-22（作者建立地端模型流程 commit）**：
  - 作者實跑 `py_compile` 與準備腳本 `--help`，兩者皆正常且沒有下載、轉檔或匯入模型；接著建立 commit `e922e4a`，訊息 `feat(local): 加入地端模型轉檔與服務匯入流程`，共 4 個轉檔腳本、服務模板與操作說明檔案。
  - `git show` 證實 Author 與 Committer 都是 `kuotunyu` 的 GitHub noreply email，沒有共同作者 trailer；尚未 Push。
  - Agent 未執行 Git。下一筆預定為聊天 UI、session 隔離、人工核准入口與託管說明。

- **2026-07-22（作者建立 UI commit）**：
  - 作者實跑 `tests/test_ui.py`，結果 **5 passed in 2.05s**；`app.py` 與 UI smoke 腳本 `py_compile` 通過且未啟動 server。接著建立 commit `6e21113`，訊息 `feat(ui): 加入聊天、試算明細與人工核准介面`，共 8 個 UI、託管、smoke 與測試檔案。
  - `git show` 證實 Author 與 Committer 都是 `kuotunyu` 的 GitHub noreply email，沒有共同作者 trailer；尚未 Push。
  - Agent 未執行 Git。下一筆預定為 README、三份完整對話範例、正體中文 commit 規範與累積進度證據；五項規則人工簽核仍保持未完成。

- **2026-07-22（公開文件 commit 前驗證）**：
  - staged 範圍為 README、三份完整對話範例、`AGENTS.md` 與 `PROGRESS.md`；未納入 `.env`、runtime artifacts、模型或權重。
  - 實跑 `uv lock --check` 通過，全套 pytest **476 passed in 2.69s**；疑似 token、私密絕對路徑、作者真實／noreply email、README 公開禁詞與未忽略 50 MB 大檔掃描全部為 0。
  - Agent 未執行 Git、沒有 API 成本、尚未 Push。文件 commit 完成後仍須由作者完成五項規則人工簽核，才可通過 Public release gate。

- **2026-07-22（作者建立公開文件 commit）**：
  - 作者建立 commit `ba01a46`，訊息 `docs: 補充評估解讀、對話範例與進度紀錄`，共 6 個 README、對話範例與專案紀錄檔案。
  - `git show` 證實 Author 與 Committer 都是 `kuotunyu` 的 GitHub noreply email，沒有共同作者 trailer；截至此筆共七個小型 Conventional Commits，仍未 Push。
  - Agent 未執行 Git。下一步由作者依 `docs/research/rules-audit.md` 完成五項人工簽核，之後建立最後的 audit commit，再進行 Public Push。

- **2026-07-22（人工規則校對第 1–3 項）**：
  - 作者親自開啟官方附表二，逐格確認 CMS 2–8 照顧及專業服務月額 10,020／15,460／18,580／24,100／28,070／32,090／36,180，並在校對表完成第 1 項簽核。
  - 作者親自開啟官方附表五，確認照顧及專業服務第一／第二／第三類部分負擔為 0%／5%／16%，且小數點後無條件捨去，並完成第 2 項簽核。
  - 第 3 項檢查發現 README 原文只寫 30% 額度，漏載第 10 條第二項「僅能用於附表四居家照顧服務以外之照顧組合」限制，因此未代勾、先阻擋 release。
  - 已補強 README、standalone FAQ、CMS 未知參考表與已知 CMS 最終報告；固定說明本工具不判定個別服務碼是否適用。新增兩項回歸測試，針對性 **35 passed in 0.81s**、`uv lock --check` 通過、全套 **478 passed in 3.13s**。
  - Agent 未執行 Git，API 成本 US$0；第 3 項仍待作者親自確認修正文案後勾選。

- **2026-07-22（人工規則校對第 4 項）**：
  - 作者提供官方現行辦法第 22 條畫面；原辦法自 2022-02-01 施行，2025-06-19 修正內容原則自 2025-09-01 施行，第二條指定資格、第 10 條第一項與指定服務碼自 2026-01-01 施行，最後一批附表自 2026-07-01 施行。
  - 稽核發現 README 雖寫「分階段生效」，仍可能讓讀者誤以為失智症年齡門檻與 PAC 都從 2026-07-01 才生效；已將 `CURRENT_2026_07` 明確改寫為「修正全部施行後的完整快照」，並列出三段施行日期及不支援過渡期日期查詢的邊界。
  - 確定性報告將「生效基準」改成「完整快照基準」，並直接輸出規則 metadata 的分階段施行說明；新增回歸測試固定三個日期與避免誤讀的文字。
  - 實跑證據：針對性 **24 passed in 0.64s**、`uv lock --check` 通過、全套 **479 passed in 2.75s**。資格與金額常數未變更，沒有 API 呼叫或成本。
  - Agent 未代勾校對表、未執行 Git；待作者親自確認新文案後完成第 4 項簽核。

- **2026-07-22（作者完成第 4 項簽核）**：
  - 作者確認 README 的完整快照標籤與三段施行日期說明，並親自在校對表將第 4 項標為完成；Agent 讀回檔案確認為 `[X]`。
  - 官方現行條文頁於同日再次查得最近修正日期仍為民國 114 年 6 月 19 日；人工校對剩最後一項「查證日後是否另有修正」。
  - Agent 未代勾第 5 項、未執行 Git；本次只有進度文件同步，沒有 API 模型呼叫或費用。

- **2026-07-22（五項簽核與最終 release review）**：
  - 作者重新整理官方現行條文頁，確認最近修正日期仍為民國 114 年 6 月 19 日，並親自完成第 5 項；Agent 讀回校對表確認 **5／5** 均為 `[X]`。
  - 新增 PLAN D22，明定 `CURRENT_2026_07` 是分階段修正全部施行後的完整快照；README 同步記錄已完成人工校對、法規修正後仍須重新查證。
  - 實跑 `uv lock --check`、`uv sync --locked --all-groups`、compileall 與完整 pytest，結果 **479 passed in 3.27s**；六支 project skills 均通過 validator。
  - 離線 CLI 實跑成功：完整快照基準 2026-07-01、CMS 4 第三類服務費 12,000 元，政府給付 10,080 元、自付 1,920 元，核准後報告與完整預覽一致。
  - 修正 PowerShell release scan 的 `$Matches` 覆寫與 CLI 編碼檢查後重新執行；最終結果為疑似秘密 0、私密絕對路徑 0、個人 email 0、公開禁詞 0、未忽略 50 MB 大檔 0，`.env` 排除規則 1，`.env.example` 非空秘密欄位 0。
  - README／PLAN／PROGRESS 同步完成後再次執行 lock check、compileall 與全套測試，最終 **479 passed in 3.12s**；快速回憶區 15 行，未超過 30 行限制。
  - 結論：release review 通過；API／模型成本 US$0。Agent 未執行 Git，待作者建立最後 audit commit 並自行 Push。

- **2026-07-22（GitHub 首次公開上線）**：
  - 作者建立 commit `0727695`，訊息 `fix(rules): 補充外籍看護限制與分階段施行說明`；Author 與 Committer 均為 `kuotunyu` 的 GitHub noreply email。
  - 作者設定 `origin` 為公開 repo，執行 `git push -u origin main` 成功；148 個 objects、267.26 KiB 完成上傳，`main` 已追蹤 `origin/main`。驗證由 Windows 已保存的 GitHub credential 自動完成，沒有要求重新輸入帳密。
  - 公開頁面實查可讀取 `main`、README、MIT License、完整檔案列表與 8 筆 commits；公開 commit 歷史 8／8 均顯示 `kuotunyu`，沒有其他共同作者。Contributors 區塊可能仍受 GitHub 快取延遲影響。
  - Agent 未執行 Git；本次只同步 PROGRESS，待作者自行建立文件 commit 並 Push。API／模型成本 US$0。

- **2026-07-22（產品工具介面重整，待作者視覺驗收）**：
  - 依作者指定的 `impeccable` skill 完成產品訪談並建立 `PRODUCT.md`：介面定位為產品工具，品牌感受為清楚、可信、平靜，正文約 18 px，無障礙以 WCAG AA 為方向；PLAN 新增 D23。
  - Gradio 移除帳冊紙張、印章、點陣背景與裝飾性字體，改用單一白色工作面、深綠重點色與明確資訊層級；控制列改為水平配置，對話輸入與送出按鈕併排，對話高度由大面積空白縮至桌機 300 px／手機 250 px，報告校閱提前出現在首屏後段。
  - 全域正文、表單、按鈕與報告內容放大至約 17–18 px；加入可見鍵盤焦點、較高對比、最小控制高度、手機無水平溢出與 reduced-motion 規則。功能、PII、HITL 與 session 行為均未移除。
  - 外部 API 查證：Context7 `/websites/gradio_app` 確認 Row／Button `scale`、Column `min_width` 與 CSS 用法；另對照鎖定的 Gradio 6.20.0，確認 Textbox、Button、Chatbot 使用的參數簽章。
  - 實跑證據：UI 專屬 pytest **5 passed**；受控動態連接埠的桌機與 390 px 手機瀏覽器 smoke 均輸出 `UI_SMOKE_OK`、console 0 error，helper 只停止自己啟動的 server；本次最終 `uv lock --check`、compileall 通過，完整 pytest **479 passed in 2.66s**。
  - 成本與 Git：沒有模型或付費 API 呼叫，新增成本 US$0；Agent 未讀取 `.env`、未停止既有程序、未執行任何 Git 指令。建議 commit：`feat(ui): 簡化試算介面並提升可讀性`。

- **2026-07-22（產品工具介面第二輪 distill，待作者視覺驗收）**：
  - 依作者回饋與 `impeccable distill` 移除主內容／報告區外層卡片、控制列分隔線、提醒框、狀態底色及模型／舊制控制的元件外殼；保留設定、對話、報告三個有意義層級，既有功能未刪除。
  - 空白對話改為 150 px；開始出現訊息後恢復桌機 230 px／手機 210 px 並可捲動。空報告最小高度由 140 降至 90 px，輸入框改單行並縮短手機 placeholder，減少首次載入的無效空白。
  - 下拉選單輸入與三個展開選項均由瀏覽器量測確認至少 18 px；修正全域 input 高度誤套 checkbox 的根因，舊制控制改為「同時顯示 2022 舊制」，checkbox 實測 22×22 px、標籤至少 18 px。
  - 瀏覽器驗收加入頁首間距、空對話高度、下拉選項字級、checkbox 尺寸與手機無水平溢出斷言。受控 helper 以動態未占用連接埠完成桌機／390 px 手機 `UI_SMOKE_OK`、console 0 error，且只停止自己啟動的 server。
  - 最終證據：`uv lock --check`、compileall 通過，完整 pytest **479 passed in 2.61s**。沒有模型或付費 API 呼叫，新增成本 US$0；PLAN 決策仍沿用 D23，無新架構或驗收標準變更。
  - Git：Agent 未讀取 Git 狀態、未執行任何 Git 指令；待作者驗收後自行 commit／Push。建議 commit：`feat(ui): 扁平化試算流程並改善空間使用`。

- **2026-07-22（輸入辨識與 progressive disclosure，待作者視覺驗收）**：
  - 依作者回饋與 `impeccable clarify` 修正首次使用心智模型：將輸入框移到對話紀錄之前，固定標籤改成「請在這裡輸入家庭情況」，placeholder 提供年齡、協助項目與持續時間的具體範例；狀態文字直接指示在上方輸入後送出。
  - 空的對話紀錄不再渲染成疑似輸入區；`conversation-section` 初始隱藏，第一次送出後才顯示。`report-section` 也改為有草稿／明細／來源後才顯示，首次載入不再保留兩塊無效空白。
  - 全域正文、表單、按鈕、下拉本體與選項、舊制標籤、狀態、報告內容提升至 19 px；真正的輸入標籤為 20 px 粗體。Context7 `/websites/gradio_app` 確認 Gradio 6 的 Row／Column 可作 event output 並動態更新 `visible`。
  - 新增確定性 UI 回歸測試，分別驗證無內容、已有對話、已有報告三種顯示狀態；UI 專屬 **6 passed**。瀏覽器 smoke 驗證桌機／390 px 手機首次載入只顯示明確輸入流程、隱藏空對話與空報告、19 px 字級、無水平溢出，結果 `UI_SMOKE_OK`、console 0 error。
  - 最終證據：`uv lock --check`、compileall 通過，完整 pytest **480 passed in 2.86s**。沒有模型或付費 API 呼叫，新增成本 US$0；PLAN 沿用 D23，沒有規則或架構決策變更。
  - Git：Agent 未讀取 Git 狀態、未執行任何 Git 指令；待作者驗收後自行 commit／Push。建議 commit：`feat(ui): 明確區分輸入區並按需顯示結果`。

- **2026-07-22（直覺式單人評估流程與空回覆保護，待作者視覺驗收）**：
  - 依作者回饋與 `impeccable onboard` 將首次操作改成四個明確動作：一次選一位家人、在指定欄位打字、按「開始資格初篩」、依序回答並校閱報告；輸入範例直接列出年齡、生活協助與持續時間。
  - 模型模式與 2022 舊制比較移到輸入區下方的「其他選項（一般情況不用設定）」收合區；主要輸入與綠色開始按鈕優先出現。標題、使用方式與輸入區之間的 Gradio 預設無效間距由瀏覽器實測 38 px 收至 20 px 門檻內。
  - 修正空模型回覆造成空白助理訊息的問題：controller 現在以不涉及資格或金額計算的確定性引導文字，要求一次選一人並補充年齡、洗澡、穿衣、吃飯、行走或如廁需求；後續狀態明確指出回到同一輸入欄並按「送出補充資料」。
  - HITL 草稿提示移除「右側」等版面相依說法，改成檢查下方內容並選擇核准或退回修正；清除動作改為「改評估另一位家人」，避免把 session 技術詞暴露給一般使用者。
  - 實跑證據：UI 專屬 **7 passed**；受控動態連接埠完成桌機／390 px 手機 smoke，均為 `UI_SMOKE_OK`、console 0 error，測試 helper 只停止自己啟動的 server。最終 `uv lock --check`、compileall 通過，完整 pytest **481 passed in 2.67s**。
  - 成本與決策：沒有模型或付費 API 呼叫，新增成本 US$0；沿用 PLAN D23，未改規則、Agent 架構或驗收標準。
  - Git：Agent 未讀取 Git 狀態、未執行任何 Git 指令；待作者視覺驗收後自行 commit／Push。建議 commit：`feat(ui): 加入直覺式單人評估引導與空回覆保護`。

- **2026-07-22（content blocks 與情境承接修正，待作者視覺驗收）**：
  - 作者實測發現單一 84 歲家人情境已清楚提供年齡與健康描述，空回覆保護卻錯誤要求「先選其中一位」；確認根因是上一輪 fallback 只要遇到空文字就固定重播多人提示，屬系統答非所問，不是使用者輸入錯誤。
  - Context7 `/websites/langchain_oss_python` 查證 LangChain 1.x 應由 `BaseMessage.content_blocks` 讀取標準文字區塊；服務層原本只接受字串，可能把有效的 provider content blocks 誤判為空白。現已同時支援字串與標準 text blocks，忽略 reasoning block，且保留原始字元與換行，維持 HITL 預覽／發布逐字一致。
  - 空回覆 fallback 改為依已知 user turns 保守找缺漏：已提供年齡就先承接，不重問年齡；只有當前輸入明確提到多人時才要求分開評估。年齡或疾病描述不直接當成失能，下一問改為洗澡、穿衣、吃飯、起身走動、如廁的協助需求與持續時間，不做資格或金額計算。
  - 一般追問不再顯示重複的狀態列，只保留對話中的實際問題；對話區在有內容後增至桌機 320 px／手機 300 px，避免較長追問把上一則使用者訊息捲出可視區而看似空白。
  - 新增零模型 `ui_fixture_app.py`，以匿名化的單人年齡／疾病／交通描述情境實際點擊 Gradio；瀏覽器確認回答保留 84 歲、改問日常生活功能、不出現「先選其中一位」、不顯示重複狀態，並輸出一問一答 screenshot。測試 helper 只停止自己啟動的動態連接埠 server。
  - 實跑證據：Agent／UI 針對性 **24 passed**；受控瀏覽器 `UI_SMOKE_OK`、console 0 error；最終 `uv lock --check`、compileall 通過，完整 pytest **483 passed in 2.62s**。沒有模型或付費 API 呼叫，新增成本 US$0。
  - 決策與 Git：沿用 PLAN D23，沒有規則、金額工具或 HITL 邊界變更；Agent 未讀取 Git 狀態、未執行任何 Git 指令。待作者驗收後建議 commit：`fix(ui): 正確承接已知情境並支援 content blocks`。

- **2026-07-22（目前問題與完整歷史分層，待作者視覺驗收）**：
  - 依作者回饋與 `impeccable layout` 重新定義結果區：固定高度 Chatbot 不再承擔主要問題；最新系統追問改由自動增高的 Markdown 區完整呈現，正文 20 px、1.75 行高、75ch 行長上限與高對比深色，主要閱讀不產生框內垂直滑桿。
  - 完整 Chatbot 移入預設收合的「查看完整對話紀錄」，僅在需要稽核過去輪次時打開；報告產生後隱藏目前問題區，避免與 HITL 待核准狀態重複。輸入欄、送出按鈕、最新問題與歷史紀錄形成明確主次層級。
  - 修正「其他選項」容器的水平捲動：控制列允許 responsive wrap，容器不再顯示水平滑桿；瀏覽器同時驗證下拉選項仍可正常展開，沒有以裁切換取表面整齊。
  - Context7 `/websites/gradio_app` 確認 Gradio 6 可用 Column 作 event output 動態切換整組元件，Markdown 適合直接呈現自動高度文字；沿用既有 Blocks 與 progressive disclosure，沒有新增前端框架。
  - 自動驗收新增：目前問題 `overflow-y` 不得為 auto／scroll、scroll height 不得超過 client height、正文 computed color 必須為 `rgb(23, 33, 29)`、完整歷史預設不可見、其他選項不可有水平捲動、390 px 手機不可水平溢出。桌機與手機一問一答 screenshots 均實際讀回。
  - 實跑證據：UI 專屬 **8 passed**；受控動態連接埠瀏覽器 `UI_SMOKE_OK`、console 0 error；最終 `uv lock --check`、compileall 通過，完整 pytest **483 passed in 2.63s**。沒有模型或付費 API 呼叫，新增成本 US$0。
  - 決策與 Git：沿用 PLAN D23，未改規則、Agent、PII 或 HITL 邊界；Agent 未讀取 Git 狀態、未執行任何 Git 指令。待作者驗收後建議 commit：`feat(ui): 分離目前問題與完整對話紀錄`。

- **2026-07-22（原地多輪回答流程與 Gradio 6 歷史相容，待作者視覺驗收）**：
  - 依作者回饋與 `impeccable onboard` 將介面拆成兩個明確階段：首次只顯示四步教學、起始描述欄與進階設定；第一次送出後整組自動隱藏，改為「系統現在想問你 → 直接回答上面的問題 → 送出回答」，每一輪都在同一位置更新，不必回頁首找輸入框。
  - 追問區加入持續多輪的明示說明；目前問題、回答欄與按鈕保持相鄰，完整歷史維持預設收合，模型模式與舊制選項只在開始前設定。桌機與 390 px 手機 screenshots 已讀回，主要操作路徑沒有內部滑桿或水平溢出。
  - 兩輪瀏覽器 smoke 首次揭露真實相容性錯誤：Gradio 6 將 Chatbot 文字送回為 `[{"type": "text", "text": ...}]` content blocks，舊 controller 以純字串 join 而在第二輪拋出 `TypeError`。依 Context7 `/websites/gradio_app` 的 ChatMessage 契約新增文字 block 正規化，非文字 block 不帶入資格初篩脈絡。
  - 新增回歸測試直接用 Gradio content blocks 重播第二輪；瀏覽器實際輸入年齡／健康描述，再補充生活協助與 8 個月持續時間，確認下一題原地更新為原住民、身障、失智、PAC 與住宿狀態，回答欄清空後仍可繼續使用，完整歷史保持收合。
  - 實跑證據：UI 專屬 **10 passed**；受控動態連接埠的桌機／手機初始與連續兩輪 smoke 為 `UI_SMOKE_OK`、console 0 error，helper 只停止自己啟動的 server；最終 `uv lock --check`、compileall 通過，完整 pytest **485 passed in 2.76s**。
  - 成本與決策：零模型 fixture，沒有 Gemini／Ollama 或付費 API 呼叫，新增成本 US$0；沿用 PLAN D23，未改規則、金額、PII 或 HITL 邊界。
  - Git：Agent 未讀取 Git 狀態、未執行任何 Git 指令；待作者視覺驗收後建議 commit：`fix(ui): 改善原地多輪回答並相容 Gradio content blocks`。

- **2026-07-22（視覺系統與歷史工具列 polish，待作者視覺驗收）**：
  - 依作者四項回饋與 `impeccable polish／colorize` 採 restrained 產品配色：工作寬度收至 1180 px，以綠灰頁底、白色操作面、淡綠目前問題區、深綠主要動作及一致的 10／12 px 圓角建立清楚、可信、平靜的層級；沒有漸層、插畫、玻璃效果或裝飾動畫。
  - 「查看完整對話紀錄」改為 20 px 粗體且具 hover 底色；其他 Accordion 標題統一為 19 px，進階設定文案縮短為「進階設定（一般不用調整）」，避免手機不自然斷行。瀏覽器 computed style 實測歷史標題至少 20 px、進階設定至少 19 px。
  - Chatbot 由每則訊息 `copy` 改成單一 `copy_all`，展開歷史實測訊息內按鈕數為 0、整體工具按鈕不超過 2 個；逐則複製不再占用訊息底部空白列，另輸出 `gradio-history-expanded.png` 人工讀回。
  - 「重新評估另一位家人」改為 2 px 深綠外框、48 px 高與清楚 hover／active 狀態；桌機保持右側緊湊次要動作，手機獨立整行，不再擠壓「系統現在想問你」。回答 composer 移除外層巢狀卡片，只保留實際輸入面與主要送出按鈕。
  - 實跑證據：UI 專屬 **10 passed**；受控動態連接埠的桌機／390 px 手機初始、連續兩輪與展開歷史 smoke 為 `UI_SMOKE_OK`、console 0 error；最終 `uv lock --check`、compileall 通過，完整 pytest **485 passed in 3.10s**。
  - 成本與決策：Context7 查證 Chatbot `buttons` API；零模型 fixture，沒有 Gemini／Ollama 或付費 API 呼叫，新增成本 US$0。沿用 PLAN D23，未改規則、金額、PII 或 HITL 邊界。
  - Git：Agent 未讀取 Git 狀態、未執行任何 Git 指令；待作者視覺驗收後建議 commit：`feat(ui): 統一視覺層級並精簡對話工具列`。

- **2026-07-22（公開展示版介面與 README 首屏，待作者視覺驗收）**：
  - 依作者指定的 `frontend-design` skill 將方向收斂為 refined civic tool：保留清楚、可信、平靜的產品工具感，不做政府表單仿製，也不加入漸層、玻璃、插畫或裝飾動畫。
  - Gradio 頁首新增三項可驗證承諾：「CMS 未知不猜級」、「金額由 Python 計算」、「報告發布前先確認」；目前問題、回答 composer、完整歷史與狀態統一使用 920 px 閱讀欄，問題正文不再受 75ch 限制而在卡片右側留下無效空白，手機版則維持滿寬堆疊。
  - README 首屏新增產品定位、Python／測試／授權／UI badges、三欄專案亮點與真實 Gradio 預覽；`docs/assets/gradio-showcase.png` 以虛構情境和零模型 fixture 產生，尺寸 1440×760、約 113 KiB，不含個資或模型輸出，可由 GitHub 與 Hugging Face 的相對路徑共同呈現。
  - 外部 API 查證：Context7 `/websites/gradio_app` 確認 Gradio 6 的 Blocks、HTML／Markdown 與 responsive Row／Column 用法；沒有改用外部前端框架。PLAN 沿用 D23，未改規則、金額、PII、Agent 或 HITL 邊界。
  - 實跑證據：UI 專屬 **10 passed in 2.03s**；桌機／390 px 手機、連續兩輪與展開歷史的受控瀏覽器 smoke 為 `UI_SMOKE_OK`、console 0 error；`uv lock --check`、compileall 通過，完整 pytest **485 passed in 2.67s**。Windows helper 留下的 fixture listener 經 PID、父程序與命令列核對後只停止該測試程序，17860 已釋放。
  - 成本與 Git：零模型 fixture，沒有 Gemini／Ollama 或付費 API 呼叫，新增成本 US$0；Agent 未讀取 Git 狀態、未執行任何 Git 指令。待作者視覺驗收後建議 commit：`feat(showcase): 強化公開介面與 README 展示`。

- **2026-07-22（首屏減法與舊制選項字級，待作者視覺驗收）**：
  - 依作者截圖與 `impeccable distill／typeset` 移除 Gradio 頁首的說明句及三個信任標籤，只保留「長照 2.0 資格與補助初步試算」；README 仍保留完整設計哲學與亮點，產品操作介面不再重複宣告。
  - 「同時顯示 2022 舊制」改為直接指定 Gradio checkbox 的 label、可見 span 與 block-info 節點，字級固定 **1.25rem（20 px）**、700 粗體、1.4 行高；勾選框維持 22×22 px，不改功能、預設值或 event binding。
  - Context7 `/websites/gradio_app` 查證 Gradio 6 Checkbox 支援 `elem_id`／`elem_classes`，官方建議以自訂 ID 搭配必要的 `!important` 覆寫；沿用既有 `legacy-toggle`，避免依賴易變的內建 class。
  - 瀏覽器驗收新增可見文字節點的 computed font-size／font-weight 斷言與 `gradio-settings.png`；人工讀回確認首屏只剩標題、舊制選項與模型下拉為同一閱讀層級。桌機／390 px 手機、進階設定、連續兩輪與歷史均為 `UI_SMOKE_OK`、console 0 error，測試連接埠皆已釋放。
  - 最終證據：UI 專屬 **10 passed in 2.15s**；`uv lock --check`、compileall 通過，完整 pytest **485 passed in 2.62s**。零模型 fixture，新增成本 US$0；沿用 PLAN D23，未改規則、金額、PII、Agent 或 HITL 邊界。
  - Git：Agent 未讀取 Git 狀態、未執行任何 Git 指令；待作者驗收後建議 commit：`feat(ui): 精簡首屏並放大舊制比較選項`。

### Post-Phase — Agent 可靠性強化

- **2026-07-22（有限次工具流程續跑保護）**：
  - 作者表示 UI／UX 暫時 OK，介面視為現階段已接受；開發主線改為改善既有 20 題揭露的 tool selection／HITL 可靠性，不調整已通過人工校對的確定性資格與金額公式。
  - 唯讀重查三模式既有 trace：共同失敗點是模型成功呼叫 `eligibility_check`／`copay_estimate`／`build_report_draft` 後提早輸出文字，未繼續建稿或呼叫受 HITL 攔截的 `publish_report`；金額工具不是本次根因。
  - Context7 `/websites/langchain_oss` 查證 LangChain 1.x class-based `AgentMiddleware`、custom state、`after_model` 與 jump hook；再以鎖定的 LangChain 1.3.14 signature 確認 `hook_config(can_jump_to=["model"])`、`ModelRequest.override` 與 `AgentState` 欄位。
  - 新增 `WorkflowContinuationMiddleware`：只讀同一使用者輪次中的成功工具證據；資格缺漏時不介入，未知 CMS 明確要求建參考報告，金額完成後要求建稿，建稿後要求逐字發布。每階段最多提醒一次、每輪最多三次；不解析使用者敘述、不補 tool args、不計算資格或金額。PLAN 新增 D24。
  - HITL approve／reject 回歸曾揭露續跑層會把已發布或已拒絕狀態誤認為草稿停住；已加入 `publish_report` 成功與 rejection 訊息終止條件，兩種既有流程均恢復通過。
  - 實跑證據：Agent 專屬 **18 passed in 0.71s**；刻意在資格、金額、建稿後各停一次的 scripted model 最終進入 HITL，資格工具回傳 `INSUFFICIENT_INFORMATION` 的案例只追問缺漏且模型呼叫數維持 2。`uv lock --check` 通過，完整 pytest **487 passed in 2.73s**。
  - 驗證邊界：尚未以真實 Gemini／Ollama 重跑診斷，因此本次只證明 graph 控制與安全邊界，不宣稱 20 題指標已提升。下一步先做單題地端 smoke；雲端批次仍須先列成本上限並取得作者確認。
  - 成本與 Git：沒有 Gemini／Ollama 或付費 API 呼叫，新增成本 US$0；Agent 未讀取 Git 狀態、未執行任何 Git 指令。建議 commit：`fix(agent): 加入有限次工具流程續跑保護`。

- **2026-07-22（確定性建稿接續、F1 template 修正與地端 20 題重測）**：
  - 真實 F1 S14 首次重測揭露 `eligibility_check` 的 Optional 型別在 tool schema 仍被列為 required；改為真正的 `None`／`UNKNOWN` 預設後，缺值會進入確定性 `INSUFFICIENT_INFORMATION`，不再於 Pydantic 驗證階段中止。既有 CMS 4 情境的省略欄位回歸測試證實仍回 `CMS_PROVIDED_FOR_ESTIMATE`。
  - 續跑提示雖有觸發，F1 仍在 ToolMessage 後回空白。比對原模型官方 tokenizer chat template 與 Ollama API 後，確認舊 Modelfile 的 `<tool_response>` 漏了工具名；模板補為同時輸出 `.ToolName` 與 `.Content`。測試 alias 共用既有 Q4_K_M blob，沒有重新下載、量化或複製 2.2 GB 權重。
  - 修正 template 後，F1 能由資格繼續呼叫金額工具，但仍不願主動呼叫 14 欄位的建稿工具。依 PLAN D25，middleware 改為只從已成功 tool calls 複製驗證過的欄位建立草稿，再從 registry 回傳複製 `report_id`／Markdown 原文送入既有 HITL；unknown CMS 則直接建只有 2–8 級參考表的草稿，不推測等級或個人金額。
  - middleware 合成的 `publish_report` 一度因明示 jump 直接進 tools 而繞過 framework 的 after-model HITL hook；移除該 jump、沿正常 routing 後，離線 approve／reject 與完整預覽重新通過。這個中間版本未進入公開 artifact，也未放寬發布規則。
  - F1 測試 alias S14 為端到端 1／1 後，已複製回 `.env` 使用的 `ltc-f1:q4_k_m` 標籤；正式標籤 S14 與 S11 分別再次端到端 1／1。舊 manifest 可由 template 與既有 GGUF 重建；沒有修改 `.env`。
  - F1 固定 20 題新結果：追問 16、工具選擇 12、參數 16、金額 19、PII 0、HITL 12、端到端 10；相較初始端到端 0、HITL 0 明顯改善，但追問 18→16。需試算 13 題中金額一致 12／13，失敗為 S08 PAC。
  - 12B adapter 固定 20 題新結果：追問 17、工具選擇 17、參數 16、金額 18、PII 0、HITL 17、端到端 12；相較初始端到端 3、HITL 4 改善，但參數 17→16、金額 19→18。S06 的不一致報告仍被 registry 拒絕。
  - 驗證證據：Agent＋evaluator **34 passed in 0.79s**；完整 pytest **488 passed in 3.25s**。README 已保留初始基線並新增「強化後地端重測」表，雲端舊數字明確標成尚未同版重跑。
  - 資源與成本：執行前 RTX 4090 約 928 MiB／5%，`ollama ps` 無載入模型；查詢時 Ollama 服務由程式自行啟動，未停止任何程序。地端重測 API 成本 US$0；雲端沒有呼叫。`OLLAMA_BASELINE_MODEL` 未設時第一次 12B 命令在模型載入前安全停止，正式重測只在子程序暫設 `ltc-gemma3-tools:12b`。
  - 清理：驗證後刪除本輪建立的 `ltc-f1-template-test:q4_k_m` 測試 alias 與 ignored 臨時 Modelfile；正式 `ltc-f1:q4_k_m`、共用 Q4_K_M 權重與版本控制內模板均保留，測試 alias 可重建。
  - 最終收尾：`uv lock --check`、三個本輪修改模組的 `py_compile` 與完整 pytest 再次通過；最新完整結果為 **488 passed in 3.24s**。快速回憶區維持 21 行，README 的初始歷史基準與強化後地端重測仍分表呈現。
  - 決策與 Git：新增 PLAN D25／D26；Agent 未讀取 Git 狀態、未執行任何 Git 指令。建議 commit：`fix(agent): 以確定性流程接續建稿與 HITL`。

- **2026-07-22（Gemini 3.5 Flash-Lite 零成本遷移準備）**：
  - Context7 `/websites/ai_google_dev_gemini-api` 與官方模型頁確認 `gemini-3.5-flash-lite` 為 2026-07-21 更新的 stable GA model，支援 function calling；官方遷移文件要求移除 `temperature`／`top_p`／`top_k`，並建議多步工具任務使用 medium 或 high thinking。
  - 鎖定套件為 LangChain 1.3.14、`langchain-google-genai` 4.3.0、`google-genai` 2.13.0；Context7 與本機 signature 均確認 `thinking_level` 可用。雲端 connector 不再傳 sampling 參數，新增 `GEMINI_THINKING_LEVEL`，預設 medium；Ollama 仍維持 `temperature=0`。
  - `.env.example`、AGENTS／CLAUDE 模型政策與 PLAN 官方來源更新為新 stable model；真正 `.env` 未讀取、未修改。新增 PLAN D27。
  - 實跑證據：`uv lock --check`、兩個遷移模組 `py_compile` 通過；Agent 專屬 **21 passed in 0.76s**，完整 pytest **490 passed in 2.86s**。沒有 Gemini 呼叫，新增 API 成本 US$0。
  - 依官方標準價 input US$0.30／1M、output（含 thinking）US$2.50／1M，單次 smoke 以 2,000 input、512 output 上限估得 **US$0.00188**；尚待作者更換 `.env` model ID 並明確核准，未執行。
  - Git：Agent 未讀取 Git 狀態、未執行任何 Git 指令。建議 commit：`feat(cloud): 遷移至 Gemini 3.5 Flash-Lite`。

- **2026-07-22（Gemini 3.5 Flash-Lite 真實連線與 tool-calling smoke）**：
  - 作者完成 `.env` 後，不揭露真值的布林檢查確認 `gemini-3.5-flash-lite`、medium thinking、主要 API key、F1 與 12B model tag 均已設定；Agent 未列印任何秘密。
  - 作者明確核准單次 smoke 最高 US$0.00188。首次命令因 per-invocation `max_tokens` 被新版 SDK 視為非法欄位，在建立 HTTP request 前由 Pydantic 本機驗證停止，沒有模型回應或 token usage；依本機 connector 實作改用 SDK request 欄位 `max_output_tokens` 後，只重試一次可計費請求。
  - 真實結果：model ID 相符、primary key slot 連線成功；模型回傳且只回傳 1 個 `connection_probe` function call，工具名稱與 `{"value": "ok"}` 參數皆完全一致。未執行外部副作用工具。
  - usage metadata：61 input、56 output、117 total tokens，其中 reasoning 40；依官方標準價 input US$0.30／1M、output US$2.50／1M 推算約 **US$0.0001583**，實際帳單仍以方案與免費額度為準，遠低於核准上限。
  - 範圍限制：這只證明新模型可透過目前 LangChain connector 連線並產生合法 tool call；不是 S14 完整資格／試算／HITL，也不是新版 20 題成績。後兩者若要執行，必須另行估價與核准。
  - Git：Agent 未讀取 Git 狀態、未執行任何 Git 指令；沿用建議 commit：`feat(cloud): 遷移至 Gemini 3.5 Flash-Lite`。

- **2026-07-22（本機分組提交，尚未 Push）**：
  - 作者自行建立 `bea9238 feat(ui): 改善多輪互動與公開展示介面`；7 個檔案，UI 測試 **10 passed**、相關模組 `py_compile` 通過，Author／Committer 均為 `kuotunyu` 的 GitHub noreply email。
  - 作者自行建立 `e2c01ea fix(agent): 強化確定性工具流程與模型相容性`；11 個檔案，Agent／架構測試 **30 passed**、相關模組 `py_compile` 通過，Author／Committer 同樣正確。
  - 兩筆 commit 目前只存在本機；尚未執行 `git push`，因此 GitHub 頁面仍顯示遠端舊 commit `eeeae13`，重新整理不會出現本機修改。最後文件 commit 完成後由作者一次 Push。
  - Agent 未執行任何 Git 指令；所有 Git 證據均來自作者貼回的 PowerShell 輸出。

- **2026-07-22（跨輪必要欄位保留與地端最終 20 題）**：
  - 逐題檢查前一版 F1／12B raw trace，確認主要殘餘問題不是金額公式，而是小模型跨輪遺忘 CMS、把未回答欄位補成 `false`／`COMMUNITY`、跳過資格前置，或 approve 後把 adapter 回帶的舊 interrupt 當成新狀態。
  - 依 Context7 `/websites/langchain_oss_python` 與鎖定的 LangChain 1.3.14 API，新增 `CaseIntakeMiddleware`：PII 遮蔽後只保存使用者明確說出的必要欄位；`before_model` 更新 thread state，`wrap_model_call` 以明確資料修正工具參數／補資格重檢，`wrap_tool_call` 再守工具順序。未提及值保持未知，不在 middleware 判資格或算金額。
  - service 每輪先把明確欄位累積進 graph state；已建草稿但尚未 publish 時只顯示固定狀態，不採用模型自行生成的金額；approve 後最終輸出固定等於完整 preview，並忽略 12B adapter 回帶的已處理 interrupt metadata。新增 PLAN D28／D29。
  - 最終 F1 artifact `artifacts/eval/f1-20-intake-final-v2.json`：追問／工具選擇／工具參數／金額／HITL／端到端均 **20／20**，PII 0；需試算 13 題金額 **13／13**。
  - 最終 12B artifact `artifacts/eval/gemma3-20-intake-final-v2.json`：追問 20、工具選擇 18、參數 18、金額 19、PII 0、HITL 18、端到端 **18／20**；需試算 13 題金額 **12／13**。S01／S20 因模型未發出第一個資格工具呼叫而保守停止，沒有由 middleware 冒充模型補做。
  - 最終工程驗證：`uv lock --check` 成功；`intake.py`、`service.py`、`factory.py`、`workflow.py` 的 `py_compile` 通過；完整 pytest **491 passed in 2.86s**。
  - 評估邊界：20 題是小型固定診斷集，不宣稱統計泛化；雲端新版沒有在本輪呼叫或重跑，既有 7／20 仍只列歷史基線。地端 API 成本 US$0，沒有停止任何既有程序，也沒有修改 `.env`。
  - Git：Agent 未執行任何 Git 指令。本輪建議 commit：`fix(agent): 強化跨輪資料保留與工具前置條件`；文件可另以 `docs: 同步地端最終診斷結果` 提交。

- **2026-07-22（有限首次工具重試、Space-ready 與 Phase review）**：
  - 逐題稽核前一版 12B S01／S20，確認失敗點都是模型以散文停住、未選第一個 `eligibility_check`。依 Context7 現行 LangChain 1.x 文件與鎖定版本，`wrap_model_call` 在至少兩個明確資格欄位時最多重試一次；重試改用隔離訊息、只暴露資格工具，不把原始對話或提示注入再次送入模型。
  - 12B 相容 adapter 只把模型完整 fenced JSON、合法工具名與物件型參數正規化成 tool call；沒有散文意圖推測或 middleware 代填。發布階段另把 adapter 回傳值鎖回 registry 的確定性 `report_id`／Markdown 原文，approve 後輸出仍與預覽逐字一致。新增 PLAN D30。
  - 更新正式 `ltc-gemma3-tools:12b` 的單工具重試模板並沿用既有模型 layers；測試 alias 完成後已移除，正式 12B 與 `ltc-f1:q4_k_m` 均保留，沒有下載或重轉權重。
  - 最終 artifacts：`f1-20-intake-final-v3.json` 與 `gemma3-20-intake-final-v3.json` 的追問／工具選擇／參數／金額／HITL／端到端均 **20／20**，PII 洩漏 0；另依 13 個有 `expected_money` 的情境獨立統計，兩者都是 **13／13**。
  - 依官方 Space 設定與相依套件文件補齊根目錄 README YAML metadata、`requirements.txt` 的 `-e .` 安裝入口與 hosting 說明；`SPACE_ID` 模擬匯入只顯示雲端 provider，沒有啟動 Ollama 或呼叫模型。新增 PLAN D31。
  - 最終工程證據：`uv lock --check`、`uv sync --locked --all-groups`、本輪模組 `py_compile` 成功，完整 pytest **495 passed in 3.97s**；兩份 v3 artifact 各 20 traces，metrics 與預期逐欄完全一致。公開檔案的疑似 token、私密路徑／作者信箱、禁詞與 50 MiB 大檔掃描均為 0。20 題仍是小型診斷集，雲端新版仍只有 connector smoke，不宣稱統計泛化或同版三模型排名。
  - 成本與 Git：本輪只跑地端 Ollama，API 成本 US$0；沒有讀取／修改 `.env`，沒有停止其他專案，也沒有執行任何 Git 指令。建議功能 commit：`fix(agent): 加入有限首次工具重試與嚴格 adapter 正規化`；文件可另以 `docs: 同步地端最終評估與 Space 設定` 提交。

- **2026-07-22（公開稽核摘要、乾淨安裝與交付性驗證）**：
  - 新增 public evaluation exporter；輸入仍是 ignored raw artifacts，但輸出只含逐題布林評分、aggregate、provider／model、scenario set 與 artifact SHA-256。對話、tool args／results、attempts、notes 一律排除；coverage、順序、trace 數或 metrics 不一致會直接拒絕。新增 PLAN D32。
  - 產生 `eval/results/local-models-v3.json`：兩模式各 20 rows，端到端 20／20、金額題 13／13、PII 0；掃描確認不含測試身分證、電話、姓名、raw conversation 或工具參數。連續重建的檔案 SHA-256 相同，證明 exporter 輸出可重現。
  - `uv build` 成功建立 sdist／wheel；在 repo 外全新 Python 3.11 venv 安裝 wheel 後，CLI `--offline-demo --approve` 成功。wheel 共 39 files，含 entry points 與 `py.typed`，不含 `.env`、artifacts 或 models。
  - 乾淨 wheel 安裝曾解析到比 `uv.lock` 更新的 connector；先固定頂層後再比對，仍發現 `certifi`、`google-auth` 兩個 transitive 漂移。因此改由 `uv export --locked --no-dev --no-emit-project` 產生完整 `requirements.lock.txt`，根目錄 `requirements.txt` 先引用 constraints 再 `-e .`。測試會逐字比對 exporter，避免日後更新 lock 忘記同步。另一個全新 venv 依該檔安裝後，版本逐項相符；root `app.py` 在 `SPACE_ID` 模擬下匯入成功且只列雲端 provider，沒有模型呼叫。本機與 Space 模擬 venv 的 `uv pip check` 均為 `All installed packages are compatible`。
  - 受控 fixture 使用未占用的 17861，桌機／390 px 手機、進階設定、連續兩輪、歷史展開 smoke 均為 `UI_SMOKE_OK`、console 0 error；結束後核對本輪 PID 並釋放連接埠，沒有停止其他程序。
  - 六支 project skills 在 Windows 設 `PYTHONUTF8=1` 後均由 skill-creator validator 輸出 `Skill is valid!`；未設 UTF-8 時 validator 會被系統 cp950 讀檔阻擋，這是驗證工具的 Windows encoding 限制，不是 skill 內容錯誤。
  - 最終證據：evaluation 專屬 **17 passed**；`uv lock --check`、新增 exporter `py_compile` 通過，完整 pytest **497 passed in 5.36s**。API 成本 US$0；沒有執行 Git。建議新增 commit：`feat(eval): 發布去識別化固定集評估摘要`；Space pins 與完成度文件可併入文件 commit。
  - 免費成本準備：最新 workflow 可能包含一次初始重試與最多三次續跑，故不沿用舊版 6 calls 假設；以更保守的 8 calls × 20 題 × 每次 12k input／3k output、input US$0.30／1M、output US$2.50／1M 重跑腳本，得到 160 calls、1.92M input、480k output、上限 **US$1.776**。這只是待核准估算，未送出任何雲端請求。
  - 公開 CI：查閱 uv 官方 integration guide，新增 Windows workflow；`actions/checkout@v7`、setup-uv v8.1.0 commit SHA、uv 0.11.18、Python 3.11，依序執行 lock check、dev sync、完整 pytest 與 build。workflow 沒有 `secrets.*`、模型或付費 API 步驟；YAML 解析與架構測試通過，新增 PLAN D33。完整 pytest 隨後為 **498 passed in 3.77s**。
  - 清理：乾淨 wheel／Space 安裝使用的 repo 外暫存環境約 496.5 MiB；完成版本與相依性查證後已核對絕對路徑並刪除。內容只有可由 lock／build 重建的測試 venv 與 distributions，不影響 workspace 或模型。

- **2026-07-22（發布前重跑與作者交接）**：
  - 依 `resume-context`／`review-phase` 復原並逐項核對完成度，不以先前摘要代替證據。再次執行 `uv lock --check`、`uv sync --locked --all-groups`、public evaluation export、完整 pytest 與 `uv build`；結果為 **498 passed in 5.78s**，sdist／wheel 均成功產生。
  - `uv pip check` 顯示所有 91 個安裝套件相容；以臨時 `SPACE_ID`／非秘密模型字串模擬託管環境，provider 清單只有 `gemini`，沒有啟動或呼叫 Ollama／雲端模型。
  - 對 83 個公開候選檔案重跑 token、作者私密路徑／信箱與 50 MiB 大檔掃描：三項命中皆為 0。`.env` 未讀取、未修改、未納入掃描輸出；本輪 API 成本 US$0。
  - 新增 `docs/release-checklist.md`，把作者本機驗證、分組 commit、Push、GitHub CI、Space Secrets／Variables、公開兩輪 smoke 與可選 tag／Release 串成單一路徑；README 修正一處可能把歷史雲端固定集誤讀為新版已重跑的文字。
  - 文件變更後再次完整 pytest 為 **498 passed in 3.88s**；UI 專屬 11 passed，Agent／evaluation／架構合計 52 passed。14 份 Markdown 的本機連結全數有效，快速回憶區 18 行，六支 project skills 均輸出 `Skill is valid!`；84 個公開候選檔案的秘密、私密身分與大檔掃描仍全部為 0。
  - 最後以當前 README／發布文件重建 distribution：完整 pytest **498 passed in 3.81s**，sdist／wheel 成功，14 份 Markdown 連結仍全數有效。
  - Git：Agent 未執行任何 Git 指令。建議文件 commit：`docs: 補充發布與公開驗收清單`。

- **2026-07-22（GitHub CI、Space 建立與公開檔案再稽核）**：
  - 作者自行建立四筆正體中文 commit 並 Push `main` 至 GitHub `3b272e4`；工作目錄與 `origin/main` 同步。公開 GitHub Actions `CI #1` 對該 commit 顯示 `Status Success`，總時間 46 秒；CI 未使用 Secrets 或模型 API。
  - 作者建立公開 Gradio Space `steven0226/ltc-benefit-agent`，選用 CPU Basic／Blank／Public；已保存公開 Variables `GEMINI_MODEL`、`GEMINI_THINKING_LEVEL` 與私密 Secret `GEMINI_API_KEY`，截圖中未顯示 Secret 真值。Space 尚未收到程式碼，因此未宣稱部署完成。
  - 以不讀 Git 狀態的檔案盤點檢查 84 個公開候選檔案：總計約 1.03 MiB，沒有完全重複檔案、大型模型、raw artifacts 或超過 50 MiB 的檔案。`uv.lock` 與 `requirements.lock.txt` 分別服務 uv／CI 與 pip／Space；PLAN／PROGRESS／PRODUCT／project skills 依作者長期維護要求保留。
  - 發現 portable ignore 規則缺少 `dist/`，以及 `CLAUDE.md` 的 Conventional Commit 語言規則比 `AGENTS.md` 少一段；已補上 `dist/` 並同步正體中文規則。這是發布清理，不改架構或驗收標準，PLAN 不新增 Decision Log。
  - 成本與 Git：本輪 API 成本 US$0；Agent 未讀取 `.env`、未執行 Git 或帳號寫入。待作者驗證後建議 commit：`chore: 補齊發布忽略規則並同步開發規範`。

- **2026-07-22（Space 首次 Build 診斷與相依單檔修正）**：
  - 作者完成 Hugging Face CLI browser OAuth、確認 `whoami` 為 `steven0226`，並自行把 `main` 強制安全更新至新建 Space 的 `95654f8`；原遠端只有 Hugging Face 自動建立的 `.gitattributes` 與 15 行 README 初始化 commit。
  - 首次公開 Build 在安裝階段以 exit code 1 停止；log 明確顯示 builder 執行 `pip install -r /tmp/requirements.txt`，而入口檔中的 `-r requirements.lock.txt` 被解析為不存在的 `/tmp/requirements.lock.txt`。這不是 API key、模型、CPU 或 Gradio runtime 錯誤。
  - 修正為把 `uv export` 的完整 runtime pins 直接內嵌於根目錄 `requirements.txt`，最後保留 `-e .`；刪除重複的 `requirements.lock.txt`。UI 架構測試改為逐字比對內嵌 pins 與即時 `uv export`，PLAN 新增 D34，hosting／release checklist 同步記錄 Space 的單檔複製限制。
  - 實跑證據：`uv lock --check` 成功、UI **11 passed in 2.47s**、完整 pytest **498 passed in 3.59s**、sdist／wheel build 成功；`uv pip install --dry-run -r requirements.txt` 檢查 87 個 packages 並顯示 `Would make no changes`。
  - 成本與 Git：本輪未呼叫模型 API，成本 US$0；未讀取或修改 `.env`，Agent 未執行任何 Git 指令。待作者自行提交並 Push `origin`／`space` 後，以公開 Build log 作最終部署證據。建議 commit：`fix(space): 內嵌鎖定相依以修正建置路徑`。

- **2026-07-23（Space 第二次 Build 診斷與 runtime 自舉）**：
  - 作者自行將相依單檔修正 commit `879f3d5` Push 至 GitHub 與 Hugging Face Space。第二次公開 Build 已能完整讀取內嵌 pins，但在同一個 pipfreeze 階段解析 `-e .` 時回報 `/app` 尚無 `setup.py` 或 `pyproject.toml`。
  - Build log 證明實際順序為：先把 `requirements.txt` mount 到 `/tmp` 並安裝，之後才 `COPY --link ./ /app`。因此 requirements 改為只包含 `uv.lock` 匯出的外部套件；根目錄 `app.py` 在 runtime 以 `Path(__file__).resolve().parent / "src"` 加入 module path，再載入正式 UI。新增 PLAN D35，hosting／release checklist 與架構測試同步鎖住此順序。
  - 實跑證據：`uv lock --check` 成功、UI **11 passed in 2.31s**、完整 pytest **498 passed in 3.10s**、sdist／wheel build 與 `app.py` 的 `py_compile` 成功；`uv pip install --dry-run -r requirements.txt` 檢查 86 packages 並顯示 `Would make no changes`。
  - 成本與 Git：本輪未呼叫模型 API，成本 US$0；未讀取或修改 `.env`，Agent 未執行任何 Git 指令。待作者自行提交並依序 Push `origin`／`space`。建議 commit：`fix(space): 改由 runtime 載入 src package`。

- **2026-07-23（Space 第三次 Build 診斷與 extras 相容 lock）**：
  - 作者自行將 runtime 自舉 commit `211de11` Push 至 GitHub 與 Space。第三次公開 Build 已越過 include／editable install 問題，但 resolver 明確拒絕專案 lock 的 Pydantic 2.13.4；Space 自動加入的 `gradio[oauth,mcp]==6.20.0` 要求 Pydantic 2.11.10–2.12.x。
  - 依 Context7 `/gradio-app/gradio` 確認 MCP 由 `gradio[mcp]` extra 安裝，再以官方 PyPI 6.20.0 JSON metadata 複核版本範圍。因公開 builder 實際訊息使用 `<2.12.5`，在 `pyproject.toml` 加入 `pydantic>=2.11.10,<2.12.5`，重新解析 lock 為 Pydantic 2.12.4／core 2.41.5；連帶把要求 Pydantic >=2.12.5 的 `google-genai` 2.13.0 降為相容的 2.8.0。
  - 以 builder 顯示的完整參數執行 Python 3.11 原生 pip dry-run：`requirements.txt`、`gradio[oauth,mcp]==6.20.0`、`uvicorn>=0.14.0`、`websockets>=10.4`、`spaces` 全部成功解析；uv dry-run 亦成功。使用 dummy key 僅建構 LangChain connector，輸出 `ChatGoogleGenerativeAI gemini-3.5-flash-lite medium`，沒有送出網路模型請求。
  - 實跑證據：`uv sync --locked --all-groups` 成功、`uv pip check` 為 91 packages compatible、Agent／UI／架構 **46 passed in 2.79s**、完整 pytest **498 passed in 3.16s**、sdist／wheel build 成功。真實 Gemini smoke 尚未執行，需待 Space Running 後另列上限取得核准。
  - 成本與 Git：本輪模型 API 成本 US$0；未讀取或修改 `.env`，Agent 未執行任何 Git 指令。待作者自行 commit 並依序 Push `origin`／`space`。建議 commit：`fix(space): 對齊 Gradio MCP 的 Pydantic 相依`。

- **2026-07-23（公開 Space Running 與版本比較驗收修正）**：
  - 作者自行建立 `7e06a7c fix(space): 對齊 Gradio MCP 的 Pydantic 相依`，依序 Push GitHub 與 Hugging Face Space。Hugging Face API 回報相同 commit、`RUNNING`、CPU Basic；公開首頁 HTTP 200，第四次 Build 已通過。
  - 作者在公開 UI 手動輸入已知 CMS 4、一般戶、無外籍看護、預計 18,000 元情境；系統成功完成多輪追問、資格工具、金額工具與確定性草稿。畫面金額為原始／調整額度 18,580 元、政府給付 15,120 元、額度內部分負擔 2,880 元、超額 0 元，與整數公式一致。
  - 公開草稿同時揭露兩個驗收缺陷：勾選「同時顯示 2022 舊制」後，UI 附加訊息中的 `LEGACY_2022` 被 intake 當成主版本，導致主報告誤用舊制；資格結論與身分依據直接顯示英文 enum。作者尚未按核准，因此未把有誤版本發布為最終報告。
  - 修正以 `INTERFACE_COMPARE_HISTORICAL_SNAPSHOT=true; PRIMARY_RULE=CURRENT_2026_07` 專用 directive 表達比較意圖；workflow 仍建立 legacy 附錄，但 intake 主版本只看到現制。renderer 另把四種資格狀態與五種身分依據轉為正體中文，工具／trace enum 不變。新增 PLAN D37。
  - 實跑證據：新增 UI directive、intake version intent、workflow comparison 與 report label 回歸斷言；Agent＋UI 專屬 **38 passed in 2.74s**。隨後 `uv lock --check`、完整 pytest **500 passed in 3.10s**，sdist／wheel build 均成功。
  - 成本與 Git：作者手動 Space 對話會使用 Gemini，但本輪沒有 usage metadata，實際費用以帳單為準；Agent 未另發模型請求、未讀取 `.env`、未執行 Git。測試完成後建議 commit：`fix(report): 修正舊制比較版本與資格中文顯示`。

- **2026-07-23（公開一般戶試算驗收與福利類別正規化）**：
  - 作者自行建立並同步 `7aa06bf fix(report): 修正舊制比較版本與資格中文顯示`；Hugging Face API 回報相同 SHA、`RUNNING`、CPU Basic。公開複驗確認主報告已改為 `CURRENT_2026_07`，資格結論與「65 歲以上老人」均為正體中文，不再洩漏 raw enum。
  - 同一張公開草稿顯示使用者明確輸入「一般戶」卻被模型傳成第一類，導致部分負擔 0%、政府給付 18,000 元。正確應為第三類 16%、政府給付 15,120 元、額度內部分負擔 2,880 元；作者尚未核准錯誤草稿。
  - intake 新增福利身分同義詞正規化：第一類／長照低收入戶、第二類／長照中低收入戶、第三類／長照一般戶／一般戶；每輪使用最後一個明確標籤，並在 tool middleware 中覆蓋模型參數。system prompt 與 tool schema 同步說明對應關係，新增 PLAN D38。
  - 回歸案例讓模型故意送出 `FIRST`、使用者輸入「一般戶」，最終 `copay_estimate` audit payload 仍為 `THIRD`，草稿為第三類、16%、政府給付 15,120 元、自付 2,880 元。另以七種公開標籤逐一驗證映射。
  - 實跑證據：Agent 專屬 **35 passed in 1.02s**；`uv lock --check`、完整 pytest **508 passed in 3.20s**，sdist／wheel build 均成功。
  - 成本與 Git：作者手動 Space 對話的實際 token／費用無法由畫面取得；Agent 未另發模型請求、未讀取 `.env`、未執行 Git。建議 commit：`fix(agent): 鎖定福利身分類別正規化`。

- **2026-07-23（公開核准事件診斷與穩定 session 修正）**：
  - 作者自行建立 `93b7a2d fix(agent): 鎖定福利身分類別正規化` 並同步 GitHub／Space；Hugging Face API 回報相同 SHA、`RUNNING`、CPU Basic。公開草稿確認主版本 `CURRENT_2026_07`、第三類、16%、政府給付 15,120 元、額度內部分負擔與合計自付 2,880 元，福利類別與金額缺陷已通過。
  - 作者第一次按「核准並發布」後畫面仍保留操作按鈕，第二次顯示 `common.error`。Space runtime log 明確回報 `此 thread 沒有待確認的完整報告`；問題位於 Gradio session／完成狀態同步，不是資格、金額或 registry 改寫。
  - 依 Context7 `/gradio-app/gradio` 的 session state 與多輸出 callback 文件，UI 改用 `gr.State(lambda: uuid4().hex)` 作每個瀏覽器 session 的穩定 thread ID，不再依賴跨 Space SSR 事件可能漂移的 `request.session_hash`。服務另保存已發布原文；相同 thread 重複 approve 直接回傳第一次結果，不再次 resume HITL 或新增 human decision。
  - Gradio 6 SSR 實測會讓作為事件來源的 Button 保留於 DOM，但能可靠更新 `interactive=False`。完成態因此明示為不可重按的「已核准並發布」，拒絕按鈕以 disabled CSS 隱藏；上方固定顯示「報告已核准；發布內容與校閱草稿逐字一致。」新增 PLAN D39。
  - 零模型 fixture／Playwright 在未占用的 7873 實際產生草稿並點擊核准，輸出 `UI_SMOKE_OK`；畫面確認完成文案、disabled 按鈕、拒絕按鈕隱藏與 15,120／2,880 元保持不變。測試只終止本輪核對過 PID 的 fixture，未碰其他程序。
  - 實跑證據：Agent＋UI **46 passed in 2.83s**；`uv lock --check`、完整 pytest **508 passed in 3.40s**，sdist／wheel build 成功。沒有呼叫模型 API，新增成本 US$0；未讀取 `.env`、未執行 Git。建議 commit：`fix(ui): 穩定 Space 核准 session 與完成狀態`。

- **2026-07-23（公開核准流程驗收通過）**：
  - 作者自行建立 `3250ed2 fix(ui): 穩定 Space 核准 session 與完成狀態`，依序 Push GitHub 與 Hugging Face Space；Hugging Face API 回報完整 SHA `3250ed24ecf331b5f654bdcd0d19a3f72551cee0`、`RUNNING`、CPU Basic。
  - 作者以全新公開 Space session 重跑已知 CMS 4、一般戶、無外籍看護、預計服務費 18,000 元案例；報告維持現制、第三類、16%、原始／調整後月額 18,580 元、政府給付 15,120 元、額度內部分負擔／合計自付 2,880 元、超額 0 元。
  - 單次按下「核准並發布」後，畫面改為不可重按的「已核准並發布」，拒絕操作消失，未出現 `common.error`；公開最終內容與核准前草稿數字一致。因此 D39 的 stable session、冪等 approve 與明確完成狀態通過公開端到端驗收。
  - 成本與 Git：作者手動 Space 對話會使用 Gemini，但頁面沒有 usage metadata，實際費用以帳單為準；Agent 未另發付費請求、未讀取 `.env`、未執行 Git。本次僅有 `PROGRESS.md` 驗收紀錄待作者自行提交，建議 commit：`docs: 記錄 Space 核准流程公開驗收`。

- **2026-07-23（unknown CMS 公開驗收失敗與雙層防護修正）**：
  - 作者在全新公開 Space session 輸入完整 unknown CMS 情境，明確寫出尚未正式評估、不知道等級、不要推估，並要求 CMS 2 至 8 級參考表。公開 `dcb45a9` 卻產生 CMS 2、第三類、16%、政府給付 8,417 元與合計自付 1,603 元的個人試算；作者未按核准。
  - 根因是 intake／workflow 的舊 regex 把「CMS 2 至 8」前半段截成正式 CMS 2。修正新增參考範圍排除、明確 unknown 語句、正式單級與跨輪最新意圖覆寫；明確 unknown 會同時保存 `official_cms_level=None` 與 `cms_level=None`。
  - model response guard 會把 unknown CMS 下的猜測 `copay_estimate` 改成 `build_report_draft`；tool call guard 再獨立拒絕任何漏網試算。build report 強制使用 null CMS 並移除個人金額欄位。workflow 共用同一 parser，不再自行用較寬鬆 regex 判斷。
  - 同一公開句子同時含「洗澡、穿衣需要協助」與「吃飯、走動、如廁不需要協助」，也揭露舊 boolean parser 的負向片段可能蓋過正向需求；修正為有任一項明確需協助即為 True，只有純負向敘述才為 False，並補上「住在家裡」字面辨識。
  - 回歸假模型刻意送出 CMS 2 並嘗試呼叫金額工具；實際成功 trace 只有 `eligibility_check → build_report_draft`，資格 artifact 的 CMS 為 null，草稿顯示「CMS 未知：僅提供額度參考」、完整 2–8 表，且沒有政府給付或合計自付。相關 8 passed、Agent **41 passed in 0.97s**。
  - 最終證據：依 Context7 `/websites/langchain_oss_python` 查證 middleware 現行 API；`uv lock --check`、相關模組 `py_compile`、完整 pytest **514 passed in 3.22s**、sdist／wheel build 均成功。沒有呼叫付費模型、沒有讀取 `.env`、沒有執行 Git。建議 commit：`fix(agent): 阻止未知 CMS 被誤判為個人等級`。

- **2026-07-23（CMS 白話說明與回答提示）**：
  - 首頁 4 步操作後加入一段緊湊提示：CMS 是照管中心評估後核定的長照需要等級（第 2–8 級）；尚未評估可直接回答「不知道」，系統不會代猜。
  - 確定性缺漏追問改為先說「長照需要等級」再補 CMS 名稱；unknown CMS 報告與草稿狀態也重複一次短定義，讓使用者不必回頭找說明。
  - 依 `impeccable` 的 clarify／product 原則採用就地說明與漸進揭露，不新增大型說明卡。針對 UI／Agent 測試 **52 passed in 2.83s**；`uv lock --check`、相關模組 `py_compile`、完整 pytest **514 passed in 3.20s**、sdist／wheel build 均成功。
  - 沒有呼叫付費模型、沒有讀取 `.env`、沒有執行 Git。建議 commit：`fix(ui): 補充 CMS 白話說明與回答提示`。

- **2026-07-23（多輪回答操作引導）**：
  - 依使用者首次送出後的實際截圖，將追問標題改為「目前這一題」，並把回答欄集中成獨立的「下一步：在這裡回答」操作區；明示可以分多次補充，按鈕改為「送出回答，繼續下一題」。
  - 每次開始或送出回答後，以 Gradio 6 的前端 `.then(fn=None, js=...)` callback 將焦點移回可見的回答欄；依 Context7 `/gradio-app/gradio/gradio_6.0.1` 確認 `Textbox.autofocus` 與事件 listener 的現行用法後實作。
  - 獨立 fixture 使用 7862，不影響作者的 7860；桌機與 390 px 手機多輪 smoke 均通過，第一輪與第二輪追問後輸入欄皆取得焦點，結果為 `UI_SMOKE_OK`。測試服務已關閉，沒有停止作者的既有程式。
  - 最終證據：`uv lock --check`、相關 UI／Agent 模組 `py_compile`、完整 pytest **514 passed in 3.33s**、sdist／wheel build 均成功。沒有呼叫付費模型、沒有讀取 `.env`、沒有執行 Git；建議 commit：`fix(ui): 強化 CMS 說明與多輪回答引導`。

- **2026-07-23（常駐聊天面板與直接多輪操作）**：
  - 依作者實際操作回饋，移除「目前這一題」獨立卡片與「查看完整對話紀錄」折疊層；改為單一常駐 Chatbot，user／assistant 訊息以 bubble transcript 直接顯示，回答欄與送出按鈕固定整合在同一面板下緣。
  - 依 `impeccable` 的 clarify／product 原則收斂為唯一主要路徑；再以 Context7 `/gradio-app/gradio/gradio_6.0.1` 核對 `Chatbot` 的 `messages`、`autoscroll`、`layout`、高度與事件現行 API。前端 callback 會找出實際可捲動容器、移至最新訊息，再聚焦回答欄。
  - Playwright fixture 使用獨立 7862，連續送出兩輪後不點擊任何展開控制即可看到完整上下文、第二筆使用者回答與下一個系統問題；桌機／390 px 手機截圖完成，輸出 `UI_SMOKE_OK`、console 0 error。測試中發現一個由本輪 helper 遺留的舊 fixture PID，核對 command line 為 `scripts/ui_fixture_app.py` 後只終止該測試程序並釋放 7862，未碰作者的 7860 或其他程序。
  - 最終證據：UI 專屬 **11 passed**；`uv lock --check`、相關模組 `py_compile`、完整 pytest **514 passed in 3.26s**、sdist／wheel build 均成功。沒有呼叫付費模型、沒有讀取 `.env`、沒有執行 Git；建議 commit：`fix(ui): 改為常駐多輪聊天介面`。

- **2026-07-23（對話中的精簡 4 步提示）**：
  - 初始頁仍顯示包含 CMS 與個資提醒的完整操作說明；開始對話後，聊天面板頂端改用緊湊提示列持續呈現「看最新問題、在下方回答、不知道就說不知道、資料齊全後確認報告」。
  - 桌面版以標題加四欄橫向排列；900 px 以下自動變成標題加 2×2 步驟，不增加折疊操作，提示與主要對話使用同一 960 px 寬度。
  - 依 `frontend-design` 的產品介面原則維持既有平靜、可信配色；再用 Context7 `/gradio-app/gradio/gradio_6.0.1` 確認 `Markdown`、`elem_id`、`visible` 與 CSS 選擇器的現行介面。
  - UI pytest **11 passed in 2.23s**；獨立 7862 fixture 的桌機／390 px 手機多輪 smoke 為 `UI_SMOKE_OK`、console 0 error，兩種尺寸均驗證提示文字、最大高度及無水平溢出。helper 遺留的 listener 經 PID 與 command line 核對為 `scripts/ui_fixture_app.py` 後只終止該測試程序，7862 已釋放。
  - 最終證據：`uv lock --check`、相關模組 `py_compile`、完整 pytest **514 passed in 3.33s**、sdist／wheel build 均成功。沒有呼叫付費模型、沒有讀取 `.env`、沒有執行 Git；建議 commit：`fix(ui): 在多輪對話保留精簡操作提示`。

- **2026-07-23（精簡步驟導覽視覺調整）**：
  - 依作者本機截圖，將原本容易不規則斷行的純文字提示列改為四張等寬步驟卡；每張卡以淡綠編號圓點建立掃讀順序，外層使用低彩度漸層、細框與極淡陰影，沒有新增裝飾圖示或動畫。
  - 桌面維持四欄，900 px 以下改為 2×2；桌面正文 18 px、手機 17 px，與既有高齡友善字級及綠色產品語彙一致。
  - 依 `frontend-design` 的 refined minimal 方向調整；Context7 `/gradio-app/gradio/gradio_6.0.1` 再確認 `gr.Markdown` 的 `elem_id` 與自訂 CSS 範圍。
  - UI pytest **11 passed in 2.20s**。瀏覽器檢查前發現原預定 7862 已由 `5_doc-inspector` 使用，因此沒有停止該程序，改用已確認空閒的 17870；桌機／390 px 手機多輪 smoke 均為 `UI_SMOKE_OK`、console 0 error。結束後只終止命令列確認為本輪 `scripts/ui_fixture_app.py` 的 PID，17870 已釋放。
  - 最終證據：`uv lock --check`、相關模組 `py_compile`、完整 pytest **514 passed in 3.14s**、sdist／wheel build 均成功。沒有呼叫付費模型、沒有讀取 `.env`、沒有執行 Git；建議 commit 維持：`fix(ui): 在多輪對話保留精簡操作提示`。
  - 作者已在本機 7860 實際看到最終桌面畫面，確認「UI/UX 的部分沒問題」；因此本輪由「工程完成，待驗收」更新為「本機視覺驗收通過」。公開 Space 仍待作者提交與重新部署後複驗。
  - 依作者最後微調，首頁 CMS 說明移除「不知道 CMS 沒關係：」前綴，直接以 CMS 定義開頭，減少不必要的文案層級。
  - 作者再次檢查 CMS 文案微調後的本機畫面，確認 UI/UX 最終無問題；本機 UI/UX 驗收正式完成，下一步由作者自行提交並同步 GitHub／Hugging Face Space。
  - 作者已將 commit `dafaea4` 同步至 GitHub 與 Hugging Face Space，並以公開 Space 截圖確認新版首頁正常上線：四步操作、CMS 定義、個資提醒、主要輸入區與進階設定皆正確顯示。公開 UI/UX 驗收完成。
  - 稽核先前保留的 Agent 文案差異：追問欄位、缺漏提示、未知 CMS 參考報告與草稿完成訊息皆統一補上「照管中心核定的長照需要等級（第 2–8 級）」白話定義；資格與金額邏輯未變。`tests/test_agent_phase2.py` **41 passed in 1.37s**。

- **2026-07-23（Phase 4 最終公開驗收與 review-phase）**：
  - 作者已將 CMS 白話說明 commit `55e872f` 同步至 GitHub 與 Hugging Face Space；公開首頁、常駐聊天面板、精簡四步提示與報告校閱介面均正常。
  - unknown CMS 公開 smoke 通過：系統只顯示 CMS 2–8 額度參考表、1966 與下一步申請流程，沒有推估個人 CMS，也沒有個人化政府給付或合計自付；單次核准後畫面顯示「已核准並發布」。
  - 最終本機證據：`uv lock --check` 成功、`uv pip check` 顯示 91 packages compatible、完整 pytest **514 passed in 4.64s**、`uv build` 成功產生 sdist／wheel、離線 CLI `--approve` 完成預覽與逐字發布。
  - 公開 CI 證據：GitHub Actions 對 `55e872f` 與前四筆公開 commit 均為 `completed / success`。公開文案掃描未發現禁止名稱；敏感字串掃描只命中 PROGRESS 的歷史測試帳號敘述，已改為不具識別性的泛稱。
  - 作者已將最終驗收文件 commit `85a9461` 同步至 GitHub 與 Hugging Face Space；公開 API 確認 Space 為 `RUNNING`／CPU Basic，該 commit 的 GitHub Actions 結果為 `completed / success`。
  - Phase gate：Phase 0–4 與公開交付全部通過；新版雲端同版 20 題仍是可選診斷，需另行核准 US$1.776 上限，不是發布阻擋條件。
  - 成本與 Git：Agent 本次 review 沒有呼叫付費模型，新增成本 US$0；作者手動 Space smoke 的實際 usage 以帳單為準。Agent 未執行 Git。建議 commit：`docs: 完成 Phase 4 公開驗收紀錄`；該 commit 的 CI 成功後，可由作者自行建立 `phase-4` tag／Release。
