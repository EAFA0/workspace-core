---
name: spec
description: 知识 owner、文档引用和 workspace 分发的确定性前门。当已验证知识需要选择 biz-knowledge、repo-knowledge、Skill、architecture 或 Biz-Test owner，或需要检查/移动文档引用、构建可分发 core 时使用。Skill 是“如何完成一类任务”的可执行知识 owner。
---

# spec — 确定性文档前门

用确定性命令获取知识 owner 契约、检查引用和构建可分发 core。

## 何时用

写入以下类型时，**先** `spec show <type>`：

| type | 什么时候 |
|------|---------|
| `biz-test` | 在线测试跑出重要 case、值得回归时写回 biz-tests |
| `kb-routing` | 已验证知识写入时选择唯一 owner |

## 命令

优先用已安装的 `spec` 命令；环境未安装时回退到 skill 内路径。

```bash
spec list                 # 枚举所有类型 + 何时用
spec show kb-routing      # 输出知识 owner 选择规则
spec show biz-test        # 输出 Biz-Test 写回契约
spec refs check           # 活动 docs 本地 Markdown 链接 + canonical 索引检查
spec refs move <src> <dst>  # dry-run：预览移动和自动改链
spec refs move <src> <dst> --apply  # 备份后事务化移动；失败自动恢复
spec health check         # 只读检查引用、索引、Skill 路由、owner 布局和分发闭包
spec health check --workspace <path> --json  # 外部调度器显式指定目标 workspace
spec health check --json  # 机器输出；exit 0=健康 1=有发现 2=执行错误
spec dist check --smoke     # 检查 canonical core 可直接分发
spec dist build <dir> --archive  # 从同一源码生成只读发行物
spec dist init <workspace>  # 初始化空 INDEX 和数据目录
spec dist doctor <workspace>  # 验证重建结果

# 回退（未安装 spec 命令时）：
python3 skills/spec/scripts/spec.py <同上参数>
```

> 安装：在 workspace 根目录运行：
>
> ```bash
> ln -sf "$PWD/skills/spec/bin/spec" ~/.local/bin/spec
> ```
>
> `bin/spec` 用 `readlink -f` 解析真实路径，symlink 到任意 PATH 目录均可。

## 工作原理（为什么可信）

- **路径与元信息** 集中在 `spec.manifest.yaml`（唯一路由真相源）。文档搬家只改这一行，引用它的文档零改动。
- **正文**（how-to / 规范）运行时 `cat` 磁盘文件，工具内**不 hardcode 任何规范文字** → 不存在"工具输出与文档不一致"。
- **文档移动** 保留原生 Markdown：`refs move` 重算入链、出链和章节锚点后的相对路径，不引入第二套引用语法。
- **健康门禁** 只聚合确定性检查并返回 exit code，不自动合并、移动、删除或改写知识。
- **分发** 读取 workspace 根 `workspace-core.manifest.yaml`；发行目录只是构建产物，禁止作为第二份源码维护。

## 扩展

新增一类契约 = 往 `spec.manifest.yaml` 的 `types` 加一条路径与元信息，不改代码。
