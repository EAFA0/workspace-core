# Workspace 路由

Workspace 中的 scripts 和 skills 可按需维护；危险清理采用可恢复的移动操作，而非直接删除。

## 需求入口

若当前 cwd 位于需求工作区且根目录存在 `AGENTS.md`，先读它。该文件只承载需求目标、特定约束和上下文指针；全局规则仍以本 workspace 为准。

## 稳定标准

| 主题 | Owner |
|------|-------|
| 协作与验收质量底线 | `docs/architecture/01-core-principles.md` |
| 知识分类、召回和生命周期 | `docs/architecture/03-knowledge-model.md` |
| 文档所有权与单一真相源 | `docs/architecture/06-doc-layering-principles.md` |

核心提醒：先读真实实现；命令实测，不看 diff 就信；Review-before-push；PRD 只读；工具损坏时换可验证路径。

## 任务速查

| 任务 | 入口 |
|------|------|
| 知识归属、引用与分发 | `skills/spec/SKILL.md` |
| 需求 dossier、知识整理、skill 整理 | `skills/workflows/SKILL.md` |

涉及个人项目或业务链路时，先查 `biz-knowledge` / `repo-knowledge` 索引；涉及任务方法时，先读取对应 Skill，再探索代码。

## 运行时知识写入

- 已验证且未来可复用的事实，在当前上下文内直接融合到 `biz-knowledge`、`repo-knowledge`、对应 Skill 或 `biz-tests`。
- 推测和探索过程留在会话；需求特定且尚未稳定的约束写需求 dossier。
- 不创建中间总结或会话快照。
- 新建或删除正式文档时同步 canonical `INDEX.md`。
- 任务结束前执行 knowledge flush；最终回复声明 `知识写入：<owner 路径>`，确无可复用知识则写 `知识写入：无（<原因>）`。
- 不确定 owner 时运行 `bash skills/spec/bin/spec show kb-routing`。

## 工具与运行时

- Workspace 内置能力只以 `skills/` 下的已安装 Skill 为准；其他能力按当前会话注入的 Skill catalog 发现，不维护第二份手工总索引。
- 不把运行时配置、工具路径或阶段状态复制进架构标准。
