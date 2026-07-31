# Docs 路由

本文件只做目录导航，不承载规则正文。

## 标准层

| 内容 | 契约 | 当前索引 |
|------|------|----------|
| 跨目录稳定标准 | [architecture/README.md](architecture/README.md) | [architecture/INDEX.md](architecture/INDEX.md) |
| Biz-Test 契约 | [../biz-tests/README.md](../biz-tests/README.md) | [../biz-tests/INDEX.md](../biz-tests/INDEX.md) |

## 正式知识

| 内容 | 契约 | 当前索引 |
|------|------|----------|
| 业务规则 | [biz-knowledge/README.md](biz-knowledge/README.md) | [biz-knowledge/INDEX.md](biz-knowledge/INDEX.md) |
| Feature 与仓库知识 | [repo-knowledge/README.md](repo-knowledge/README.md) | [repo-knowledge/INDEX.md](repo-knowledge/INDEX.md) |
| 只读需求源 | [prd/README.md](prd/README.md) | [prd/INDEX.md](prd/INDEX.md) |

知识分类和召回顺序见 [03-knowledge-model.md](architecture/03-knowledge-model.md)。

## 执行入口

- 确定性契约与校验：`skills/spec/`
- 项目级 SOP：`skills/workflows/`
- 可执行知识与平台机制：对应 Skill 的 `SKILL.md` / `references/` / `scripts/`

平台实现、运行状态和工具注册属于当前 workspace adapter，不由本 core 路由维护。
