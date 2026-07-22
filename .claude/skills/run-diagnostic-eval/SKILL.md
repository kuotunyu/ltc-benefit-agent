---
name: run-diagnostic-eval
description: Safely run or resume ltc-benefit-agent's fixed trace evaluation, inspect model failures, and record evidence. Use for one-case smoke tests, the 20-case local suite, comparing providers, checking PII/HITL/tool metrics, or preparing a gated cloud evaluation.
---

# Run Diagnostic Eval

## Workflow

1. Read `PROGRESS.md`, the Phase 3 section of `PLAN.md`, and `eval/scenarios.json`. Treat existing `artifacts/eval/*.json` as evidence, not source truth.
2. Before local inference, check `nvidia-smi`, free disk, running Python/model-service processes, and `ollama list`. Never stop an existing process.
3. Start with one scenario:

```powershell
uv run python -m ltc_benefit_agent.evaluation --provider gemma3_baseline --scenario S14_THIRD_CATEGORY --output artifacts\eval\smoke.json
```

4. Run all 20 only after the smoke finishes. Keep output under ignored `artifacts/eval/`.
5. Read both `metrics` and per-case `results`/`traces`. Preserve failures; do not adjust expectations to improve scores. Confirm money against tool results, never model prose.

## Provider gates

- For F1, first confirm `ltc-f1:q4_k_m` exists. If absent, run `scripts/prepare_f1_ollama.py` without flags for check-only. Do not pass `--execute --accepted-license` unless the author has accepted the gated license and explicitly authorized the download.
- For cloud mode, run `scripts/estimate_cloud_cost.py`, show assumptions and the USD cap, then wait for explicit approval. Without approval, do not use `--allow-cloud`.
- The 12B baseline uses the explicit compatibility template in `deploy/ollama/`; label its scores as adapter results, not native tool-calling results.

## Handoff

Run the relevant pytest files and `uv lock --check`. Use the project `update-progress` skill to record exact commands, counts, model string, cost, failures, and remaining gates. Never run Git; provide only a suggested Conventional Commit message.
