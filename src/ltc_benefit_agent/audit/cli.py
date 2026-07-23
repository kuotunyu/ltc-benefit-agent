"""Explicit command-line entry point for rule-source audits and review reports."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Sequence

from .checker import audit_online
from .consistency import ConsistencyStatus, check_project_consistency
from .manifest import default_manifest_path, load_manifest
from .models import RuleAuditStatus
from .public_summary import (
    build_public_audit_summary,
    default_approved_status_path,
)
from .review import load_audit_evidence, render_review_report


_PROTECTED_OUTPUT_SUFFIXES = (
    (".env",),
    ("src", "ltc_benefit_agent", "tools", "rules.py"),
    ("src", "ltc_benefit_agent", "tools", "eligibility.py"),
    ("src", "ltc_benefit_agent", "tools", "copay.py"),
    (
        "src",
        "ltc_benefit_agent",
        "audit",
        "data",
        "rule-sources-v1.json",
    ),
    (
        "src",
        "ltc_benefit_agent",
        "audit",
        "data",
        "approved-audit-status-v1.json",
    ),
)


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve()


def _path_key(path: Path) -> str:
    """Return a platform-normalized key for paths that may not exist yet."""

    return os.path.normcase(os.fspath(path))


def _same_existing_file(left: Path, right: Path) -> bool:
    """Compare existing file identities so hard links cannot bypass guards."""

    try:
        return left.exists() and right.exists() and left.samefile(right)
    except OSError:
        return False


def _matches_protected_suffix(path: Path) -> bool:
    normalized_parts = tuple(part.casefold() for part in path.parts)
    return any(
        normalized_parts[-len(suffix) :]
        == tuple(part.casefold() for part in suffix)
        for suffix in _PROTECTED_OUTPUT_SUFFIXES
    )


def _validate_output_paths(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> None:
    outputs = {
        flag: _resolved(path)
        for flag, path in (
            ("--output", args.output),
            ("--public-output", args.public_output),
            ("--review-output", args.review_output),
        )
        if path is not None
    }
    output_paths = tuple(outputs.values())
    if (
        len({_path_key(path) for path in output_paths}) != len(output_paths)
        or any(
            _same_existing_file(left, right)
            for index, left in enumerate(output_paths)
            for right in output_paths[index + 1 :]
        )
    ):
        parser.error(
            "--output, --public-output, and --review-output must use distinct paths"
        )

    protected_paths = (
        _resolved(default_manifest_path()),
        _resolved(default_approved_status_path()),
    )
    if args.manifest is not None:
        protected_paths += (_resolved(args.manifest),)
    if args.input is not None:
        protected_paths += (_resolved(args.input),)
    protected_path_keys = {_path_key(path) for path in protected_paths}

    for flag, output_path in outputs.items():
        if (
            _path_key(output_path) in protected_path_keys
            or any(
                _same_existing_file(output_path, protected_path)
                for protected_path in protected_paths
            )
            or _matches_protected_suffix(output_path)
        ):
            parser.error(
                f"{flag} cannot overwrite audit input, manifest, approved status, "
                ".env, or business rule files"
            )


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
        "--public-output",
        type=Path,
        help="Write a minimized whitelist-only JSON summary safe for CI artifacts.",
    )
    parser.add_argument(
        "--review-output",
        type=Path,
        help="Write a deterministic zh-TW Markdown report for human review.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help=(
            "Do not print the full private evidence JSON to stdout. "
            "Source IDs, statuses, and output locations remain visible."
        ),
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
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be a finite number greater than zero")
    if args.input is not None and args.source_ids:
        parser.error("--input cannot be combined with --source")
    if args.public_output is not None and args.input is not None:
        parser.error(
            "--public-output cannot be combined with --input; "
            "public summaries require a fresh full manifest audit"
        )
    if args.public_output is not None and args.source_ids:
        parser.error(
            "--public-output cannot be combined with --source; "
            "public summaries require a full manifest audit"
        )
    _validate_output_paths(parser, args)
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
    if args.public_output is not None:
        public_payload = build_public_audit_summary(
            results,
            manifest_version=manifest_set.manifest_version,
            expected_source_ids=tuple(
                source.source_id for source in manifest_set.sources
            ),
        )
        args.public_output.parent.mkdir(parents=True, exist_ok=True)
        args.public_output.write_text(
            json.dumps(public_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
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
    if not args.quiet:
        print(encoded, end="")
    for result in results:
        print(f"{result.source_id}: {result.status.value}")
    if args.review_output is not None and consistency is not None:
        print(f"review_report: {args.review_output}")
        print(f"project_consistency: {consistency.status.value}")
    if args.public_output is not None:
        print(f"public_summary: {args.public_output}")
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
