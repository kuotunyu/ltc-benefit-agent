"""從 ignored raw artifacts 產生可提交的去識別化評估摘要。"""

from __future__ import annotations

import argparse
from pathlib import Path

from ltc_benefit_agent.evaluation.public_export import (
    write_public_evaluation_summary,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACTS = (
    ROOT / "artifacts" / "eval" / "f1-20-intake-final-v3.json",
    ROOT / "artifacts" / "eval" / "gemma3-20-intake-final-v3.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export deterministic scores without raw conversation or PII."
    )
    parser.add_argument(
        "--scenario-file",
        type=Path,
        default=ROOT / "eval" / "scenarios.json",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        type=Path,
        dest="artifacts",
        help="Raw artifact path; repeat for multiple runs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "eval" / "results" / "local-models-v3.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifacts = tuple(args.artifacts or DEFAULT_ARTIFACTS)
    summary = write_public_evaluation_summary(
        args.scenario_file,
        artifacts,
        args.output,
    )
    print(f"PUBLIC_EVAL_OK runs={len(summary['runs'])} output={args.output}")


if __name__ == "__main__":
    main()
