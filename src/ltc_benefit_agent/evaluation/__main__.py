from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ltc_benefit_agent.agent.config import AgentProvider

from .runner import run_suite


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="執行固定 20 題 trace 診斷集")
    parser.add_argument(
        "--provider",
        required=True,
        choices=[item.value for item in AgentProvider],
    )
    parser.add_argument("--scenario", action="append", dest="scenarios")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-cloud",
        action="store_true",
        help="僅在已取得成本確認後使用；沒有此旗標時雲端模式拒絕執行",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_suite(
        provider=AgentProvider(args.provider),
        output_path=args.output,
        scenario_ids=set(args.scenarios) if args.scenarios else None,
        allow_cloud=args.allow_cloud,
    )
    print(json.dumps(payload["metrics"], ensure_ascii=False, indent=2))
    print(f"完整 trace：{args.output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
