"""Explicit command-line entry point for rule-source audits and review reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .checker import audit_online
from .consistency import ConsistencyStatus, check_project_consistency
from .manifest import load_manifest
from .models import RuleAuditStatus
from .review import load_audit_evidence, render_review_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read approved official sources, compare deterministic semantics, and "
            "write evidence only. Business rules are never modified."
        )
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--source", action="append", dest="source_ids")
    parser.add_argument(
        "--input",
        type=Path,
        help="Read an existing P1 JSON artifact instead of contacting official sources.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--review-output",
        type=Path,
        help="Write a deterministic zh-TW Markdown report for human review.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root used by cross-file consistency checks.",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.input is not None and args.source_ids:
        parser.error("--input cannot be combined with --source")
    manifest_set = load_manifest(args.manifest)
    if args.input is not None:
        manifest_version, results = load_audit_evidence(args.input)
        if manifest_version != manifest_set.manifest_version:
            raise SystemExit(
                "Audit evidence manifest_version does not match the loaded manifest"
            )
    else:
        requested = set(args.source_ids or ())
        if requested:
            unknown = requested - {
                source.source_id for source in manifest_set.sources
            }
            if unknown:
                raise SystemExit(f"Unknown source_id: {', '.join(sorted(unknown))}")
        sources = tuple(
            source
            for source in manifest_set.sources
            if not requested or source.source_id in requested
        )
        results = tuple(
            audit_online(source, timeout_seconds=args.timeout) for source in sources
        )
    payload = {
        "schema_version": "1",
        "manifest_version": manifest_set.manifest_version,
        "writes_performed": False,
        "results": [result.to_dict() for result in results],
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    consistency = None
    if args.review_output is not None:
        consistency = check_project_consistency(args.project_root, manifest_set)
        report = render_review_report(
            results,
            consistency,
            manifest_version=manifest_set.manifest_version,
        )
        args.review_output.parent.mkdir(parents=True, exist_ok=True)
        args.review_output.write_text(report, encoding="utf-8")
    print(encoded, end="")
    for result in results:
        print(f"{result.source_id}: {result.status.value}")
    if args.review_output is not None and consistency is not None:
        print(f"review_report: {args.review_output}")
        print(f"project_consistency: {consistency.status.value}")
    if any(result.status is RuleAuditStatus.CHECK_UNAVAILABLE for result in results):
        return 3
    if any(
        result.status is RuleAuditStatus.REVIEW_REQUIRED for result in results
    ) or (
        consistency is not None
        and consistency.status is ConsistencyStatus.DRIFT_DETECTED
    ):
        return 2
    return 0
