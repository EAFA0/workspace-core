# 知识体系维护 Runbook

> 定位：同一个维护 Agent 在同一上下文内完成检查、核验、最小修复和复验。
> 本流程不创建 finding 中间层、报告文件、change-summary 或会话快照。

## 外部调度契约

外部系统只负责定时触发、保存最终输出和通知。它不解析知识、不维护 finding 队列。

建议由外部系统定期触发，也可在大规模知识变更后手动触发。每次运行使用同一套优先级，不读取日期、不维护游标：

1. 先处理确定性 health finding；
2. 若存在活动 Issue，按 P1 → P2 → P3 消费一个问题或同一工具的一组问题；
3. 若没有可处理 Issue，根据当前代码、Git 变更或权威证据选择一个最值得核验的最小知识单元；
4. 没有明确证据或安全修复目标时 no-op，不为轮换覆盖率强行修改。

语义单元只从 `biz-knowledge`、`repo-knowledge`、Skill 和 architecture 中选择。`biz-tests/` 不进入周期语义巡检：它只在具体任务产生稳定、值得重复执行的业务 case 时写回；周期维护仍可通过 `spec health` 检查其索引、引用、凭证和结构完整性。

**修复时机就是发现问题的当前轮次**：确定性或语义问题一旦被当前维护 Agent 核验，立即在同一上下文内修复并复验，不等待另一个 job 或后续 Agent。

运行要求：

- Agent 对 workspace 有读写权限，但禁止 push、发布和部署。
- Python 3、Git、PyYAML 可用。
- 默认禁网；只有需要核验现实一致性时才按需开放明确证据源。
- 凭据由外部系统提供，不写入 workspace 或最终输出。
- 开始前运行 `git status --porcelain` 记录当前工作树状态。不再因全树有未提交改动而整体跳过；改为对每个要修改的目标文件单独检查 `git status --porcelain <file>`：该文件有未提交改动时跳过该文件并记录 `FILE_DIRTY_SKIP: <path>`，干净文件照常修复。

## 单轮流程

### 1. 运行确定性检查

```bash
skills/spec/bin/spec health check --workspace <workspace> --json
```

- exit `0`：进入语义检查。
- exit `1`：当前 Agent 直接核验并修复这些确定性问题。
- exit `2`：停止知识修复，报告检查器或环境错误。

确定性检查覆盖：

- Markdown 引用、canonical INDEX 和磁盘一致性；
- PRD / Biz-Test 索引；
- 根 `ISSUES.md` schema、活动状态和旁路 tracker；
- Skill 路由、自有资源路径和脚本权限；
- 断裂符号链接；
- owner 布局和 INDEX 状态列；
- 分发闭包；
- 工作区与 staged whitespace。

### 2. 按最小单元做语义检查

单轮不必读完整知识库，但必须完整处理一个最小单元，例如：

- `ISSUES.md` 中一个最高优先级问题或同一工具的一组问题；
- 一篇 feature + 相关 biz-knowledge / foundations；
- 一个 Skill + 它引用的 references / scripts；
- 一组 architecture 标准 + 对应路由。

若本轮选择 `ISSUES.md`，必须：

1. 先按 P1 → P2 → P3 选择一个问题或同一工具的一组问题；
2. 用当前代码、CLI `--help`、配置或平台状态重新验证，不能沿用旧记录；
3. 本地可修时在当前上下文完成修复和测试；
4. 外部平台阻塞时只保留最小证据、责任边界和重审条件；
5. 问题解决或被现实推翻后，把仍有复用价值的经验融合到对应 Skill，并从 `ISSUES.md` 删除；
6. 不创建旁路 `Issue.md`、局部 tracker 或已解决归档。

若本轮选择 Skill，必须同时核对：

- 路由 description 和 Route by task 是否覆盖真实用户表达；
- 具体 GUIDE、scripts、tests 是否仍与当前工具行为一致；
- 工具经验是否误写进业务文档，工具缺陷是否误写进稳定指南；
- 聚合 Skill 的内部工具坐标是否能被使用审计观察，而不只统计顶层集合名。

检查：

1. 同一当前事实是否由多个 owner 维护；
2. owner 是否与当前代码、配置或权威来源冲突；
3. 内容类型是否放错 owner；
4. 路由或索引是否复制正文；
5. Skill 是否保存通用常识、历史候选或无消费者内容；
6. 是否存在已无现实对象或消费者的内容；
7. 值得重复执行的验证是否缺少 Biz-Test；
8. 重要决策是否只有裸结论，缺少关键原因、适用边界、重审条件或证据指针。
9. 正式知识是否混入单次事故时间线、一次性 logid、临时账号、会话归档信息或未验证假说；
10. 已验证且可能复现的故障根因是否尚未抽取为包含适用范围、现象、触发条件、判别证据和处理方式的 Failure Mode。
11. 当前结论是否由真实实现、实际配置或可重复命令验证，而不是沿用旧文档、会话结论或字段名称推断；
12. 正式 owner 是否混入会漂移的运行状态，例如当前灰度比例、名单人数、部署工单、版本号或一次执行结果；
13. 新证据已经推翻旧假设时，owner 是否仍保留被证伪结论、修正时间线或“此前假设”叙述。

不以文件年龄作为过期证据。没有现实证据时不判断 stale fact。

### 3. 在当前上下文内直接修复

发现问题后不输出中间 finding，直接按 [knowledge-tidy-runbook.md](knowledge-tidy-runbook.md) 执行最小修复：

- 重新读取 current owner 和证据；
- 确定唯一目标 owner；
- 在目标语义章节融合，不追加时间线；
- 重复副本删除或改为短链接；
- 可执行知识进入 Skill；
- 可重复验证进入 Biz-Test；
- 单次事故历史留在任务/日志系统，只把可复用 Failure Mode 融合到 feature、foundation 或 Skill；
- 先读真实实现并用实际配置或命令验证关键结论；字段存在、旧文档描述和历史会话都不能单独作为正确性证据；
- 删除动态运行状态和被证伪假设，只保留当前稳定事实、适用边界、判别证据和重审条件；
- 重要决策补当前结论、关键原因、边界、重审条件和证据指针；
- 工具自身 bug 或待办进入 `ISSUES.md`，不污染 Skill 的稳定用法；
- 已解决工具问题完成 Skill 迁移后从 `ISSUES.md` 直接删除，不保留完成历史；
- 新建或删除正式文档时同步 canonical INDEX；
- 危险删除先 `mv → /tmp`。

一次只处理一个语义单元，不顺手重塑无关内容。

### 4. 遇到不确定项时停止

以下情况不自动修改：

- 证据不足或互相冲突；
- 需要产品、业务或架构决策；
- 无法确定唯一 owner；
- 修复会改变业务语义；
- 需要访问当前不可用的代码、配置或平台证据。

最终输出 `需要人工决策`，列出证据、冲突点和最小问题；不要创建中间文档。

### 5. 复验

修复后重新运行：

```bash
skills/spec/bin/spec health check --workspace <workspace> --json
```

只有 exit `0` 才算本轮完成。失败时继续修复本轮引入的问题；无法安全修复则回滚或上报人工。

### 6. 提交本轮修改

复验通过后，只暂存并提交本轮自己修改的文件：

```bash
git add <本轮修改的文件列表>
git commit -m "knowledge maintenance: <修复摘要>"
```

- 不得 `git add -A` 或 `git add .`，避免误提交他人未提交改动；
- 不得 push、发布或部署；
- 本轮无修改时不创建空 commit。

## 输出

- 无问题、无修改：输出 `KNOWLEDGE_MAINTENANCE_OK`。
- 有修改：列出修改的 owner 路径、每项修复原因和复验结果。
- 需要人工决策：列出阻塞证据和需要决定的问题。
- 执行错误：保留 exit code、stdout/stderr 和失败步骤。

最终输出是运行结果，不保存为 workspace 文档。

## Canonical Prompt

外部系统直接使用：

```text
skills/workflows/references/knowledge-health-agent-prompt.txt
```

不要复制 prompt 正文，避免出现第二份维护源。
