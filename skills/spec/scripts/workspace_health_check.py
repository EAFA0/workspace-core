#!/usr/bin/env python3
"""Run deterministic workspace knowledge-health checks without mutating content."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import dist
import doc_refs
import index_consistency


WORKSPACE = Path(__file__).resolve().parents[3]
DOCS_ROOT_ALLOWLIST = {
    ".git",
    ".gitignore",
    "README.md",
    "architecture",
    "biz-knowledge",
    "prd",
    "repo-knowledge",
}
FORBIDDEN_INDEX_COLUMNS = {"状态", "阶段", "进度", "完成度", "更新时间"}
ISSUE_HEADERS = ["工具", "问题", "影响", "优先级", "状态"]
ISSUE_PRIORITIES = {"P1", "P2", "P3"}
ISSUE_STATUS_PREFIXES = ("🔴 待处理", "🟡 待修复", "🔵 观察项")
RESOLVED_ISSUE_MARKERS = ("✅", "已修复", "已解决", "已确认")
SECRET_SCAN_ROOTS = ("docs", "skills", "biz-tests")
SECRET_SCAN_SUFFIXES = {
    "",
    ".cfg",
    ".conf",
    ".env",
    ".form",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".query",
    ".sh",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
LEAKED_BASIC_PREFIX = "QUt" + "UQTkwMDNh"
LEAKED_BASIC_TAIL = "Olp" + "qVTFOMkZs"
SECRET_PATTERNS = (
    (
        "Basic Authorization",
        re.compile(r"\bBasic\s+[A-Za-z0-9+/]{32,}={0,2}(?![A-Za-z0-9+/=])"),
    ),
    (
        "Bearer token",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{40,}(?![A-Za-z0-9._~+/-])"),
    ),
    (
        "JWT",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{20,}\."
            r"[A-Za-z0-9_-]{20,}\."
            r"[A-Za-z0-9_-]{20,}\b"
        ),
    ),
    (
        "private key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "known leaked Basic credential",
        re.compile(rf"\b{LEAKED_BASIC_PREFIX}[A-Za-z0-9+/=]*"),
    ),
    (
        "known leaked Basic credential tail",
        re.compile(rf"\b{LEAKED_BASIC_TAIL}[A-Za-z0-9+/=]*"),
    ),
)


@dataclass(frozen=True)
class HealthIssue:
    check: str
    message: str
    path: str = ""
    line: int = 0
    category: str = "finding"


def workspace_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def check_docs_layout(root: Path) -> list[HealthIssue]:
    docs = root / "docs"
    if not docs.exists():
        return [HealthIssue("docs-layout", "docs 目录不存在", "docs")]
    return [
        HealthIssue(
            "docs-layout",
            "docs 顶层出现未定义 owner；应归入现有 owner 或先更新知识模型",
            workspace_relative(path, root),
        )
        for path in sorted(docs.iterdir())
        if path.name not in DOCS_ROOT_ALLOWLIST
    ]


def table_headers(text: str) -> list[tuple[int, list[str]]]:
    lines = text.splitlines()
    headers = []
    for index, line in enumerate(lines[:-1]):
        if not line.lstrip().startswith("|"):
            continue
        separator = lines[index + 1]
        cells = [cell.strip() for cell in separator.strip().strip("|").split("|")]
        if not cells or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        header_cells = [
            cell.strip() for cell in line.strip().strip("|").split("|")
        ]
        headers.append((index + 1, header_cells))
    return headers


def split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    cells = []
    current = []
    escaped = False
    in_code = False
    for character in stripped[1:-1]:
        if escaped:
            current.append(character)
            escaped = False
            continue
        if character == "\\":
            current.append(character)
            escaped = True
            continue
        if character == "`":
            in_code = not in_code
            current.append(character)
            continue
        if character == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(character)
    cells.append("".join(current).strip())
    return cells


def check_issue_tracker(root: Path) -> list[HealthIssue]:
    issues = []
    canonical = root / "ISSUES.md"
    for base_name in ("docs", "skills", "tools", "biz-tests"):
        base = root / base_name
        if not base.exists():
            continue
        for path in sorted(
            candidate
            for candidate in base.rglob("*")
            if candidate.is_file()
            and candidate.name.lower() in {"issue.md", "issues.md"}
        ):
            issues.append(
                HealthIssue(
                    "issue-tracker",
                    "workspace 工具缺陷只允许进入根 ISSUES.md；请合并后删除旁路 tracker",
                    workspace_relative(path, root),
                    category="error",
                )
            )
    if not canonical.is_file():
        return issues + [
            HealthIssue(
                "issue-tracker",
                "根 ISSUES.md 不存在",
                "ISSUES.md",
                category="error",
            )
        ]

    try:
        lines = canonical.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        return issues + [
            HealthIssue(
                "issue-tracker",
                f"无法读取根 ISSUES.md: {error}",
                "ISSUES.md",
                category="error",
            )
        ]

    in_issue_table = False
    for line_number, line in enumerate(lines, start=1):
        cells = split_markdown_table_row(line)
        if cells == ISSUE_HEADERS:
            in_issue_table = True
            continue
        if not cells:
            in_issue_table = False
            continue
        if not in_issue_table:
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if len(cells) != len(ISSUE_HEADERS):
            issues.append(
                HealthIssue(
                    "issue-tracker",
                    f"Issue 表必须是 5 列，实际为 {len(cells)} 列",
                    "ISSUES.md",
                    line_number,
                    category="error",
                )
            )
            continue
        _tool, _problem, _impact, priority, status = cells
        if priority not in ISSUE_PRIORITIES:
            issues.append(
                HealthIssue(
                    "issue-tracker",
                    f"优先级必须是 P1/P2/P3，实际为 {priority}",
                    "ISSUES.md",
                    line_number,
                )
            )
        if any(marker in status for marker in RESOLVED_ISSUE_MARKERS):
            issues.append(
                HealthIssue(
                    "issue-tracker",
                    "已解决 Issue 应先迁移稳定经验，再从 ISSUES.md 删除",
                    "ISSUES.md",
                    line_number,
                )
            )
        elif not status.startswith(ISSUE_STATUS_PREFIXES):
            issues.append(
                HealthIssue(
                    "issue-tracker",
                    "状态必须以 🔴 待处理、🟡 待修复 或 🔵 观察项 开头",
                    "ISSUES.md",
                    line_number,
                )
            )
    return issues


def check_index_schema(root: Path) -> list[HealthIssue]:
    issues = []
    candidates = set((root / "docs").rglob("INDEX.md"))
    candidates.add(root / "biz-tests" / "INDEX.md")
    for path in sorted(candidate for candidate in candidates if candidate.is_file()):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            issues.append(
                HealthIssue(
                    "index-schema",
                    f"无法读取索引: {error}",
                    workspace_relative(path, root),
                    category="error",
                )
            )
            continue
        for line_number, headers in table_headers(text):
            forbidden = sorted(FORBIDDEN_INDEX_COLUMNS.intersection(headers))
            if forbidden:
                issues.append(
                    HealthIssue(
                        "index-schema",
                        f"canonical INDEX 不应承载运行状态列: {', '.join(forbidden)}",
                        workspace_relative(path, root),
                        line_number,
                    )
                )
    return issues


def check_skill_links(root: Path) -> list[HealthIssue]:
    issues = []
    skills = root / "skills"
    if not skills.exists():
        return issues
    for skill_file in sorted(skills.glob("*/SKILL.md")):
        if skill_file.parent.is_symlink():
            continue
        try:
            text = skill_file.read_text(encoding="utf-8")
        except OSError as error:
            issues.append(
                HealthIssue(
                    "skill-links",
                    f"无法读取 SKILL.md: {error}",
                    workspace_relative(skill_file, root),
                    category="error",
                )
            )
            continue
        for link in doc_refs.parse_markdown_links(skill_file, text, root):
            parts = doc_refs.split_destination(link.destination)
            if parts is None:
                continue
            path_part, _fragment = parts
            target = doc_refs.resolve_local_target(skill_file, path_part, root)
            if not target.exists():
                issues.append(
                    HealthIssue(
                        "skill-links",
                        f"Skill 路由目标不存在: {link.destination}",
                        link.source,
                        link.line,
                    )
                )
        _, inline_codes = doc_refs.protected_markdown(text)
        checked = set()
        for inline_code in inline_codes:
            try:
                tokens = shlex.split(inline_code.value)
            except ValueError:
                tokens = inline_code.value.split()
            for token in tokens:
                candidate = token.strip("()[]{}:,;").split("#", 1)[0]
                if (
                    not candidate
                    or candidate in checked
                    or any(character in candidate for character in "<>*?$")
                ):
                    continue
                if candidate.startswith(("scripts/", "bin/", "references/")):
                    target = skill_file.parent / candidate
                elif candidate.startswith("skills/"):
                    target = root / candidate
                else:
                    continue
                checked.add(candidate)
                if not target.exists():
                    issues.append(
                        HealthIssue(
                            "skill-links",
                            f"Skill 行内资源路径不存在: {candidate}",
                            workspace_relative(skill_file, root),
                            doc_refs.line_number(text, inline_code.start),
                        )
                    )
    return issues


def check_skill_scripts(root: Path) -> list[HealthIssue]:
    issues = []
    skills = root / "skills"
    if not skills.exists():
        return issues
    for skill_dir in sorted(skills.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
            continue
        for resource_dir in ("scripts", "bin"):
            directory = skill_dir / resource_dir
            if not directory.exists():
                continue
            for path in sorted(directory.rglob("*.sh")):
                if path.is_file() and path.stat().st_mode & 0o111 == 0:
                    issues.append(
                        HealthIssue(
                            "skill-scripts",
                            "Skill shell 脚本缺少可执行权限",
                            workspace_relative(path, root),
                        )
                    )
    return issues


def check_quickstart_boundaries(root: Path) -> list[HealthIssue]:
    quickstart = root / "skills" / "quickstart"
    if not quickstart.exists():
        return []
    platform_runbook_heading = re.compile(
        r"^#{2,6}\s+.*[A-Za-z][A-Za-z0-9._/ -]*\s+"
        r"(?:失败排查|故障排查|操作指南|使用手册)\s*$"
    )
    manual_heading = re.compile(
        r"^#{2,6}\s+.*(?:操作指南|使用手册)\s*$"
    )
    failure_mode_heading = re.compile(
        r"^#{2,6}\s+.*(?:Failure Mode|故障模式)\s*$",
        re.IGNORECASE,
    )
    failure_mode_table = re.compile(
        r"^\|\s*模式\s*\|\s*现象\s*\|\s*触发条件\s*\|\s*判别证据\s*\|"
        r"\s*根因\s*\|\s*处理方式\s*\|$"
    )
    issues = []
    for path in sorted(quickstart.rglob("*.md")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            issues.append(
                HealthIssue(
                    "quickstart-boundary",
                    f"无法读取 quickstart 文档: {error}",
                    workspace_relative(path, root),
                    category="error",
                )
            )
            continue
        for line_number, line in enumerate(lines, start=1):
            if (
                platform_runbook_heading.fullmatch(line.strip())
                or manual_heading.fullmatch(line.strip())
                or failure_mode_heading.fullmatch(line.strip())
                or failure_mode_table.fullmatch(line.strip())
            ):
                issues.append(
                    HealthIssue(
                        "quickstart-boundary",
                        "quickstart 只维护跨工具流程路由；平台专属手册和 Failure Mode 应迁入对应 owner",
                        workspace_relative(path, root),
                        line_number,
                    )
                )
    return issues


def check_broken_symlinks(root: Path) -> list[HealthIssue]:
    issues = []
    for name in ("docs", "skills", "biz-tests"):
        base = root / name
        if not base.exists():
            continue
        for current, directories, files in os.walk(base, followlinks=False):
            current_path = Path(current)
            for entry in sorted((*directories, *files)):
                path = current_path / entry
                if path.is_symlink() and not path.exists():
                    issues.append(
                        HealthIssue(
                            "broken-symlinks",
                            f"符号链接目标不存在: {os.readlink(path)}",
                            path.relative_to(root).as_posix(),
                        )
                    )
    return issues


def check_repository_layout(root: Path) -> list[HealthIssue]:
    issues = []
    if not (root / ".git").exists():
        issues.append(
            HealthIssue(
                "repository-layout",
                "workspace 根目录必须是唯一 Git 仓库",
                ".git",
                category="error",
            )
        )
    for root_name in SECRET_SCAN_ROOTS:
        base = root / root_name
        if not base.exists():
            continue
        for path in sorted(base.rglob(".git")):
            issues.append(
                HealthIssue(
                    "repository-layout",
                    "单仓 workspace 不允许嵌套 Git 元数据",
                    workspace_relative(path, root),
                    category="error",
                )
            )
    return issues


def check_references(root: Path) -> list[HealthIssue]:
    issues = []
    for issue in doc_refs.check_references(root):
        if issue.kind.startswith("index_"):
            continue
        if issue.level == "error" or issue.kind == "missing_inline_path":
            issues.append(
                HealthIssue(
                    "references",
                    f"{issue.kind}: {issue.message} ({issue.target})",
                    issue.source,
                    issue.line,
                )
            )
    return issues


def check_indexes(root: Path) -> list[HealthIssue]:
    issues = []
    for target in index_consistency.INDEX_TARGETS:
        result = index_consistency.check_target(target, root)
        if result.get("status"):
            issues.append(
                HealthIssue(
                    "indexes",
                    result["status"],
                    target.index,
                )
            )
        elif not result["ok"]:
            issues.append(
                HealthIssue(
                    "indexes",
                    "索引与磁盘不一致: "
                    f"索引有磁盘无={result['indexed_not_on_disk']}；"
                    f"磁盘有索引无={result['on_disk_not_indexed']}",
                    target.index,
                )
            )
    return issues


def first_table_rows(path: Path) -> list[list[str]]:
    rows = []
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            if in_table:
                break
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not in_table:
            in_table = True
            continue
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


def check_auxiliary_indexes(root: Path) -> list[HealthIssue]:
    issues = []

    biz_tests = root / "biz-tests"
    biz_index = biz_tests / "INDEX.md"
    if biz_tests.exists():
        if not biz_index.is_file():
            issues.append(
                HealthIssue(
                    "auxiliary-indexes",
                    "Biz-Test canonical INDEX.md 不存在",
                    "biz-tests/INDEX.md",
                )
            )
        else:
            try:
                indexed = {
                    cells[0].strip("`")
                    for cells in first_table_rows(biz_index)
                    if cells and cells[0].strip("`")
                }
            except OSError as error:
                issues.append(
                    HealthIssue(
                        "auxiliary-indexes",
                        f"无法读取 Biz-Test 索引: {error}",
                        "biz-tests/INDEX.md",
                        category="error",
                    )
                )
                indexed = set()
            disk = {
                path.name
                for path in biz_tests.iterdir()
                if path.is_dir() and not path.name.startswith(".")
            }
            if indexed != disk:
                issues.append(
                    HealthIssue(
                        "auxiliary-indexes",
                        "Biz-Test 索引与领域目录不一致: "
                        f"索引有磁盘无={sorted(indexed - disk)}；"
                        f"磁盘有索引无={sorted(disk - indexed)}",
                        "biz-tests/INDEX.md",
                    )
                )

    prd = root / "docs" / "prd"
    prd_index = prd / "INDEX.md"
    if prd.exists() and prd_index.is_file():
        try:
            indexed = {
                (cells[0].zfill(2), cells[1])
                for cells in first_table_rows(prd_index)
                if len(cells) >= 2 and cells[0] and cells[1]
            }
        except OSError as error:
            issues.append(
                HealthIssue(
                    "auxiliary-indexes",
                    f"无法读取 PRD 索引: {error}",
                    "docs/prd/INDEX.md",
                    category="error",
                )
            )
            indexed = set()
        disk = set()
        for path in prd.glob("*-clean.md"):
            match = re.fullmatch(r"(\d+)-(.+)-clean\.md", path.name)
            if match:
                disk.add((match.group(1).zfill(2), match.group(2)))
        if indexed != disk:
            issues.append(
                HealthIssue(
                    "auxiliary-indexes",
                    "PRD 索引与 clean 文档不一致: "
                    f"索引有磁盘无={sorted(indexed - disk)}；"
                    f"磁盘有索引无={sorted(disk - indexed)}",
                    "docs/prd/INDEX.md",
                )
            )
    return issues


def check_distribution(root: Path) -> list[HealthIssue]:
    issues = []
    operational_prefixes = (
        "缺少命令:",
        "缺少 Python 模块:",
        "manifest 读取失败:",
        "manifest 缺少 include",
        "core 路径不存在:",
    )
    for message in dist.check_core(root, smoke=True):
        category = (
            "error"
            if message.startswith(operational_prefixes)
            or message.startswith("命令失败(")
            else "finding"
        )
        issues.append(
            HealthIssue(
                "distribution",
                message,
                "workspace-core.manifest.yaml",
                category=category,
            )
        )
    return issues


def check_secrets(root: Path) -> list[HealthIssue]:
    issues = []
    for root_name in SECRET_SCAN_ROOTS:
        base = root / root_name
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            relative_parts = path.relative_to(base).parts
            if (
                not path.is_file()
                or any(part.startswith(".") for part in relative_parts)
                or "__pycache__" in relative_parts
                or path.suffix.lower() not in SECRET_SCAN_SUFFIXES
            ):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for label, pattern in SECRET_PATTERNS:
                match = pattern.search(text)
                if match is None:
                    continue
                issues.append(
                    HealthIssue(
                        "secrets",
                        f"检测到疑似真实凭证: {label}；请改为占位符或运行时注入",
                        workspace_relative(path, root),
                        doc_refs.line_number(text, match.start()),
                        category="error",
                    )
                )
    return issues


def check_git_whitespace(root: Path) -> list[HealthIssue]:
    issues = []
    repositories = [("root", root)]
    repositories.extend((name, root / name) for name in SECRET_SCAN_ROOTS)
    for name, repository in repositories:
        if not (repository / ".git").exists():
            continue
        for label, extra in (("worktree", []), ("staged", ["--cached"])):
            result = subprocess.run(
                ["git", "-C", str(repository), "diff", *extra, "--check"],
                capture_output=True,
                text=True,
            )
            if result.returncode:
                detail = (result.stdout + result.stderr).strip()
                issues.append(
                    HealthIssue(
                        "git-diff",
                        detail
                        or f"git diff {label} --check 失败，exit={result.returncode}",
                        name,
                        category="error" if result.returncode > 1 else "finding",
                    )
                )
    return issues


def run_checks(root: Path) -> list[HealthIssue]:
    checks = (
        check_references,
        check_indexes,
        check_auxiliary_indexes,
        check_issue_tracker,
        check_skill_links,
        check_skill_scripts,
        check_quickstart_boundaries,
        check_broken_symlinks,
        check_repository_layout,
        check_docs_layout,
        check_index_schema,
        check_distribution,
        check_secrets,
        check_git_whitespace,
    )
    issues = []
    for check in checks:
        try:
            issues.extend(check(root))
        except Exception as error:
            issues.append(
                HealthIssue(
                    check.__name__.removeprefix("check_").replace("_", "-"),
                    f"检查器异常: {type(error).__name__}: {error}",
                    category="error",
                )
            )
    return issues


def render(issues: list[HealthIssue], as_json: bool) -> None:
    if as_json:
        errors = sum(issue.category == "error" for issue in issues)
        findings = len(issues) - errors
        status = "error" if errors else ("findings" if findings else "ok")
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": status,
                    "summary": {
                        "findings": findings,
                        "errors": errors,
                    },
                    "issues": [asdict(issue) for issue in issues],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if not issues:
        print("HEALTH_OK")
        return
    errors = sum(issue.category == "error" for issue in issues)
    findings = len(issues) - errors
    status = "HEALTH_ERROR" if errors else "HEALTH_FAIL"
    print(f"{status}: findings={findings} errors={errors}")
    for issue in issues:
        location = issue.path
        if issue.line:
            location = f"{location}:{issue.line}"
        suffix = f" [{location}]" if location else ""
        print(f"- {issue.category}/{issue.check}: {issue.message}{suffix}")


def exit_code(issues: list[HealthIssue]) -> int:
    if any(issue.category == "error" for issue in issues):
        return 2
    return 1 if issues else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Workspace 知识体系确定性健康检查（只读）"
    )
    parser.add_argument("--workspace", default=str(WORKSPACE))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    issues = run_checks(workspace)
    render(issues, args.json)
    return exit_code(issues)


if __name__ == "__main__":
    raise SystemExit(main())
