#!/usr/bin/env python3
"""spec.py — 知识 owner、文档引用与分发的确定性前门。

设计铁律：
  - 只读 manifest（skills/spec/spec.manifest.yaml）拿路径，运行时 cat 磁盘文件取正文。
    绝不在本文件里 hardcode 规范/契约文字 → 无第二真相源 → 不存在内外不一致。

用法：
  python3 skills/spec/scripts/spec.py list                 # 枚举所有类型 + 何时用
  python3 skills/spec/scripts/spec.py show kb-routing      # 知识 owner 选择规则
  python3 skills/spec/scripts/spec.py show biz-test        # Biz-Test 写回契约
  python3 skills/spec/scripts/spec.py refs check           # 活动文档本地链接 + canonical 索引检查
  python3 skills/spec/scripts/spec.py refs move <src> <dst> [--apply]  # dry-run / 事务化移动
  python3 skills/spec/scripts/spec.py health check          # 知识体系确定性健康门禁
  python3 skills/spec/scripts/spec.py dist check           # 检查 canonical core 可直接分发
  python3 skills/spec/scripts/spec.py dist build <dir>     # 从同一源码生成只读发行物
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]               # workspace 根（skills/spec/scripts/spec.py → ../../..）
MANIFEST = Path(__file__).resolve().parents[1] / "spec.manifest.yaml"  # skills/spec/spec.manifest.yaml

# subprocess.Popen 的 executable 形参不接受空字符串；某些受限 Python 环境
# （如部分沙箱/嵌入式解释器）会把 sys.executable 报告为空串。
# 缺省回退到 /usr/bin/python3 —— spec 的入口脚本 `skills/spec/bin/spec`
# 本来就是通过 `python3` 调起本文件，故此回退与原意图一致。
_PY = sys.executable or "/usr/bin/python3"


def load_manifest() -> dict:
    try:
        data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"[spec] manifest 缺失：{MANIFEST}")
    except yaml.YAMLError as e:
        sys.exit(f"[spec] manifest 解析失败：{e}")
    if not data or "types" not in data:
        sys.exit("[spec] manifest 无 types 段")
    return data


def resolve(rel: str | None) -> Path | None:
    """manifest 里的相对路径 → 绝对路径（含 #section 的先剥掉锚点）。"""
    if not rel:
        return None
    return ROOT / rel.split("#", 1)[0]


def read_body(path: Path, section: str | None = None) -> str:
    """读磁盘正文；给了 section 就只截该 ## 标题到下一个同级/更高级标题之间。"""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return f"[读取失败：{e}]"
    if not section:
        return text.rstrip()
    lines = text.splitlines()
    out: list[str] = []
    grabbing = False
    start_level = section.count("#", 0, section.find(" ") if " " in section else len(section))
    for ln in lines:
        if ln.strip() == section.strip():
            grabbing = True
            out.append(ln)
            continue
        if grabbing:
            # 遇到同级或更高级标题即停
            if ln.startswith("#"):
                lvl = len(ln) - len(ln.lstrip("#"))
                if lvl <= start_level:
                    break
            out.append(ln)
    body = "\n".join(out).rstrip()
    return body or f"[未找到章节：{section}]"


# ── list ───────────────────────────────────────────────────────────────────
def cmd_list(m: dict, as_json: bool) -> None:
    types = m["types"]
    if as_json:
        print(json.dumps(
            {k: {"title": v.get("title"), "when": v.get("when"), "kind": v.get("kind")}
             for k, v in types.items()},
            ensure_ascii=False, indent=2))
        return
    print("可用规范类型（spec show <type> 取详情）：\n")
    width = max(len(k) for k in types)
    for k, v in types.items():
        print(f"  {k.ljust(width)}  {v.get('title', '')}")
        if v.get("when"):
            print(f"  {' ' * width}  何时: {v['when']}")
    print()


# ── show ───────────────────────────────────────────────────────────────────
def cmd_show(m: dict, vtype: str, paths_only: bool, as_json: bool) -> None:
    types = m["types"]
    if vtype not in types:
        avail = ", ".join(types)
        sys.exit(f"[spec] 未知类型 '{vtype}'。可用：{avail}")
    v = types[vtype]

    if as_json:
        out = dict(v)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    line = "━" * 60
    print(line)
    print(f"  {v.get('title', vtype)}")
    print(line)
    if v.get("home"):
        print(f"存到:   {v['home']}")
    if v.get("naming"):
        print(f"命名:   {v['naming']}")
    tmpl = v.get("template")
    print(f"模板:   {tmpl if tmpl else '（无）'}")
    if v.get("owner"):
        print(f"Owner:   {v['owner']}")

    val = v.get("validate")
    print(f"写完跑: {val.replace('{file}', '<file>') if val else '（无确定性校验器）'}")

    if paths_only:
        if v.get("owner"):
            print(f"契约: {v['owner']}")
        print(line)
        return

    owner = resolve(v.get("owner"))
    if owner and owner.exists():
        print(line)
        print(f"契约（{v['owner']}）")
        print(line)
        print(read_body(owner, v.get("section")))
    elif v.get("owner"):
        print(f"契约: {v['owner']}  [文件不存在]")
    print(line)


def cmd_refs(args: argparse.Namespace) -> int:
    script = ROOT / "skills" / "spec" / "scripts" / "doc_refs.py"
    command = [_PY, str(script), args.refs_cmd]
    if args.refs_cmd == "check":
        if args.json:
            command.append("--json")
        if args.include_frozen:
            command.append("--include-frozen")
    elif args.refs_cmd == "move":
        command.extend([args.source, args.destination])
        if args.apply:
            command.append("--apply")
        if args.json:
            command.append("--json")
    return subprocess.call(command, cwd=str(ROOT))


def cmd_health(args: argparse.Namespace) -> int:
    script = ROOT / "skills" / "spec" / "scripts" / "workspace_health_check.py"
    command = [_PY, str(script)]
    if args.workspace:
        command.extend(["--workspace", args.workspace])
    if args.json:
        command.append("--json")
    return subprocess.call(command, cwd=str(ROOT))


def cmd_dist(args: argparse.Namespace) -> int:
    script = ROOT / "skills" / "spec" / "scripts" / "dist.py"
    command = [_PY, str(script), args.dist_cmd]
    if args.dist_cmd == "check":
        if args.json:
            command.append("--json")
        if args.smoke:
            command.append("--smoke")
    elif args.dist_cmd == "build":
        command.append(args.output)
        if args.archive:
            command.append("--archive")
    elif args.dist_cmd in {"init", "doctor"}:
        command.append(args.workspace)
    return subprocess.call(command, cwd=str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description="规范/契约 确定性前门")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="枚举所有规范类型")
    p_list.add_argument("--json", action="store_true")

    p_show = sub.add_parser("show", help="产出+存储某类型需要的一切")
    p_show.add_argument("type")
    p_show.add_argument("--paths-only", action="store_true", help="只给路径，不 cat 正文")
    p_show.add_argument("--json", action="store_true")

    p_refs = sub.add_parser("refs", help="检查或移动 workspace Markdown 引用")
    refs_sub = p_refs.add_subparsers(dest="refs_cmd", required=True)

    p_refs_check = refs_sub.add_parser("check", help="检查活动文档链接与 canonical 索引")
    p_refs_check.add_argument("--json", action="store_true")
    p_refs_check.add_argument("--include-frozen", action="store_true")

    p_refs_move = refs_sub.add_parser("move", help="dry-run 或事务化移动 Markdown")
    p_refs_move.add_argument("source")
    p_refs_move.add_argument("destination")
    p_refs_move.add_argument("--apply", action="store_true")
    p_refs_move.add_argument("--json", action="store_true")

    p_health = sub.add_parser("health", help="运行 workspace 知识体系健康门禁")
    health_sub = p_health.add_subparsers(dest="health_cmd", required=True)

    p_health_check = health_sub.add_parser("check", help="只读确定性检查")
    p_health_check.add_argument(
        "--workspace",
        help="目标 workspace；默认使用 spec 所在 workspace",
    )
    p_health_check.add_argument("--json", action="store_true")

    p_dist = sub.add_parser("dist", help="检查、构建或初始化可分发 workspace core")
    dist_sub = p_dist.add_subparsers(dest="dist_cmd", required=True)

    p_dist_check = dist_sub.add_parser("check", help="检查 canonical core 分发闭包")
    p_dist_check.add_argument("--json", action="store_true")
    p_dist_check.add_argument("--smoke", action="store_true")

    p_dist_build = dist_sub.add_parser("build", help="从 canonical source 生成发行物")
    p_dist_build.add_argument("output")
    p_dist_build.add_argument("--archive", action="store_true")

    p_dist_init = dist_sub.add_parser("init", help="初始化 INDEX 和数据目录")
    p_dist_init.add_argument("workspace")

    p_dist_doctor = dist_sub.add_parser("doctor", help="验证重建后的 workspace")
    p_dist_doctor.add_argument("workspace")

    args = ap.parse_args()

    m = load_manifest()

    if args.cmd == "list":
        cmd_list(m, args.json)
    elif args.cmd == "show":
        cmd_show(m, args.type, args.paths_only, args.json)
    elif args.cmd == "refs":
        sys.exit(cmd_refs(args))
    elif args.cmd == "health":
        sys.exit(cmd_health(args))
    elif args.cmd == "dist":
        sys.exit(cmd_dist(args))


if __name__ == "__main__":
    main()
