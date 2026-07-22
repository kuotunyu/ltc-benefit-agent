"""合併 partial evaluation JSON，輸出固定 20 題的單一可稽核 artifact。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ltc_benefit_agent.evaluation.merge import merge_evaluation_artifacts
from ltc_benefit_agent.evaluation.scenarios import load_scenarios


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = merge_evaluation_artifacts(
        args.input,
        output_path=args.output,
        expected_scenario_ids=[item.scenario_id for item in load_scenarios()],
    )
    print(json.dumps(payload["metrics"], ensure_ascii=False, indent=2))
    print(f"合併 artifact：{args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
