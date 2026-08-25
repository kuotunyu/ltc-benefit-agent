# ltc-benefit-agent

[![CI](https://github.com/kuotunyu/ltc-benefit-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/kuotunyu/ltc-benefit-agent/actions/workflows/ci.yml)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-585%20passed-success)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **狀態：Frozen / Portfolio Complete（2026-08-20）** — `v0.2.0` 已完成 current-truth、發布與公開展示驗收；後續只保留官方來源監測與必要安全維護。

我在陪伴家人理解長照申請流程時，發現真正困難的往往不是缺少資訊，而是規則散落、版本混淆，以及試算結果難以核對。我希望把這段經驗整理成一個可稽核的開源作品：讓對話協助釐清需求，讓確定性程式負責資格初篩與金額計算，並把最終決定清楚留給照管中心與人工覆核。

本專案為具備確定性防禦與可驗證性的台灣長照 2.0 資格初篩與補助試算 Agent。系統遵守「模型負責自然語言對話與意圖理解，Python 負責資格與金額計算，人類專家 (HITL) 負責最終核准」的安全原則，以降低模型幻覺引發的金額誤算與越權承諾風險。

> **免責聲明**：本專案僅供初步試算與學術研究，非正式資格核定或法律、醫療建議；最終資格與金額以照管中心、地方主管機關與 1966 專線核定為準。

[線上 Demo](https://huggingface.co/spaces/steven0226/ltc-benefit-agent) · [Deployment lineage](docs/deployment-lineage.md) · [v0.2.0 Release](https://github.com/kuotunyu/ltc-benefit-agent/releases/tag/v0.2.0)

![ltc-benefit-agent 多輪試算介面](docs/assets/gradio-showcase.png)

---

## 系統核心機制

1. **計算與對話分離 (Deterministic Tools Only)**：
   金額、級別與部分負擔比例完全由版本化 Python 規則引擎計算，模型無法自由產生或覆寫任何幣值。
2. **保守式 Intake 與 Fail-Closed 防禦**：
   在使用者未確定 CMS 級別前，系統不會進行猜測或產生個人化金額，嚴格避免誤導使用者。
3. **全文 PII 遮蔽與隱私保護**：
   針對臺灣身分證、電話與標示姓名等支援類型，使用者輸入、工具調用參數與稽核紀錄會在模型邊界前遮蔽；公開操作仍禁止輸入真實個資。
4. **人工審核 (Human-in-the-Loop) 逐字鎖定**：
   試算報告草稿經由人工審核後發布，核准發布之內容與預覽草稿逐字簽章一致，防止中途竄改。

---

## 系統架構與防護流程

### 1. 系統模組與資安防護拓撲

```mermaid
%%{init: {'themeVariables': {'fontSize': '20px'}}}%%
flowchart TD
    U["使用者多輪對話"] --> P["PII 遮蔽過濾器<br/>(去識別化過濾)"]
    P --> I["保守式 Intake Middleware<br/>(Fail-Closed 門控)"]
    I --> A["對話 Agent Router<br/>(意圖理解)"]
    A --> T["確定性 Python 工具集<br/>(版本化規則引擎)"]
    T --> D["試算報告草稿<br/>(Draft Report)"]
    D --> H{"人工核准 (HITL)"}
    H -->|核准| R["逐字鎖定之最終報告"]
    H -->|駁回| X["拒絕發布與退回"]
    S[("版本法規快照 DB<br/>CURRENT_2026_07")] --> T

    style H fill:#fff9db,stroke:#f59f00,stroke-width:2px
    style T fill:#e7f5ff,stroke:#1971c2,stroke-width:2px
```

### 2. 確定性計算與 HITL 人工審核時序 (Sequence Diagram)

```mermaid
%%{init: {'themeVariables': {'fontSize': '20px'}}}%%
sequenceDiagram
    autonumber
    actor User as 使用者 / 家屬
    participant PII as PII Filter & Middleware
    participant Agent as Agent Router
    participant Engine as Python 法規引擎<br/>(確定性計算)
    actor HITL as 人工專家 (HITL)

    User->>PII: 輸入長照試算對話
    Note over PII: 全文 PII 脫敏遮蔽<br/>確認 CMS 級別完備性
    PII->>Agent: 傳送清洗後 Prompt
    Agent->>Engine: 調用計算工具 (CMS 級別, 身分, 服務)
    Engine-->>Agent: 回傳精確金額 (給付 NT$15,120, 自付 NT$2,880)
    Agent->>HITL: 提交試算報告草稿 (Draft Report)

    alt 人工審核通過
        HITL-->>User: 核准並簽章發布逐字鎖定報告
    else 資訊不足或駁回
        HITL-->>User: 駁回草稿並要求補齊資料
    end
```

---

## 模型選型與橫向評測

專案針對地端與雲端模型進行 20 題端到端固定診斷集評測（涵蓋年齡邊界、失智、PAC、住宿排除、未知 CMS、福利類別、外籍看護、超額支出與 PII 提示注入）：

| 評測模型 / 模式 | 定位說明 | 初始端到端 | 強化後成功率 | 金額題準確度 | PII 洩漏筆數 |
|---|---|---:|---:|---:|---:|
| **3B 台灣地端模型** | 輕量化、繁體中文在地化 | 0 / 20 | **20 / 20** | **13 / 13** | **0 筆** |
| **12B 地端基準 Adapter** | 跨模型能力對照基準 | 3 / 20 | **20 / 20** | **13 / 13** | **0 筆** |
| **雲端歷史基線** | 商業 API 對照組 | 7 / 20 | 基線未重跑 | 12 / 13 | 0 筆 |

*註：586 項單元與整合測試全數通過，詳細評測細目請參閱 [eval/results/local-models-v3.json](eval/results/local-models-v3.json)。表中 PII 數字只代表固定診斷集，不代表公開環境的零風險保證。*

---

## 法規快照與計算規則

系統內建版本化長照法規快照（預設為 `CURRENT_2026_07`，保留 `LEGACY_2022` 供歷史比對）：

| 版本 | 快照日期 |
|---|---:|
| `LEGACY_2022` | 2022-02-01 |
| `CURRENT_2026_07` | 2026-07-01 完整快照 |

| CMS 級別 | 2 級 | 3 級 | 4 級 | 5 級 | 6 級 | 7 級 | 8 級 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| **照顧與專業服務月額 (NT$)** | 10,020 | 15,460 | 18,580 | 24,100 | 28,070 | 32,090 | 36,180 |

- **部分負擔比率**：一般戶 16%、中低收入戶 5%、低收入戶 0%。
- **外籍看護扣減**：聘有外籍家庭看護者，照顧與專業服務額度按 30% 計算。
- **代表案例**：CMS 4 級、一般戶 (16%)、無外籍看護、當月服務費 NT$18,000 → **政府給付 NT$15,120，自付 NT$2,880**。

> 機器可核對原句（與 `rule_audit` 一致性稽核逐字綁定，上方表格為其排版呈現）：
> CMS 2–8 的照顧及專業服務月額為 10,020、15,460、18,580、24,100、28,070、32,090、36,180 元。
> 部分負擔比率為第一類 0%、第二類 5%、第三類 16%。

### 官方來源與授權

- [歷史條文](https://law.moj.gov.tw/LawClass/LawOldVer.aspx?lnndate=20220120&lser=001&pcode=L0070059)
- [現行條文與附件](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0070059)
- [附表二：給付額度](https://law.moj.gov.tw/LawClass/LawGetFile.ashx?FileId=0000398330&lan=C)
- [附表五：部分負擔比率](https://law.moj.gov.tw/LawClass/LawGetFile.ashx?FileId=0000398333&lan=C)
- [1966 申請流程](https://1966.gov.tw/ltc/cp-6533-70777-207.html)

---

## 快速開始

需求：Python 3.11+、`uv`。

### 1. 安裝依賴與執行測試 (586 passed)

```powershell
uv sync --locked
uv run pytest -q
```

### 2. 啟動互動介面

```powershell
# 執行 Offline 驗證 Demo
uv run ltc-benefit-agent --offline-demo --approve

# 啟動 Web UI (開啟 http://127.0.0.1:7860)
uv run ltc-benefit-ui
```

---

## 授權與聲明

本專案採 [MIT License](LICENSE)。僅供初步試算與研究用途，非正式資格核定。
