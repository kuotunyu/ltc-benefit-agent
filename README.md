---
title: LTC Benefit Agent
emoji: 🧮
colorFrom: green
colorTo: gray
sdk: gradio
sdk_version: 6.20.0
python_version: "3.11"
app_file: app.py
fullWidth: true
header: mini
short_description: 可稽核的台灣長照 2.0 資格初篩與補助試算
---

# ltc-benefit-agent

> **可驗證、可稽核的台灣長照 2.0 資格初篩與補助試算 Agent**

![Python 3.11](https://img.shields.io/badge/Python-3.11-185A45?style=flat-square)
![tests 535 passed](https://img.shields.io/badge/tests-535%20passed-185A45?style=flat-square)
[![CI](https://github.com/kuotunyu/ltc-benefit-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/kuotunyu/ltc-benefit-agent/actions/workflows/ci.yml)
![License MIT](https://img.shields.io/badge/license-MIT-4B5D55?style=flat-square)
![UI Gradio](https://img.shields.io/badge/UI-Gradio-4B5D55?style=flat-square)

[線上操作](https://huggingface.co/spaces/steven0226/ltc-benefit-agent) ·
[Phase 4 Release](https://github.com/kuotunyu/ltc-benefit-agent/releases/tag/phase-4) ·
[原始碼](https://github.com/kuotunyu/ltc-benefit-agent)

**對話交給模型；資格與金額交給 Python；最終報告交給人確認。LLM 不算錢。**

## 為什麼做這個專案

我做這個專案，是因為面對家人可能需要長照時，讀懂規定只是第一步，真正困難的是把年齡、身分、CMS、福利類別和每月服務費換算成「我家大概能用多少、要付多少」。因此這不是一個讓語言模型自由回答的計算機，而是一套可驗證、可稽核的協作流程：對話模型只負責理解、追問與選工具；資格、額度、部分負擔、超額與無條件捨去一律由確定性 Python 工具計算。**LLM 不算錢。**

> 本專案僅供初步試算。規則常數已依官方資料建立測試，並於公開前由作者逐項人工校對；法規修正後仍須重新查證。它不是正式資格核定、法律、醫療或財務建議，最終以照管中心、地方主管機關及 1966 回覆為準。

目前已完成確定性工具、離線 Agent／CLI、PII 防護、人工核准、20 題診斷 evaluator、兩個地端模式、歷史雲端固定集與聊天介面。固定集都使用相同情境與確定性評分，不以模型自評或單題 smoke 代填主表；新版雲端模型尚未在最新 workflow 上重跑，相關表格會明確標示版本邊界。

## 專案亮點

| 多輪對話引導 | 確定性規則工具 | 人工確認與稽核 |
|---|---|---|
| 依缺漏資料逐項追問；CMS 未知時不猜級 | 資格、額度、比例、捨去與超額皆由純 Python 計算 | PII 遮蔽、工具 trace、完整報告預覽與 approve／reject |

## 介面預覽

![ltc-benefit-agent 多輪試算介面](docs/assets/gradio-showcase.png)

> 預覽使用虛構測試情境與零模型 fixture；不包含真實個資，也不代表正式資格核定。

## 核心邊界

- 預設使用 `CURRENT_2026_07`；只有使用者明確要求才比較 `LEGACY_2022`。
- CMS 必須是使用者已知的正式評估結果。未知時不猜級，只顯示申請初篩、CMS 2–8 參考表與 1966 指引。
- v1 個人化金額只涵蓋「照顧及專業服務」月額；交通、輔具、無障礙改善與喘息不混入試算。
- 輸入型別不接受姓名、身分證、電話或地址。
- 現制福利身分使用法定「第一類／第二類／第三類」，不把模糊口語自行映射。
- 最終 Markdown 先由 renderer 建稿，再於 `publish_report` 暫停；核准後輸出與預覽逐字相同。
- 未經 renderer 與人工核准的模型訊息若含幣值或百分比，服務層會直接攔截，不讓模型自行生成的金額對外顯示。

## 法規快照稽核

民眾操作不會即時抓取法規網站。獨立的確定性 checker 會核對四個官方白名單來源，並以 `VERIFIED_SNAPSHOT`、`REVIEW_REQUIRED`、`CHECK_UNAVAILABLE` 區分「內容一致」、「需要人工複核」與「未完成檢查」。raw bytes 改變不等於規則改變，結論以必要欄位的結構化比較為準。

P1 線上查證與 P2 離線複核分開執行：

```powershell
uv run --group audit ltc-rule-audit `
  --output artifacts/rule-audit/2026-07-23-online.json

uv run --group audit ltc-rule-audit `
  --input artifacts/rule-audit/2026-07-23-online.json `
  --review-output artifacts/rule-audit/2026-07-23-review.md `
  --project-root .
```

P2 另外比較 manifest、runtime metadata／常數、README、fixtures 與測試斷言。整個流程不使用 LLM，也不自動更新規則；任何差異都必須先由作者檢閱，再另開工作修改。完整來源與人工 gate 契約見 [法規來源 manifest](docs/research/rule-source-manifest.md)。

## Agent 與工具流程

```mermaid
flowchart TD
    U["使用者多輪敘述"] --> P["PII 遮蔽與最小化事件 log"]
    P --> A["對話 Agent"]
    A --> Q{"必要資料完整？"}
    Q -- "否" --> ASK["逐項追問"]
    ASK --> U
    Q -- "是" --> E["eligibility_check"]
    E --> C{"有正式 CMS 2–8？"}
    C -- "否" --> REF["CMS 參考表與 1966 指引"]
    C -- "是" --> M["copay_estimate：全整數試算"]
    A --> F["faq_search：法源摘錄"]
    REF --> D["build_report_draft：確定性 Markdown"]
    M --> D
    F --> D
    D --> H["publish_report：人工 approve／reject"]
    H -- "approve" --> R["逐字鎖定的最終報告"]
    H -- "reject" --> A
```

業務工具位於 `src/ltc_benefit_agent/tools/`，不依賴 Agent framework、不讀環境變數，也不進行網路呼叫。FAQ 有可選的姊妹作 adapter；未安裝時使用內建零依賴字詞搜尋，兩者回傳同一 schema。

## 快速開始

需求：Python 3.11 與 uv。Windows 本機使用 uv-managed Python 3.11。

```powershell
uv sync --locked
uv run pytest
```

不呼叫任何模型的完整報告預覽／核准示範：

```powershell
uv run ltc-benefit-agent --offline-demo --approve
```

啟動聊天介面：

```powershell
uv run ltc-benefit-ui
```

預設只綁定 `127.0.0.1:7860`。若連接埠已被占用，程式會停止並要求改用 `.env.example` 所列的連接埠設定，不會終止其他程式。模型與轉檔細節見[地端模型準備](docs/local-models.md)，託管限制見[託管環境指引](docs/hosting.md)，作者發布時可依[發布與公開驗收清單](docs/release-checklist.md)逐項操作。

## 公開介面

```python
from ltc_benefit_agent.tools import (
    CopayInput,
    EligibilityInput,
    ResidenceStatus,
    WelfareCategory,
    assess_eligibility,
    calculate_copay,
)

eligibility = assess_eligibility(
    EligibilityInput(
        age=70,
        indigenous=False,
        has_disability_certificate=False,
        has_dementia_diagnosis=False,
        is_pac_case=False,
        has_functional_impairment=True,
        impairment_duration_months=6,
        residence_status=ResidenceStatus.COMMUNITY,
        official_cms_level=4,
    )
)

estimate = calculate_copay(
    CopayInput(
        cms_level=4,
        welfare_category=WelfareCategory.THIRD,
        has_foreign_caregiver=False,
        planned_spend=12_000,
    )
)
```

所有金額都是整數新臺幣：

```text
adjusted_quota = base_quota 或 floor(base_quota × 30 / 100)
eligible_spend = min(planned_spend, adjusted_quota)
copay = eligible_spend × copay_percent // 100
government_payment = eligible_spend - copay
overage = max(planned_spend - adjusted_quota, 0)
total_out_of_pocket = copay + overage
```

未提供 `planned_spend` 時，只產生「額度全數使用示例」，不偽裝成實際帳單。

## 規則版本與數值

| 版本 | 快照日期 | 主要資格差異 |
|---|---:|---|
| `LEGACY_2022` | 2022-02-01 | 失智症須 50 歲以上；沒有 PAC 類別 |
| `CURRENT_2026_07` | 2026-07-01 完整快照 | 失智症不設年齡門檻；新增 PAC 短期需求；納入分階段生效修正 |

`CURRENT_2026_07` 是修正內容全部施行後的完整快照標籤，不代表所有規則都在 2026-07-01 才生效。2025-06-19 修正內容原則自 2025-09-01 施行；失智症取消 50 歲門檻、PAC 資格及第 10 條第一項等指定規定自 2026-01-01 施行；最後一批附表修正自 2026-07-01 施行。v1 不支援 2022 舊制與完整現制之間的過渡期日期查詢。

CMS 2–8 的照顧及專業服務月額為 10,020、15,460、18,580、24,100、28,070、32,090、36,180 元。聘僱外國家庭幫傭、家庭看護或中階技術家庭看護等法定情形時，此項額度按附表二額度的 30% 計算；該額度依法僅能用於附表四居家照顧服務以外之照顧組合。本工具只試算額度與部分負擔，不判定個別服務碼是否適用。部分負擔比率為第一類 0%、第二類 5%、第三類 16%。

完整來源、版本 metadata 與人工簽核欄位見[規則校對表](docs/research/rules-audit.md)。

## PII 與人工確認

- 使用框架 middleware 與防禦性入口遮蔽台灣身分證、手機／市話及「姓名／我叫」等標籤式姓名。
- model input、tool result、輸出與 audit payload 都經過遮蔽；log 只留事件、工具名稱及遮蔽後參數／結果，不保存原始對話。
- 未帶語境的裸姓名無法只靠 regex 完整辨識，因此介面明確要求不要輸入不必要個資。
- 官方 URL 內的數字不會被電話 regex 誤遮蔽。
- `publish_report` 只允許 approve／reject；registry 拒絕任何與草稿不一致的 Markdown。

## 20 題診斷結果

這 20 題不是 20 位真實民眾的統計，而是 20 戶預先寫好標準答案的模擬家庭。情境涵蓋年齡邊界、原住民、身障、失智、PAC、住宿排除、unknown CMS、三福利類別、外籍看護、零／低於／等於／超額支出、舊現制差異、PII 與提示注入。評分完全依 tool trace，不使用另一個 LLM 判分。

可以把每一題想成一戶家庭要連續通過以下關卡：

```text
問對缺漏資料 → 選對工具 → 傳入正確資料 → 取得正確結果
→ 不洩漏個資 → 送人工確認 → 整戶案件端到端通過
```

只要其中一關失敗，該題就不算端到端通過。例如金額雖然正確，但沒有在發布前等待人工核准，仍然是端到端失敗。

| 指標 | 白話意思 | 判讀方式 |
|---|---|---|
| 缺漏追問正確 | Agent 是否知道還缺什麼，並問對下一個問題 | 越高越好 |
| 工具選擇正確 | 必要工具全都有呼叫，且沒有呼叫不該用的工具 | 越高越好 |
| 工具參數正確 | 傳入年齡、CMS、福利類別、服務費等資料是否正確 | 越高越好 |
| 金額條件無誤 | 該算錢時結果完全一致；不該算錢時沒有金額標準答案 | 越高越好；口徑說明見下方 |
| PII 洩漏次數 | 測試個資是否出現在模型輸出、工具結果或 audit trace | 越低越好，0 最佳 |
| HITL 正確觸發 | 最終報告是否先停下來顯示預覽，等待人工核准 | 越高越好 |
| 端到端通過 | 前述要求是否在同一題全部通過 | 最嚴格、最重要 |

### 初始基線（可靠性強化前）

| 指標 | 雲端模式 | 3B 台灣地端 | 12B 地端基準 adapter |
|---|---:|---:|---:|
| 缺漏追問正確 | 10 / 20 | 18 / 20 | 12 / 20 |
| 工具選擇正確 | 12 / 20 | 0 / 20 | 5 / 20 |
| 工具參數正確 | 19 / 20 | 12 / 20 | 17 / 20 |
| 金額條件無誤（20 題口徑） | 19 / 20 | 14 / 20 | 19 / 20 |
| PII 洩漏次數 | 0 | 0 | 0 |
| HITL 正確觸發 | 10 / 20 | 0 / 20 | 4 / 20 |
| 端到端通過 | 7 / 20 | 0 / 20 | 3 / 20 |

### 可靠性強化後地端重測

intake middleware 會在 PII 遮蔽後，只保存使用者明確提供、可逐字核對的計算必要欄位；未提及的值保持未知，跨輪 CMS 與版本也不交給模型自行記憶。workflow middleware 則只在已有成功、可稽核的工具證據後接續固定流程：複製已驗證的資格／金額參數建立草稿，再把 registry 回傳的 `report_id` 與 Markdown 原文送入既有 HITL。兩層都不判資格、不算金額，也不把模型臆測值當成使用者資料。

若使用者已明確提供至少兩個資格欄位，而模型第一次仍漏掉 `eligibility_check`，系統最多只做一次結構化重試：不重送原始對話，只提供遮蔽後的明確欄位，且只暴露資格工具。12B 相容 adapter 只有在模型明確輸出單一、合法、完整 fenced JSON tool call 時才正規化；不從散文猜工具、不補參數，也不自行執行模型沒有選擇的工具。F1 的 Ollama Hermes template 另依原模型官方 chat template 補上 tool response 的工具名。

| 指標 | 3B 初始 | 3B 強化後 | 12B 初始 | 12B 強化後 |
|---|---:|---:|---:|---:|
| 缺漏追問正確 | 18 / 20 | 20 / 20 | 12 / 20 | 20 / 20 |
| 工具選擇正確 | 0 / 20 | 20 / 20 | 5 / 20 | 20 / 20 |
| 工具參數正確 | 12 / 20 | 20 / 20 | 17 / 20 | 20 / 20 |
| 金額條件無誤（20 題口徑） | 14 / 20 | 20 / 20 | 19 / 20 | 20 / 20 |
| PII 洩漏次數 | 0 | 0 | 0 | 0 |
| HITL 正確觸發 | 0 / 20 | 20 / 20 | 4 / 20 | 20 / 20 |
| 端到端通過 | 0 / 20 | 20 / 20 | 3 / 20 | 20 / 20 |

真正需要試算的 13 題中，強化後 F1 與 12B adapter 都是 `13 / 13` 金額完全一致。雲端模式尚未在這版 intake／workflow 上重跑，因此上方初始表的雲端 `7 / 20` 只能當歷史基線，不能直接和地端強化後數字宣稱同版優劣。重跑雲端固定集前仍須重新估算並核准費用。

### 金額列的正確讀法

20 題中只有 13 題具備正式 CMS 且應該進行金額試算；另外 7 題因 CMS 未知、初篩未符合或規則不適用，本來就不應試算。原始 evaluator 在這 7 題沒有設定金額標準答案，因此上表的 `19 / 20` 不能解讀成「實際算了 20 題並答對 19 題」。如果模型在這些題目誤呼叫金額工具，會由「工具選擇正確」指標判定失敗。

只看真正需要試算的 13 題，結果如下：

| 模式 | 初始基線 | 可靠性強化後 |
|---|---:|---:|
| 雲端模式 | 12 / 13 | 尚未同版重跑 |
| 3B 台灣地端 | 7 / 13 | 13 / 13 |
| 12B 地端基準 adapter | 12 / 13 | 13 / 13 |

### 結果代表什麼

- intake、有限結構化重試與確定性接續改善兩個地端模式的跨輪資料、工具選擇、建稿與 HITL：F1 端到端由 `0 / 20` 到 `20 / 20`，12B adapter 由 `3 / 20` 到 `20 / 20`。
- 兩個地端模式在這組固定診斷題全數通過，但仍不能據此宣稱可無人監督；正式服務仍需照管中心核定與報告發布前人工確認。
- 12B 的 S01 年齡邊界題與 S20 提示注入題，最終是在隔離原始對話、只暴露資格工具的一次性重試中，由模型明確輸出合法 JSON tool call 後通過；系統沒有從散文猜意圖，也沒有替模型捏造參數或資格結論。
- 初始雲端模式為 `7 / 20`；新 workflow 尚未重跑雲端固定集，不能用舊雲端數字宣稱目前三者排名。
- 所有已跑模式的 PII 洩漏仍為 0；安全閘門與人工核准沒有為了提高通過率而放寬。

這張表衡量的是「LLM 能否可靠地主持多輪工作流」，不是 Python 資格與金額規則本身的單元測試成績。後者另由下方 498 項 pytest 與 336 組規則／金額主矩陣驗證。

技術上，初始雲端固定集因每分鐘請求限制採限速 partial run，最後依 scenario ID 離線合併並從 raw trace 重跑 evaluator。F1 重測使用原模型官方 Hermes chat template 所要求的具名 tool response；12B 欄位使用明示相容 adapter，原始 manifest 不具 native-tools capability，因此結果不得描述成原模型原生 function-calling 成績。原 F1 模型卡自述 BFCL 91% 只作背景資料，不等於本專案 20 題表現。本診斷集樣本很小，不宣稱統計泛化。

去除原始對話、tool arguments、tool results 與 attempts 後的逐題布林評分，公開於 [local-models-v3.json](eval/results/local-models-v3.json)。摘要保留 scenario set／raw artifact SHA-256，並由 exporter 重新計算 metrics；coverage、順序、trace 數或 aggregate 不一致時會拒絕輸出：

```powershell
uv run python scripts\export_public_evaluation.py
```

## 測試與實跑證據

Windows 11、uv-managed CPython 3.11.15：

| 驗證 | 結果 |
|---|---:|
| pytest | 535 passed |
| 規則／金額主矩陣 | 336 組 |
| Agent／PII／HITL 離線整合 | 通過 |
| 固定診斷集 schema／evaluator | 20 題通過驗證 |
| UI session／託管限制／port 測試 | 通過 |
| 真實本機 12B 固定 20 題（最終強化後） | 20 / 20 端到端；需試算題 13 / 13 金額一致；0 次 PII 洩漏 |
| 真實本機 3B 固定 20 題（最終強化後） | 20 / 20 端到端；需試算題 13 / 13 金額一致；0 次 PII 洩漏 |
| 真實雲端 S14 單題 | 兩次獨立執行皆端到端通過；預覽與核准報告一致 |
| 真實雲端固定 20 題（初始基線） | 7 / 20 端到端；需試算題 12 / 13 金額一致；0 次 PII 洩漏；新 workflow 尚未重跑 |
| 真實雲端新版 connector smoke | stable `gemini-3.5-flash-lite` 連線成功；1 次 function call 的名稱與參數完全一致 |
| 瀏覽器桌機／手機 smoke | 通過、console 0 error |
| Windows 公開 CI | lock check、完整 pytest、distribution build；不使用 Secrets |
| 雲端模型呼叫 | 舊版兩次 S14 與固定 20 題；新版另完成一次 117-token connector smoke |

實際套件版本由 `uv.lock` 鎖定；目前主要 framework 版本為 Agent 1.3.14、graph runtime 1.2.9、UI 6.20.0、pytest 9.1.1。完整逐次證據與已知坑見 [PROGRESS.md](PROGRESS.md)。

## 成本

- 已完成兩次獨立的雲端 S14 smoke 與固定 20 題；evaluator 沒有回傳帳單值，因此不宣稱精確實際費用。
- 依 2026-07-22 執行前查證的標準文字單價、保守上限 6 次呼叫／題、每次 12k input 與 3k output：兩次 smoke 合計核准上限 US$0.09，20 題批次核准上限 US$0.90，累計保守上限 US$0.99。
- 上一項是已完成的舊 workflow 歷史授權。最新 workflow 多了一次有界初始重試與最多三次續跑保護；若要重跑新版 20 題，現以更保守的 8 calls／題、相同 token 上限與新模型單價估算：160 calls、1.92M input、480k output，費用上限 **US$1.776**。這筆尚未核准、也尚未執行。
- 新版 connector smoke 使用 61 input、56 output tokens；依當日標準單價推算約 US$0.0001583，實際帳單仍以方案與免費額度為準。這只驗證連線與 function calling，不是新版端到端成績。
- 真實雲端 smoke 或批次都必須先讓作者確認最新單價、token 假設與上限。
- 地端推論使用既有 GPU；權重轉檔前另檢查授權、磁碟、GPU 與執行中程序。

## 完整對話範例

1. [65 歲以上、正式 CMS 與服務費](docs/examples/01-age65-known-cms.md)
2. [55 歲原住民、第二類](docs/examples/02-indigenous-second-category.md)
3. [50 歲以下失智者、舊現制差異、CMS 未知](docs/examples/03-dementia-version-unknown-cms.md)

## 官方來源與資料授權

- [2022-02-01 歷史條文](https://law.moj.gov.tw/LawClass/LawOldVer.aspx?lnndate=20220120&lser=001&pcode=L0070059)
- [現行條文與附件](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0070059)
- [附表二：給付額度](https://law.moj.gov.tw/LawClass/LawGetFile.ashx?FileId=0000398330&lan=C)
- [附表五：部分負擔比率](https://law.moj.gov.tw/LawClass/LawGetFile.ashx?FileId=0000398333&lan=C)
- [1966 申請流程](https://1966.gov.tw/ltc/cp-6533-70777-207.html)

政府網站資料依各來源的政府資料開放授權條款與使用規範使用。本 repo 不重新散布大型附件，只保存官方 URL、版本快照與必要短摘錄。

## License

[MIT](LICENSE)
