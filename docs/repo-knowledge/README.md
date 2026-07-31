# Repo Knowledge Contract

本目录记录仓库公共基座和 feature 落地知识。

## 组织维度

| 目录 | Owner 维度 | 判据 |
|------|------------|------|
| `foundations/` | 仓库 | 任意该仓任务都需要知道 |
| `features/` | 业务链路 | 只在处理该链路时需要，可跨多个仓库 |

- Feature 文档按完整链路组织，不按仓库再次拆分。
- 同一事实只在一个位置维护，其他文档通过链接引用。

## 文档要求

### Foundations

- 仓库职责与边界
- 关键入口和数据模型
- 通用工具链与约束
- 全仓库级踩坑

### Features

- 链路目标和业务边界
- 涉及仓库及各自职责
- 关键实现点
- feature 特有踩坑和验证方式

## 索引

当前 workspace 只有一个 canonical [INDEX.md](./INDEX.md)，其中按 `Foundations` / `Features` 两节索引二级目录内容。`foundations/` 和 `features/` 不再各建 INDEX，避免同一文档出现多个索引 owner。

知识分类和召回顺序见 [`03-knowledge-model.md`](../architecture/03-knowledge-model.md)。
