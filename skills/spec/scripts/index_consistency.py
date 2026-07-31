#!/usr/bin/env python3
"""index_consistency — INDEX.md ↔ 磁盘文件 双向一致性 SSOT。

唯一真相源：INDEX.md 检查与修复都收敛在本模块，其他校验器通过公开函数复用，
避免各自维护实现。--fix 自动移除过期条目并追加缺失占位行，保持排序和格式。

设计边界（确定性 vs 判断）：
  - 检查、移除过期行 = 确定性 → 自动做。
  - 追加缺失文件 = 只写「占位骨架行」（真实数据仅文件名+链接，其余列 <待补充>），
    绝不捏造 title/仓库/决策等判断性内容——交人/agent 填。

用法：
  python3 skills/spec/scripts/index_consistency.py            # --check（默认）：报告 + 有不一致 exit 1
  python3 skills/spec/scripts/index_consistency.py --fix       # 修复 INDEX（移除过期 + 追加占位），exit 0
  python3 skills/spec/scripts/index_consistency.py --json
  python3 skills/spec/scripts/index_consistency.py --only architecture,biz-knowledge,repo-knowledge
  python3 skills/spec/scripts/index_consistency.py --workspace PATH

公开接口：`check_target`、`check_all`、`fix_target`、`fix_all`。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

WORKSPACE = Path(
    os.environ.get(
        "WORKSPACE",
        Path(__file__).resolve().parents[3],
    )
).resolve()


# ── 配置：每个被索引目录一行 ───────────────────────────────────────────
@dataclass
class IndexTarget:
    key: str
    dir: str                         # 磁盘目录（相对 workspace）
    index: str                       # INDEX/路由文件路径（相对 ws）
    mode: str                        # single-table | double-table
    section_headings: tuple          # 索引段的 ## 标题候选
    subdirs: list = field(default_factory=list)   # double-table 的子目录


INDEX_TARGETS: list[IndexTarget] = [
    IndexTarget("architecture", "docs/architecture", "docs/architecture/INDEX.md",
                "single-table", ("Architecture Index",)),
    IndexTarget("biz-knowledge", "docs/biz-knowledge", "docs/biz-knowledge/INDEX.md",
                "single-table", ("Biz Knowledge Index",)),
    IndexTarget("repo-knowledge", "docs/repo-knowledge", "docs/repo-knowledge/INDEX.md",
                "double-table", ("Repo Knowledge Index",),
                subdirs=["foundations", "features"]),
]

# 显式不纳入：
# - docs/README.md：导航，不是内容索引。
# - docs/prd/INDEX.md：来源映射，不要求每个导出文件逐一登记。
# - repo-knowledge/{foundations,features}：由父级 INDEX.md 统一维护。

DEFAULT_KEYS = [
    target.key for target in INDEX_TARGETS
]


def get_target(key: str) -> IndexTarget:
    for t in INDEX_TARGETS:
        if t.key == key:
            return t
    raise KeyError(f"no index target: {key}")


# ── 共享原语（从 dashboard lift，保持逐字一致）────────────────────────
def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def md_files(p: Path, recursive: bool = False) -> list[Path]:
    if not p.exists():
        return []
    iterator = p.rglob("*.md") if recursive else p.glob("*.md")
    return sorted([
        x for x in iterator
        if x.is_file()
        and not x.name.startswith("_")
        and ".git" not in x.parts
    ])


def _index_section_text(text: str, headings: tuple) -> str:
    """定位索引段（## 标题命中 headings 之一），命中不到退回全文。"""
    pat = "|".join(re.escape(h) for h in headings)
    for sec in re.split(r"\n(?=## )", text):
        if re.match(rf"##\s*({pat})\s*\n", sec):
            return sec + "\n"
    return text


def _table_md_links(section_text: str) -> set[str]:
    """索引段内、表格行中的本地 .md 链接原值。"""
    files = set()
    for line in section_text.splitlines():
        if not (line.lstrip().startswith("|") and line.count("|") >= 2):
            continue
        for m in re.finditer(r"\]\(([^)]+\.md)\)", line):
            target = m.group(1).split("#", 1)[0]
            if target.startswith("/") or "://" in target:
                continue
            files.add(target)
    return files


def _relative_doc_key(index: Path, root: Path, target: str) -> str | None:
    """索引内链接 → 相对被索引目录的完整路径。目录外链接不属于当前索引。"""
    try:
        resolved = (index.parent / target).resolve()
        relative = resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    if relative.name in {"README.md", "INDEX.md"} or relative.suffix != ".md":
        return None
    return relative.as_posix()


def _indexed_doc_keys(t: IndexTarget, ws: Path) -> set[str]:
    index = ws / t.index
    root = ws / t.dir
    section = _index_section_text(read_text(index), t.section_headings)
    keys = set()
    for target in _table_md_links(section):
        key = _relative_doc_key(index, root, target)
        if key is not None:
            keys.add(key)
    return keys


def _disk_doc_keys(root: Path, recursive: bool) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in md_files(root, recursive=recursive)
        if path.name not in {"README.md", "INDEX.md"}
    }


# ── 检查 ───────────────────────────────────────────────────────────────
def _check_single(t: IndexTarget, ws: Path) -> dict:
    index = ws / t.index
    if not index.exists():
        return {"status": "index_missing"}
    indexed = _indexed_doc_keys(t, ws)
    disk = _disk_doc_keys(ws / t.dir, recursive=False)
    return {
        "indexed_not_on_disk": sorted(indexed - disk),
        "on_disk_not_indexed": sorted(disk - indexed),
        "ok": indexed == disk,
    }


def _check_double(t: IndexTarget, ws: Path) -> dict:
    """双索引：按 <subdir>/<file>.md 完整路径比较，允许不同子目录同名。"""
    index = ws / t.index
    if not index.exists():
        return {"status": "index_missing"}
    indexed = _indexed_doc_keys(t, ws)
    disk = set()
    for sub in t.subdirs:
        for p in md_files(ws / t.dir / sub):
            if p.name not in {"README.md", "INDEX.md"}:
                disk.add(p.relative_to(ws / t.dir).as_posix())
    return {
        "indexed_not_on_disk": sorted(indexed - disk),
        "on_disk_not_indexed": sorted(disk - indexed),
        "ok": indexed == disk,
    }


_CHECKERS = {
    "single-table": _check_single,
    "double-table": _check_double,
}


def check_target(t: IndexTarget, ws: Path = WORKSPACE) -> dict:
    return _CHECKERS[t.mode](t, ws)


def check_all(ws: Path = WORKSPACE, only: list[str] | None = None) -> dict:
    """返回 {key: result}；only 可限定子集。"""
    if only is None:
        only = DEFAULT_KEYS
    return {key: check_target(get_target(key), ws) for key in only}


# ── 修复（移除过期 + 追加占位骨架，保持排序/格式）─────────────────────
PLACEHOLDER = "<待补充>"


def _table_bounds(lines: list[str], headings: tuple) -> tuple[int, int, int] | None:
    """在 headings 命中的索引段里找表格：返回 (header_idx, sep_idx, body_end_excl)。
    找不到返回 None（调用方跳过并报告，不猜）。"""
    pat = "|".join(re.escape(h) for h in headings)
    in_sec = False
    i = 0
    while i < len(lines):
        if re.match(rf"##\s*({pat})\s*$", lines[i].strip()):
            in_sec = True
            i += 1
            continue
        if in_sec and lines[i].startswith("## "):
            break
        if in_sec and lines[i].lstrip().startswith("|") and lines[i].count("|") >= 2:
            header = i
            if i + 1 < len(lines) and re.search(r"\|[\s:-]+\|", lines[i + 1]):
                sep = i + 1
                j = sep + 1
                while j < len(lines) and lines[j].lstrip().startswith("|") and lines[j].count("|") >= 2:
                    j += 1
                return (header, sep, j)
        i += 1
    return None


def _placeholder_row(header_line: str, link_md: str) -> str:
    """按表头列数生成占位行：链接放「含 文档/doc 的列」，否则第 2 列；其余 <待补充>。"""
    headers = [c.strip() for c in header_line.strip().strip("|").split("|")]
    n = len(headers)
    link_col = 1 if n > 1 else 0
    for idx, h in enumerate(headers):
        if re.search(r"文档|doc|名称|条目", h, re.I):
            link_col = idx
            break
    cells = [PLACEHOLDER] * n
    cells[link_col] = link_md
    return "| " + " | ".join(cells) + " |"


def fix_target(t: IndexTarget, ws: Path = WORKSPACE, apply: bool = False) -> dict:
    """移除过期行并追加缺失占位行。"""
    chk = check_target(t, ws)
    if chk.get("status"):
        return {"key": t.key, "status": chk["status"], "changed": False}
    stale = chk["indexed_not_on_disk"]
    missing = chk["on_disk_not_indexed"]
    if not stale and not missing:
        return {"key": t.key, "changed": False, "removed": [], "appended": []}

    index = ws / t.index
    lines = read_text(index).splitlines()
    bounds = _table_bounds(lines, t.section_headings)
    if bounds is None:
        return {"key": t.key, "changed": False, "skipped": "定位不到索引表（表头/分隔行），跳过不猜",
                "stale": stale, "missing": missing}
    header, sep, body_end = bounds

    # 1) 移除过期行。
    removed = []
    kept_body = []
    for ln in lines[sep + 1:body_end]:
        hit = None
        for m in re.finditer(r"\]\(([^)]+\.md)\)", ln):
            target = m.group(1).split("#", 1)[0]
            key = _relative_doc_key(index, ws / t.dir, target)
            if key in stale:
                hit = key
                break
        if hit:
            removed.append(hit)
        else:
            kept_body.append(ln)

    # 2) 追加占位骨架行到表末。
    appended = []
    new_rows = []
    for name in missing:
        if t.mode == "double-table":
            row = _placeholder_row(lines[header], f"[{name}]({name})")
        else:
            row = _placeholder_row(lines[header], f"[{name}](./{name})")
        new_rows.append(row)
        appended.append(name)

    new_lines = lines[:sep + 1] + kept_body + new_rows + lines[body_end:]
    changed = bool(removed or appended)
    if apply and changed:
        index.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return {"key": t.key, "changed": changed, "removed": removed, "appended": appended,
            "applied": apply and changed}
def fix_all(ws: Path = WORKSPACE, only: list[str] | None = None, apply: bool = False) -> list[dict]:
    targets = [t for t in INDEX_TARGETS if only is None or t.key in only]
    return [fix_target(t, ws, apply) for t in targets]


# ── CLI ─────────────────────────────────────────────────────────────────
def _print_check(ws: Path, only: list[str] | None) -> int:
    targets = [t for t in INDEX_TARGETS if only is None or t.key in only]
    bad = 0
    for t in targets:
        r = check_target(t, ws)
        if r.get("status"):
            print(f"[{t.key}] {r['status']}")
            continue
        if r["ok"]:
            print(f"[{t.key}] ✓ 一致")
        else:
            bad += 1
            print(f"[{t.key}] ✗ 不一致")
            if r["indexed_not_on_disk"]:
                print(f"    过期（索引有磁盘无）: {r['indexed_not_on_disk']}")
            if r["on_disk_not_indexed"]:
                print(f"    遗漏（磁盘有索引无）: {r['on_disk_not_indexed']}")
    return 1 if bad else 0


def _print_fix(ws: Path, only: list[str] | None) -> int:
    for r in fix_all(ws, only, apply=True):
        if r.get("status"):
            print(f"[{r['key']}] {r['status']}")
        elif r.get("skipped"):
            print(f"[{r['key']}] 跳过：{r['skipped']}  过期={r.get('stale')} 遗漏={r.get('missing')}")
        elif r["changed"]:
            print(f"[{r['key']}] 已修复：移除 {r['removed']}；追加占位 {r['appended']}（<待补充> 待填）")
        else:
            print(f"[{r['key']}] ✓ 无需改动")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="INDEX.md ↔ 磁盘 双向一致性 SSOT")
    ap.add_argument("--fix", action="store_true", help="修复（移除过期 + 追加占位），默认只 check")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--workspace", default=str(WORKSPACE))
    ap.add_argument("--only", default=None, help="逗号分隔的 target key 子集")
    args = ap.parse_args()
    ws = Path(args.workspace)
    only = [x.strip() for x in args.only.split(",")] if args.only else None

    if args.json:
        import json
        payload = {t.key: check_target(t, ws)
                   for t in INDEX_TARGETS if only is None or t.key in only}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        sys.exit(0)

    sys.exit(_print_fix(ws, only) if args.fix else _print_check(ws, only))


if __name__ == "__main__":
    main()
