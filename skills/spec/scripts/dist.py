#!/usr/bin/env python3
"""Build and validate a distributable workspace core from canonical source."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "workspace-core.manifest.yaml"


def load_manifest(root: Path = ROOT) -> dict:
    path = root / MANIFEST.name
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise RuntimeError(f"manifest 读取失败: {error}") from error
    if not isinstance(data, dict) or not data.get("include"):
        raise RuntimeError("manifest 缺少 include")
    return data


def is_excluded(relative: str, patterns: list[str]) -> bool:
    path = Path(relative)
    if "__pycache__" in path.parts or path.suffix == ".pyc":
        return True
    return any(path.match(pattern) for pattern in patterns)


def collect_files(root: Path, manifest: dict) -> list[Path]:
    files: set[Path] = set()
    excludes = manifest.get("exclude", [])
    for entry in manifest["include"]:
        path = root / entry
        if not path.exists():
            raise RuntimeError(f"core 路径不存在: {entry}")
        candidates = [path] if path.is_file() else path.rglob("*")
        for candidate in candidates:
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(root).as_posix()
            if is_excluded(relative, excludes):
                continue
            files.add(candidate)
    manifest_path = root / MANIFEST.name
    if manifest_path.exists():
        files.add(manifest_path)
    return sorted(files)


def check_dependencies(manifest: dict) -> list[str]:
    issues = []
    for command in manifest.get("required_commands", []):
        if shutil.which(command) is None:
            issues.append(f"缺少命令: {command}")
    for module in manifest.get("required_python_modules", []):
        try:
            importlib.import_module(module)
        except ImportError:
            issues.append(f"缺少 Python 模块: {module}")
    return issues


def check_forbidden(root: Path, files: list[Path], patterns: list[str]) -> list[str]:
    compiled = [re.compile(pattern) for pattern in patterns]
    issues = []
    text_suffixes = {".md", ".py", ".sh", ".yaml", ".yml", ".json", ".txt"}
    for path in files:
        if path.name == MANIFEST.name:
            continue
        if path.suffix not in text_suffixes and path.name != MANIFEST.name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for pattern in compiled:
                if pattern.search(line):
                    issues.append(
                        f"{path.relative_to(root)}:{line_number}: "
                        f"命中禁止模式 {pattern.pattern}: {line.strip()}"
                    )
    return issues


def check_relative_links(root: Path, files: list[Path]) -> list[str]:
    issues = []
    markdown_files = {path.resolve() for path in files if path.suffix == ".md"}
    pattern = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)")
    for path in sorted(markdown_files):
        text = path.read_text(encoding="utf-8")
        in_fence = False
        for line_number, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in pattern.finditer(line):
                destination = match.group(1).split("#", 1)[0].strip("<>")
                if (
                    not destination
                    or "://" in destination
                    or destination.startswith(("mailto:", "#"))
                    or any(character in destination for character in "<>{}*$")
                ):
                    continue
                target = (path.parent / destination).resolve()
                if target.is_dir():
                    readme = target / "README.md"
                    if readme in markdown_files:
                        continue
                if target not in markdown_files and not target.exists():
                    issues.append(
                        f"{path.relative_to(root)}:{line_number}: "
                        f"链接目标不存在: {destination}"
                    )
    return issues


def run_core_smoke(root: Path) -> list[str]:
    issues = []
    spec = root / "skills/spec/bin/spec"
    commands = [
        ["bash", str(spec), "list"],
        ["bash", str(spec), "show", "kb-routing", "--paths-only"],
        ["bash", str(spec), "show", "biz-test", "--paths-only"],
        ["bash", str(spec), "refs", "check"],
    ]
    for command in commands:
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            env=environment,
        )
        if result.returncode != 0:
            issues.append(
                f"命令失败({result.returncode}): {' '.join(command)}\n"
                f"{result.stdout}{result.stderr}"
            )
    return issues


def check_core(root: Path = ROOT, smoke: bool = False) -> list[str]:
    manifest = load_manifest(root)
    files = collect_files(root, manifest)
    issues = check_dependencies(manifest)
    issues.extend(check_forbidden(root, files, manifest.get("forbidden_patterns", [])))
    issues.extend(check_relative_links(root, files))
    if smoke:
        issues.extend(run_core_smoke(root))
    return issues


def copy_core(root: Path, destination: Path) -> list[Path]:
    manifest = load_manifest(root)
    files = collect_files(root, manifest)
    for source in files:
        relative = source.relative_to(root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return files


def empty_index(title: str, header: str, separator: str) -> str:
    return f"# {title}\n\n{header}\n{separator}\n"


def init_data(root: Path) -> None:
    directories = [
        "docs/prd",
        "docs/biz-knowledge",
        "docs/repo-knowledge/features",
        "docs/repo-knowledge/foundations",
        "biz-tests",
    ]
    for directory in directories:
        (root / directory).mkdir(parents=True, exist_ok=True)
    indexes = {
        "docs/biz-knowledge/INDEX.md": empty_index(
            "Biz Knowledge Index",
            "| 业务领域 | 文档 | 涉及仓库 | 关联 Feature |",
            "|---------|------|---------|--------------|",
        ),
        "docs/repo-knowledge/INDEX.md": (
            "# Repo Knowledge Index\n\n## Foundations\n\n"
            "| 仓库 | 文档 | 核心领域 |\n"
            "|------|------|---------|\n\n"
            "## Features\n\n"
            "| Feature | 文档 | 涉及仓库 | 核心内容 |\n"
            "|---------|------|---------|---------|\n"
        ),
        "docs/prd/INDEX.md": empty_index(
            "Requirement Source Index",
            "| 编号 | slug | 来源 | 标题 | 对应知识 |",
            "|------|------|------|------|----------|",
        ),
        "biz-tests/INDEX.md": empty_index(
            "Biz-Test Index",
            "| 领域 slug | 对应 Biz Knowledge | 对应 Feature |",
            "|----------|--------------------|--------------|",
        ),
    }
    for relative, content in indexes.items():
        path = root / relative
        if not path.exists():
            path.write_text(content, encoding="utf-8")


def command_check(args: argparse.Namespace) -> int:
    issues = check_core(ROOT, smoke=args.smoke)
    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    elif issues:
        for issue in issues:
            print(f"[ERROR] {issue}")
    else:
        print("dist check: OK")
    return 1 if issues else 0


def command_build(args: argparse.Namespace) -> int:
    issues = check_core(ROOT)
    if issues:
        for issue in issues:
            print(f"[ERROR] {issue}")
        return 1
    destination = Path(args.output).resolve()
    if destination.exists():
        raise RuntimeError(f"输出已存在: {destination}")
    destination.mkdir(parents=True)
    copy_core(ROOT, destination)
    init_data(destination)
    smoke_issues = check_core(destination, smoke=True)
    if smoke_issues:
        shutil.rmtree(destination)
        raise RuntimeError("\n".join(smoke_issues))
    if args.archive:
        archive = destination.with_suffix(".tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(destination, arcname=destination.name)
        print(f"dist build: OK; dir={destination}; archive={archive}")
    else:
        print(f"dist build: OK; dir={destination}")
    return 0


def command_init(args: argparse.Namespace) -> int:
    root = Path(args.workspace).resolve()
    init_data(root)
    print(f"dist init: OK; workspace={root}")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    root = Path(args.workspace).resolve()
    issues = check_core(root, smoke=True)
    if issues:
        for issue in issues:
            print(f"[ERROR] {issue}")
        return 1
    print("dist doctor: OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Workspace core distribution")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check")
    check.add_argument("--json", action="store_true")
    check.add_argument("--smoke", action="store_true")
    check.set_defaults(handler=command_check)

    build = subparsers.add_parser("build")
    build.add_argument("output")
    build.add_argument("--archive", action="store_true")
    build.set_defaults(handler=command_build)

    init = subparsers.add_parser("init")
    init.add_argument("workspace")
    init.set_defaults(handler=command_init)

    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("workspace")
    doctor.set_defaults(handler=command_doctor)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"dist: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
