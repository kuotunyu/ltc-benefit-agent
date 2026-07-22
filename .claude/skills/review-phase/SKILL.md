---
name: review-phase
description: 在 ltc-benefit-agent 每個 Phase 收尾時核對 PLAN DoD、測試證據、文件同步、安全與公開文案，產生清楚的通過／未通過報告和作者 Git 建議。任何 Phase 驗收、交付檢查或準備進入下一階段時使用。
---

# 檢查 Phase Gate

## 流程

1. 讀取 PLAN 當前 Phase 的交付項、DoD、成本閘門與風險，不自行擴大驗收範圍。
2. 逐項執行安全且與當前 Phase 相稱的驗證；保留命令、退出碼與關鍵輸出。
3. 遇到付費 API、模型下載／轉檔、長時間 GPU 工作、部署或帳號操作時停止，先列成本與影響並取得作者明確確認。
4. 確認 README／PLAN／PROGRESS／CLAUDE／`.env.example` 中當前 Phase 應同步的內容；不存在或尚未到該 Phase 的檔案標記不適用。
5. 若本 Phase 修改外部套件 API，確認已依 `verify-external-api` 留下 Context7 library ID、來源、鎖定版本與測試證據；fallback 必須明示。
6. 檢查公開產物不含 `.env` 真值、個資、內部禁詞、絕對私密路徑、未驗證數字或不實完成聲明。
7. 使用 `update-progress` 的格式記錄驗證結果；Phase 只有在所有必要 DoD 通過且作者確認後才標成完成。
8. 回報結果並停在 Phase gate，不自動開始下一 Phase。

## 特殊邊界

- 不執行任何 Git 指令；只提供建議 Conventional Commit 訊息與 `phase-N` tag。
- 不停止其他程序、不覆蓋既有 port、不讀 `.env`；需要資源時只做唯讀盤點。
- 失敗即報失敗與最小修正路徑，不為了讓 checklist 變綠而降低標準。
- 測試未執行、外部資源未驗證或作者尚未核准時，不使用「完成」。

## 驗收回報

- 結論：通過／未通過／工程完成待作者確認。
- DoD：逐項狀態與證據。
- 成本與資源：實際值；沒有就寫 $0。
- 殘留風險與待作者處理。
- 建議 commit 訊息與 tag；明示未由 Agent 執行。
