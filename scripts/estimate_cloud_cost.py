"""以明示單價與 token 上限估算雲端診斷的最壞成本，不呼叫 API。"""

from __future__ import annotations

import argparse
from decimal import Decimal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="估算文字模型呼叫成本上限")
    parser.add_argument("--scenarios", type=int, default=20)
    parser.add_argument("--calls-per-scenario", type=int, required=True)
    parser.add_argument("--input-tokens-per-call", type=int, required=True)
    parser.add_argument("--output-tokens-per-call", type=int, required=True)
    parser.add_argument("--input-usd-per-million", type=Decimal, required=True)
    parser.add_argument("--output-usd-per-million", type=Decimal, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if min(
        args.scenarios,
        args.calls_per_scenario,
        args.input_tokens_per_call,
        args.output_tokens_per_call,
    ) < 0:
        raise ValueError("數量與 token 上限不得為負數")
    calls = args.scenarios * args.calls_per_scenario
    input_tokens = calls * args.input_tokens_per_call
    output_tokens = calls * args.output_tokens_per_call
    million = Decimal(1_000_000)
    input_cost = Decimal(input_tokens) / million * args.input_usd_per_million
    output_cost = Decimal(output_tokens) / million * args.output_usd_per_million
    total = input_cost + output_cost
    print(f"calls={calls}")
    print(f"input_tokens_cap={input_tokens}")
    print(f"output_tokens_cap={output_tokens}")
    print(f"input_cost_cap_usd={input_cost:.6f}")
    print(f"output_cost_cap_usd={output_cost:.6f}")
    print(f"total_cost_cap_usd={total:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
