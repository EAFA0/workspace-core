#!/usr/bin/env python3
"""Check and move workspace Markdown documents without introducing a new link syntax."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote

import index_consistency


WORKSPACE = Path(__file__).resolve().parents[3]
LINK_RE = re.compile(r"(?<!!)\[([^\]\n]+)\]\(([^)\n]+)\)")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
WORKSPACE_PREFIXES = ("docs/", "skills/", "biz-tests/", "memory/")


@dataclass(frozen=True)
class InlineCode:
    start: int
    end: int
    value: str


@dataclass(frozen=True)
class MarkdownLink:
    source: str
    line: int
    label: str
    destination: str
    start: int
    end: int


@dataclass(frozen=True)
class RefIssue:
    level: str
    kind: str
    source: str
    line: int
    target: str
    message: str


@dataclass(frozen=True)
class Rewrite:
    source: str
    future_source: str
    markdown_links: int
    inline_paths: int


def workspace_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def markdown_files(root: Path) -> list[Path]:
    files: set[Path] = set()
    for directory in (root / "docs", root / "skills", root / "biz-tests"):
        if not directory.exists():
            continue
        for path in directory.rglob("*.md"):
            if path.is_file() and ".git" not in path.parts:
                files.add(path)
    for relative in (
        "AGENTS.md",
        "SOUL.md",
        "USER.md",
        "memory/MEMORY.md",
    ):
        path = root / relative
        if path.is_file():
            files.add(path)
    return sorted(files)


def is_frozen(path: Path, root: Path) -> bool:
    relative = workspace_relative(path, root)
    if relative.startswith("docs/prd/"):
        return True
    return False


def protected_markdown(text: str) -> tuple[str, list[InlineCode]]:
    masked = list(text)
    inline_codes: list[InlineCode] = []
    offset = 0
    fence_character: str | None = None
    fence_length = 0

    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        fence_match = re.match(r"(`{3,}|~{3,})", stripped)
        if fence_character is not None:
            for index in range(offset, offset + len(line)):
                if masked[index] != "\n":
                    masked[index] = " "
            if (
                fence_match
                and fence_match.group(1)[0] == fence_character
                and len(fence_match.group(1)) >= fence_length
            ):
                fence_character = None
                fence_length = 0
            offset += len(line)
            continue

        if fence_match:
            fence_character = fence_match.group(1)[0]
            fence_length = len(fence_match.group(1))
            for index in range(offset, offset + len(line)):
                if masked[index] != "\n":
                    masked[index] = " "
            offset += len(line)
            continue

        line_without_newline = line.rstrip("\r\n")
        for match in re.finditer(r"(`+)(.+?)\1", line_without_newline):
            content_start = offset + match.start(2)
            content_end = offset + match.end(2)
            inline_codes.append(
                InlineCode(content_start, content_end, match.group(2))
            )
            for index in range(offset + match.start(), offset + match.end()):
                masked[index] = " "
        offset += len(line)

    return "".join(masked), inline_codes


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def parse_markdown_links(source: Path, text: str, root: Path) -> list[MarkdownLink]:
    masked, _ = protected_markdown(text)
    links = []
    for match in LINK_RE.finditer(masked):
        destination = text[match.start(2):match.end(2)].strip()
        links.append(
            MarkdownLink(
                source=workspace_relative(source, root),
                line=line_number(text, match.start()),
                label=text[match.start(1):match.end(1)],
                destination=destination,
                start=match.start(2),
                end=match.end(2),
            )
        )
    return links


def split_destination(destination: str) -> tuple[str, str] | None:
    value = destination.strip()
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1]
    if not value or SCHEME_RE.match(value) or value.startswith("//"):
        return None
    if any(character in value for character in ("{", "}", "*", "$")):
        return None
    if re.search(r"\s", value):
        return None
    path_part, separator, fragment = value.partition("#")
    return path_part, f"#{fragment}" if separator else ""


def resolve_local_target(source: Path, path_part: str, root: Path) -> Path:
    decoded = unquote(path_part)
    if not decoded:
        return source.resolve()
    if decoded.startswith("~"):
        return Path(decoded).expanduser().resolve()
    candidate = Path(decoded)
    if candidate.is_absolute():
        return candidate.resolve()
    return (source.parent / candidate).resolve()


def is_inside(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def should_check_target(source: Path, target: Path, root: Path) -> bool:
    """活动 docs 全查；其他入口只查指向 docs 的入链。"""
    docs_root = root / "docs"
    return is_inside(source, docs_root) or is_inside(target, docs_root)


def check_references(
    root: Path = WORKSPACE, include_frozen: bool = False
) -> list[RefIssue]:
    issues: list[RefIssue] = []
    for source in markdown_files(root):
        frozen = is_frozen(source, root)
        if frozen and not include_frozen:
            continue
        try:
            text = source.read_text(encoding="utf-8")
        except OSError as error:
            issues.append(
                RefIssue(
                    "error",
                    "read_failed",
                    workspace_relative(source, root),
                    0,
                    "",
                    str(error),
                )
            )
            continue
        for link in parse_markdown_links(source, text, root):
            parts = split_destination(link.destination)
            if parts is None:
                continue
            path_part, _fragment = parts
            target = resolve_local_target(source, path_part, root)
            if not should_check_target(source, target, root):
                continue
            level = "warning" if frozen else "error"
            if not target.exists():
                issues.append(
                    RefIssue(
                        level,
                        "missing_target",
                        link.source,
                        link.line,
                        link.destination,
                        "本地 Markdown 链接目标不存在",
                    )
                )
        _, inline_codes = protected_markdown(text)
        for inline_code in inline_codes:
            parsed = inline_path_target(source, inline_code.value, root)
            if parsed is None:
                continue
            target, _ = parsed
            if not should_check_target(source, target, root):
                continue
            if not target.exists():
                issues.append(
                    RefIssue(
                        "warning",
                        "missing_inline_path",
                        workspace_relative(source, root),
                        line_number(text, inline_code.start),
                        inline_code.value,
                        "行内代码中的文档路径不存在",
                    )
                )

    for target in index_consistency.INDEX_TARGETS:
        if not (root / target.index).exists():
            continue
        result = index_consistency.check_target(target, root)
        if result.get("status"):
            issues.append(
                RefIssue(
                    "error",
                    "index_unavailable",
                    target.index,
                    0,
                    target.key,
                    result["status"],
                )
            )
            continue
        if not result["ok"]:
            message = (
                f"索引有磁盘无={result['indexed_not_on_disk']}；"
                f"磁盘有索引无={result['on_disk_not_indexed']}"
            )
            issues.append(
                RefIssue(
                    "error",
                    "index_inconsistent",
                    target.index,
                    0,
                    target.key,
                    message,
                )
            )
    return issues


def future_path(path: Path, source: Path, destination: Path) -> Path:
    resolved = path.resolve()
    source_resolved = source.resolve()
    if resolved == source_resolved:
        return destination.resolve()
    try:
        relative = resolved.relative_to(source_resolved)
    except ValueError:
        return resolved
    return (destination / relative).resolve()


def encoded_relative_path(source: Path, target: Path, original: str) -> str:
    relative = os.path.relpath(target, source.parent).replace(os.sep, "/")
    if original.startswith("./") and not relative.startswith((".", "/")):
        relative = f"./{relative}"
    if original.endswith("/") and not relative.endswith("/"):
        relative += "/"
    return quote(relative, safe="/-._~")


def inline_path_target(source: Path, value: str, root: Path) -> tuple[Path, str] | None:
    path_part, separator, fragment = value.partition("#")
    if not path_part.endswith(".md"):
        return None
    if any(character in path_part for character in ("<", ">", "*", "{", "}", "$")):
        return None
    if path_part.startswith(WORKSPACE_PREFIXES):
        target = (root / unquote(path_part)).resolve()
        style = "workspace"
    elif path_part.startswith(("./", "../")):
        target = (source.parent / unquote(path_part)).resolve()
        style = "relative"
    elif Path(path_part).is_absolute():
        target = Path(unquote(path_part)).resolve()
        style = "absolute"
    else:
        return None
    suffix = f"#{fragment}" if separator else ""
    return target, f"{style}{suffix}"


def rewrite_markdown(
    source: Path,
    text: str,
    move_source: Path,
    move_destination: Path,
    root: Path,
) -> tuple[str, int, int]:
    future_source = future_path(source, move_source, move_destination)
    replacements: list[tuple[int, int, str]] = []
    markdown_count = 0
    inline_count = 0

    for link in parse_markdown_links(source, text, root):
        parts = split_destination(link.destination)
        if parts is None:
            continue
        path_part, fragment = parts
        if not path_part:
            continue
        target = resolve_local_target(source, path_part, root)
        future_target = future_path(target, move_source, move_destination)
        if future_source == source.resolve() and future_target == target:
            continue
        new_path = encoded_relative_path(future_source, future_target, path_part)
        replacements.append((link.start, link.end, f"{new_path}{fragment}"))
        markdown_count += 1

    _, inline_codes = protected_markdown(text)
    for inline_code in inline_codes:
        parsed = inline_path_target(source, inline_code.value, root)
        if parsed is None:
            continue
        target, style_with_fragment = parsed
        style, _, fragment = style_with_fragment.partition("#")
        future_target = future_path(target, move_source, move_destination)
        if future_source == source.resolve() and future_target == target:
            continue
        if style == "workspace":
            new_path = workspace_relative(future_target, root)
        elif style == "absolute":
            new_path = str(future_target)
        else:
            new_path = encoded_relative_path(
                future_source, future_target, inline_code.value
            )
        if fragment:
            new_path = f"{new_path}#{fragment}"
        replacements.append((inline_code.start, inline_code.end, new_path))
        inline_count += 1

    rewritten = text
    for start, end, replacement in sorted(replacements, reverse=True):
        rewritten = f"{rewritten[:start]}{replacement}{rewritten[end:]}"
    return rewritten, markdown_count, inline_count


def validate_move_paths(
    source: Path, destination: Path, root: Path
) -> tuple[Path, Path, Path]:
    source = source.resolve()
    destination = destination.resolve()
    root = root.resolve()
    source.relative_to(root)
    destination.relative_to(root)
    if not source.exists():
        raise ValueError(f"源路径不存在: {source}")
    if destination.exists():
        raise ValueError(f"目标路径已存在: {destination}")
    if is_frozen(source, root):
        raise ValueError("冻结历史或 PRD 不允许通过 refs move 修改")
    if source.is_file() and source.suffix != ".md":
        raise ValueError("首版 refs move 只移动 Markdown 文件或包含 Markdown 的目录")
    source_repo = git_root(source)
    destination_repo = git_root(destination.parent)
    if source_repo != destination_repo:
        raise ValueError("源和目标必须位于同一 Git 仓库")
    return source, destination, source_repo


def git_root(path: Path) -> Path:
    while not path.exists() and path != path.parent:
        path = path.parent
    if path.is_file():
        path = path.parent
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def build_rewrite_plan(
    source: Path, destination: Path, root: Path
) -> tuple[dict[Path, tuple[Path, str]], list[Rewrite]]:
    rewritten_files: dict[Path, tuple[Path, str]] = {}
    summary: list[Rewrite] = []
    for markdown_file in markdown_files(root):
        if is_frozen(markdown_file, root):
            continue
        text = markdown_file.read_text(encoding="utf-8")
        rewritten, markdown_count, inline_count = rewrite_markdown(
            markdown_file, text, source, destination, root
        )
        future_source = future_path(markdown_file, source, destination)
        if rewritten != text or future_source != markdown_file.resolve():
            rewritten_files[markdown_file.resolve()] = (future_source, rewritten)
            summary.append(
                Rewrite(
                    workspace_relative(markdown_file, root),
                    workspace_relative(future_source, root),
                    markdown_count,
                    inline_count,
                )
            )
    return rewritten_files, summary


def create_backup(
    source: Path,
    destination: Path,
    rewrites: dict[Path, tuple[Path, str]],
    root: Path,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = Path(
        tempfile.mkdtemp(prefix=f"spec-refs-move-{timestamp}-", dir="/tmp")
    )
    files_root = backup / "files"
    original_files = set(rewrites)
    if source.is_file():
        original_files.add(source)
    else:
        original_files.update(path for path in source.rglob("*") if path.is_file())
    for path in sorted(original_files):
        relative = path.resolve().relative_to(root.resolve())
        backup_path = files_root / relative
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)
    manifest = {
        "workspace": str(root),
        "source": workspace_relative(source, root),
        "destination": workspace_relative(destination, root),
        "files": [workspace_relative(path, root) for path in sorted(original_files)],
    }
    (backup / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return backup


def run_git_move(source: Path, destination: Path, repository: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "mv",
            "--",
            str(source.relative_to(repository)),
            str(destination.relative_to(repository)),
        ],
        check=True,
    )


def remove_empty_parents(path: Path, stop: Path) -> None:
    current = path.resolve()
    stop = stop.resolve()
    while current != stop and is_inside(current, stop):
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def git_diff_check(paths: set[Path]) -> None:
    repositories = {git_root(path if path.is_dir() else path.parent) for path in paths}
    for repository in sorted(repositories):
        subprocess.run(
            ["git", "-C", str(repository), "diff", "--check"],
            check=True,
        )


def restore_backup(
    backup: Path,
    source: Path,
    destination: Path,
    repository: Path,
    root: Path,
) -> None:
    if destination.exists() and not source.exists():
        run_git_move(destination, source, repository)
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    for relative in manifest["files"]:
        backup_path = backup / "files" / relative
        original_path = root / relative
        original_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, original_path)


def apply_move(
    source: Path,
    destination: Path,
    repository: Path,
    rewrites: dict[Path, tuple[Path, str]],
    root: Path,
) -> Path:
    backup = create_backup(source, destination, rewrites, root)
    baseline_errors = [
        issue for issue in check_references(root) if issue.level == "error"
    ]
    baseline_keys = {issue_key(issue) for issue in baseline_errors}
    try:
        run_git_move(source, destination, repository)
        remove_empty_parents(source.parent, repository)
        touched_paths: set[Path] = {destination}
        for original_source, (future_source, rewritten) in rewrites.items():
            target = future_source if original_source == source or source in original_source.parents else original_source
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rewritten, encoding="utf-8")
            touched_paths.add(target)
        issues = check_references(root)
        errors = [issue for issue in issues if issue.level == "error"]
        new_errors = [
            issue for issue in errors if issue_key(issue) not in baseline_keys
        ]
        if new_errors:
            rendered = "; ".join(
                f"{issue.source}:{issue.line} {issue.message} {issue.target}"
                for issue in new_errors[:10]
            )
            raise RuntimeError(f"移动新增引用错误: {rendered}")
        git_diff_check(touched_paths)
    except Exception:
        restore_backup(backup, source, destination, repository, root)
        raise
    return backup


def issue_key(issue: RefIssue) -> tuple[str, ...]:
    if issue.kind in {"index_inconsistent", "index_unavailable"}:
        return issue.kind, issue.source, issue.target
    return issue.kind, issue.source, str(issue.line), issue.target, issue.message


def render_issues(issues: list[RefIssue], as_json: bool) -> int:
    if as_json:
        print(json.dumps([asdict(issue) for issue in issues], ensure_ascii=False, indent=2))
    else:
        if not issues:
            print("refs check: OK")
        for issue in issues:
            location = f"{issue.source}:{issue.line}" if issue.line else issue.source
            print(
                f"[{issue.level.upper()}] {location} "
                f"{issue.kind}: {issue.message} ({issue.target})"
            )
    return 1 if any(issue.level == "error" for issue in issues) else 0


def command_check(args: argparse.Namespace) -> int:
    return render_issues(
        check_references(
            Path(args.workspace),
            include_frozen=args.include_frozen,
        ),
        args.json,
    )


def command_move(args: argparse.Namespace) -> int:
    root = Path(args.workspace).resolve()
    source, destination, repository = validate_move_paths(
        root / args.source, root / args.destination, root
    )
    rewrites, summary = build_rewrite_plan(source, destination, root)
    payload = {
        "source": workspace_relative(source, root),
        "destination": workspace_relative(destination, root),
        "mode": "apply" if args.apply else "dry-run",
        "rewrites": [asdict(item) for item in summary],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"refs move ({payload['mode']}): "
            f"{payload['source']} -> {payload['destination']}"
        )
        for item in summary:
            print(
                f"  {item.source} -> {item.future_source} "
                f"(links={item.markdown_links}, inline_paths={item.inline_paths})"
            )
    if not args.apply:
        return 0
    backup = apply_move(source, destination, repository, rewrites, root)
    print(f"refs move: OK; backup={backup}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Workspace Markdown 引用检查与搬迁")
    parser.add_argument("--workspace", default=str(WORKSPACE))
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--json", action="store_true")
    check_parser.add_argument("--include-frozen", action="store_true")
    check_parser.set_defaults(handler=command_check)

    move_parser = subparsers.add_parser("move")
    move_parser.add_argument("source")
    move_parser.add_argument("destination")
    move_parser.add_argument("--apply", action="store_true")
    move_parser.add_argument("--json", action="store_true")
    move_parser.set_defaults(handler=command_move)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, subprocess.CalledProcessError, RuntimeError) as error:
        print(f"refs: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
