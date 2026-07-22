---
name: update-progress
description: 依實際驗證證據更新 ltc-benefit-agent 的 PROGRESS.md 快速回憶區與 append-only Phase 日誌，並在重大決策改變時同步 PLAN Decision Log。每次收工、Phase 收尾或做出影響後續的決策時使用。
---

# 更新專案進度

## 更新前

1. 讀取 PLAN 當前 Phase 的交付項與 DoD。
2. 蒐集本 session 實際執行的命令、關鍵輸出、檔案與成本；沒跑的項目標記「未驗證」。
3. 清除證據中的 API key、`.env` 真值、個資、絕對私密路徑與不必要的終端雜訊。

## 更新 PROGRESS

1. 重寫頂部快速回憶區，維持 30 行內，固定包含：
   - 上次收工日期
   - 現在做到哪
   - 下一步（第一項必須可直接執行）
   - 未決問題
   - 待使用者人工處理
   - 已知坑
2. 在對應 Phase 小節追加日期條目，不刪除舊紀錄；記錄：
   - 完成內容
   - 實跑證據與關鍵數字
   - 決策變更及 PLAN Decision Log 編號
   - API／模型實際成本
   - 待作者進行的 Git 操作
3. 若改變架構、規則版本、外部資源或驗收標準，在 PLAN 新增 Decision Log 條目，不覆寫舊決策。
4. Phase 尚未經作者確認時，不標成完成；寫「工程完成，待驗收」或實際狀態。

## Git 邊界

- 不執行任何 Git 指令，也不讀 Git 狀態或歷史。
- 可在回報中提供一個建議 Conventional Commit 訊息與 Phase tag，由作者自行判斷與執行。
- 作者尚未提供 commit hash 時，PROGRESS 寫「待作者回填」，不得猜測。

## 完成檢查

- 快速回憶區與 Phase 日誌同時更新。
- 每一個「通過」都有本次或既有明確證據。
- 決策與 PLAN 一致，成本未漏記，沒有秘密或個資。

