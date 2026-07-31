#!/usr/bin/env python3
"""Redact high-confidence credentials from workspace text artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

import workspace_health_check


REPLACEMENTS = {
    "Basic Authorization": "{{Authorization}}",
    "Bearer token": "Bearer {{ACCESS_TOKEN}}",
    "JWT": "{{JWT_TOKEN}}",
    "known leaked Basic credential": "{{BASIC_AUTH_REDACTED}}",
    "known leaked Basic credential tail": "{{BASIC_AUTH_REDACTED}}",
}


def candidate_files(root: Path):
    for root_name in workspace_health_check.SECRET_SCAN_ROOTS:
        base = root / root_name
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            relative_parts = path.relative_to(base).parts
            if (
                path.is_file()
                and not any(part.startswith(".") for part in relative_parts)
                and "__pycache__" not in relative_parts
                and path.suffix.lower()
                in workspace_health_check.SECRET_SCAN_SUFFIXES
            ):
                yield path


def redact_text(text: str) -> tuple[str, int]:
    count = 0
    result = text
    for label, pattern in workspace_health_check.SECRET_PATTERNS:
        replacement = REPLACEMENTS.get(label)
        if replacement is None:
            continue
        result, replacements = pattern.subn(replacement, result)
        count += replacements
    return result, count


def run(root: Path, apply: bool) -> tuple[int, int]:
    changed_files = 0
    redactions = 0
    for path in candidate_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        redacted, count = redact_text(text)
        if not count:
            continue
        changed_files += 1
        redactions += count
        print(f"{path.relative_to(root)}: {count}")
        if apply:
            path.write_text(redacted, encoding="utf-8")
    return changed_files, redactions


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check or redact high-confidence workspace credentials"
    )
    parser.add_argument(
        "--workspace",
        default=str(workspace_health_check.WORKSPACE),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write redacted placeholders; default is check-only",
    )
    args = parser.parse_args()
    changed_files, redactions = run(Path(args.workspace).resolve(), args.apply)
    action = "redacted" if args.apply else "found"
    print(f"{action}: files={changed_files} matches={redactions}")
    if args.apply:
        return 0
    return 1 if redactions else 0


if __name__ == "__main__":
    raise SystemExit(main())
