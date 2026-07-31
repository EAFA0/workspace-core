# Dossier 建立与维护 Runbook（需求工作集索引操作手册）

> **定位**：为一个需求工作区建立/维护 dossier（`<requirement-worktree>/AGENTS.md`）时的**可执行步骤**（how-to，祈使句），不是规范。
> **规范依据**：dossier 的内容边界、Index-Not-Copy 和生命周期见 `docs/architecture/03-knowledge-model.md §3.1`。本 Runbook 只给建立与维护步骤。
> **触发轴**：语义触发车道——agent 对话中命中「建 dossier / 需求工作集 / 压缩老丢背景 / 维护需求上下文入口」时 load。

---

## 通用约束（先读）

- **index-not-copy（铁律）**：除"需求特定约束"段外，一切都是**链接**。别把 PRD/业务/仓库知识正文复制进来——复制必腐化。
- **唯一原创段是"需求特定约束"**：那些压缩后老丢、每次要重提的禁忌/决策/迁移顺序，只有这里能写。这是 dossier 的全部新增价值，别留空。
- **文件即锚点**：dossier 就是 `<requirement-worktree>/AGENTS.md` 本身，兼作支持目录指令注入的 agent 锚点，不另建文件。
- **Dossier 与正式知识边界不变**：需求工作区 dossier 只承载活动期入口；跨需求知识写入 `~/workspace` 单仓中的正式 owner，push 仍遵守 Review-before-push。

---

## 一、建立 dossier（新需求工作区）

### Step 1：确认工作区拓扑
```bash
cd <requirement-worktree>
git rev-parse --show-toplevel 2>/dev/null && echo "⚠️ 根是 git 仓,AGENTS.md 会被 track,确认 .gitignore" || echo "根非 git 仓 ✓"
ls -d */                       # 看涉及哪些仓库或模块
for d in */; do [ -e "$d.git" ] && echo "$d → $(cd $d && git branch --show-current)"; done
```

### Step 2：盘点已有材料（都将被链接，不复制）
- 工作区根已有的散落任务笔记（`*_TASK.md`、`template_*.md` 等）→ 进「上下文指针」段。
- 各需求仓 `ai-docs/change_plans/` 的 plan → 链接。
- 当前 workspace 对应 PRD（`docs/prd/`）、业务知识（`biz-knowledge/`）、仓库知识（`repo-knowledge/`）→ 链接（带行号更佳）。

### Step 3：写 `<requirement-worktree>/AGENTS.md`（骨架见 §四模板）
四段：① 一句话目标 ② 需求特定约束（占位待填）③ 涉及仓库表 ④ 上下文指针。**末尾反向引用 workspace 根规则** `<workspace>/AGENTS.md`，避免只读取需求工作区规则。

### Step 4：确认全局 cwd 指针规则已就位（一次性）
```bash
grep -n "需求工作区指针\|worktree" <workspace>/AGENTS.md
```
- 命中 → 已就位，不自动加载父级规则的 agent 也能被引导过来。
- 未命中 → 在全局 `AGENTS.md` 的“需求入口”补一条："cwd 在 `~/worktree/*` 且根有 AGENTS.md → 新会话/压缩恢复后先读它"。**此规则全局一条即可，不随需求增加**。

### Step 5：填需求特定约束（最重要，可与用户协作）
把用户反复重提的东西固化进约束段，用显式标注：
- `❌ 禁止:` <本需求不能碰的>（如"❌ 禁止: 改动 go.mod / 重编号已存在 IDL 字段号"）
- `⚠️ 约束:` <顺序、边界或不变量>（如"⚠️ 约束: dual-call 模式 oldCall 必须先于 asyncDiffProbe"）
- `📌 决策:` <已定的技术选择 + 一句为什么>

---

## 二、维护 dossier（需求推进中）

- **约束变更**：新增禁忌/决策随时补进约束段——这是活文档，鼓励更新。
- **指针失效**：链接目标移动/重命名 → 同步改链接（dossier 只是索引，断链就失去价值）。
- **不堆历史**：dossier 不是日志。已作废的约束直接删/改，不留"曾经"叙事（06 反模式 #6）。
- **不搬知识**：推进中产生的 durable 洞见先留在约束段或对应 change_plan，**需求完成时**才蒸馏（见 §三），不要中途往 dossier 里灌知识正文。

---

## 三、退役 dossier（需求完成）

需求 merge / 收尾时：
1. **蒸馏 durable 知识**：约束段/指针里沉淀下来的、跨需求可复用的 → 直接融合到业务规则、feature、仓库基座或通用知识。
2. **dossier 退役**：`mv → /tmp`。**不允许把 dossier 当永久知识留存**——它的 durable 部分已经直接进入正式 owner。

---

## 四、dossier 模板（骨架）

```markdown
# 工作集索引:<slug>
> 用途:本需求上下文入口。新会话/压缩恢复后先读。索引+约束,不复制内容。
> 本文件同时是 agent 在本需求工作区的 AGENTS.md。

## 一句话目标
<...>

## 需求特定约束 ⚠️(压缩后最易丢,优先复习)
- ❌ 禁止: <...>
- ⚠️ 约束: <...>
- 📌 决策: <...>

## 涉及仓库
| 仓 | 本需求角色 | 通用知识 |
|----|-----------|-------------------|
| ... | ... | <workspace>/docs/repo-knowledge/... |

## 上下文指针(link,不复制)
- PRD: <...>
- change plan: ./​<repo>/ai-docs/change_plans/<x>.md
- 业务背景: <workspace>/docs/biz-knowledge/<feature>.md
- 本地任务笔记: ./<existing>.md

## 全局规范
- 真相源: <workspace>/AGENTS.md（工作模式/知识层/工具）
```

---

## 五、避坑

- **别复制知识正文**：dossier 一旦开始抄 PRD/业务规则,就腐化成第二真相源了。只链接。
- **约束段别留空**：那是 dossier 唯一新增价值,空着等于白建。
- **双锚点缺一则跨 CLI 失效**：worktree 反向引用全局 + 全局 cwd 指针规则,两条都要在。
- **完成不退役会污染**：需求做完的 dossier 不蒸馏不删,下次进错工作区读到过期约束会误导。
