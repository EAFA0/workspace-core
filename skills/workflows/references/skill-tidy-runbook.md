# Skill 整理 Runbook

> **定位**：整理 skill 结构与路由时的可执行步骤。
> **文档边界**：每个 skill 自己的 `SKILL.md` 是公开接口 owner；跨 skill 只使用逻辑坐标，规则见 `docs/architecture/06-doc-layering-principles.md`。
> **触发轴**：做整理的 Agent 对话中命中「整理 skill / 工具排布 / skill 集合化 / 折叠 skill / skill 太多了」时 load。

---

## 通用约束（先读，贯穿全程）

- **规范是 SSOT**：一切结构/description/归属判定以本 Runbook 和 `06-doc-layering-principles.md` 为准。判定不确定时回查对应章节。
- **移动不删除**：废弃目录、旧脚本一律 `mv → /tmp`，不 `rm`；仓库内优先 `git mv` 保历史。
- **保持 diff 可读**：一次只做一类。「搬脚本」「转文档」「改引用」「改路由表」分开提交，不混做。
- **验收前不 push**：整理是结构性改动，落地后等人工验收 + 明确 push 审批（见 AGENTS.md 代码协作纪律）。
- **召回优先，控制暴露**：用户会直接点名的工具必须出现在顶层 description 和二级 Route 中，但不等于每个工具都暴露成独立 Skill。
- **默认使用三层披露**：同一 workspace 内工具较多时，优先采用一个宽入口 + 按工具名路由 + 按需加载 GUIDE/scripts，避免始终注入大量 metadata。
- **不按用途分套件**：不以“测试 / 基础设施 / 文档 / 低频”等用途拆成多个集合；集合内部按真实工具名组织。
- **保留独立 owner**：独立生命周期、外部托管、专属运行时契约或无法由集合稳定召回的能力继续单独暴露。
- **归属不明就标记**：拿不准放哪 → 标「待归类」暂留原地，不硬塞进错误集合。

---

## 一、盘点：先看清有什么、在哪、能不能动

整理前必须先建立全景，**跳过盘点直接动手是最大的坑**。

### 1.1 列出所有 skill 及其物理位置

逐个 skill 根目录列清单。区分**物理目录**与**符号链接**——这决定它能不能被折叠：

```bash
# 对每个 skill 根执行；符号链接要看清指向哪
for d in <skill-root>/*; do
  if [ -L "$d" ]; then echo "LINK   $(basename $d) -> $(readlink $d)"; else echo "native $(basename $d)"; fi
done
```

产出一张表：`skill 名 | 物理位置 | native/符号链接 | 指向`。

### 1.2 识别"不可折叠"的来源（关键前置）

有三类来源**不能当普通目录折叠**，动了会引入冲突或丢能力：

| 来源类型 | 识别方法 | 处理原则 |
|---------|---------|---------|
| **外部工具托管**（包管理器/CLI 安装并维护） | 存在 lock 文件（如 `skill-lock.json`）记录该 skill；或目录自带 `.git` 且本仓未 track | **不折叠、不 co-locate**；只在集合 Route 表加文字指针引用（「引用而非复制」原则） |
| **符号链接指向别处** | 1.1 里显示 `LINK ->` | 折叠对象是**链接的源**，不是链接本身；改源前确认源仓是否你能改 |
| **另一个 root 的镜像** | 多个 root 里同名，其一是指向另一处的符号链接 | 只改被指向的那个真身，镜像自动同步 |

> **为什么先做这步**：整理的破坏性主要来自"把托管源当自有目录搬走"。托管方下次同步会还原或冲突。先分清"我的 / 别人的"，再决定动谁。

### 1.3 判断入口粒度

按用户语言判断，而不是按维护者的用途分类：

| 类型 | 默认结构 | 判据 |
|------|----------|------|
| 工具集合 | 顶层 `skills/<collection>/` + `references/<tool>/GUIDE.md` + `scripts/<tool>/` | 同一 workspace 有多个自有工具，需要保留工具名召回并降低公开 Skill 数量 |
| 独立工具 / 平台 Skill | 顶层 `skills/<tool-or-platform>/` | 有独立外部 owner、生命周期、运行时契约，或集合无法稳定召回 |
| 流程 Skill | 少量顶层 workflow + references | 任务横跨多个工具，如开发、测试、排查、知识整理 |
| 注册表 Skill | 独立顶层 | owner 是运行时注册事实，如 background job、lifecycle hook |

不要建立 `infra-suite`、`testing-suite`、`doc-suite`、`long-tail-tools` 这类按用途或频率切分的多个入口。若需要聚合，使用一个宽工具入口，并让所有具体工具名、对象名和常见动词出现在 Layer 1 description 与 Layer 2 Route 中。

## 二、归属判定：每个 Skill 该去哪

对盘点出的每个 Skill 逐个判断：

1. **用户会说什么**：把工具名、平台对象名、常见动词和安全边界写进集合 description 与 Route 示例，不能只写目录分类。
2. **注入预算是否值得独立入口**：只有独立生命周期、外部 owner、专属契约或召回实测不稳定时，才为单工具增加顶层 metadata。
3. **对象是否统一**：若环境、实例查询、直连和灰度对比共享同一环境/实例上下文，可在集合内保留为一个平台工具坐标。
4. **只是任务阶段吗**：开发/测试/排查只保留方法和工具选择，不拥有工具脚本。
5. **只是低频吗**：低频不决定独立或聚合；关键是工具名是否能在 Layer 1/2 被稳定召回。
6. **facade 是否已有 owner**：外部独立 Skill 已被运行时注入时只写逻辑 handoff，不复制或代理。

输出一张归属表：`用户表达 → 顶层入口 → 内部工具坐标 / 独立 Skill → 理由`。跨 root 场景额外标一列：`真实 owner / symlink`。

---

## 三、执行：建立单入口 + 按工具名组织

### 3.1 建立集合公开接口

顶层集合 `SKILL.md` 使用统一工具入口的三层披露：

1. **Layer 1 description**：宽定位、完整工具/对象/动词关键词，以及“先使用本 Skill 再按 Route 读取 GUIDE”的指导句。
2. **Layer 2 Route by task**：每行按真实工具名路由到 `references/<tool>/GUIDE.md`，并附具体用户表达示例。
3. **Layer 3 resources**：具体机制和命令在 GUIDE，确定性执行在 `scripts/<tool>/`。

内部 GUIDE 不保留 frontmatter，防止递归扫描器把它再次暴露成 Skill。不要在 Layer 1 description 中罗列物理子目录。

### 3.2 搬脚本到集合内 `scripts/<tool>/`

```bash
git mv <old>/scripts   skills/<collection>/scripts/<tool>
```

- **保持内部同级关系**：若脚本依赖同级兄弟目录（如 `bin/` 找 `../<pkg>`），必须整体搬、保持相对位置。
- **⚠️ 深度敏感脚本**：脚本里若有 `Path(__file__).parent.parent...`（数到某个根）或写死的相对层级，移动改变了目录深度 → **必须用 `python3 -c` 实测校准**，不要盲目 ±1：

```bash
python3 -c "from pathlib import Path; p=Path('<新路径>/xxx.py').resolve(); print(p.parent.parent.parent)"  # 对照期望根
```

- 自相对脚本（`$SCRIPT_DIR/..`、`dirname(__file__)`）作为整体单元搬迁时**安全**，无需改。

### 3.3 迁移用法文档

- 每个内部工具使用 `references/<tool>/GUIDE.md` 作为工具级入口；详细机制可留在同目录相邻文档。
- 工具名、平台名、常用动词、对象和安全边界由集合 description 与 Route 共同覆盖。
- GUIDE 只维护命令、护栏和专有机制，不重复集合级路由说明。
- 只有满足独立 owner 判据的能力才保留自己的顶层 `SKILL.md` frontmatter。

### 3.4 清理与符号链接处置

- 旧目录先 `mv → /tmp`，确认验收后再由 Git 记录删除；`subskills/`、重复 `scripts/scripts/` 等无意义中间层清空。
- 冗余符号链接（源已被另一 root 独立注入）→ 移到 `/tmp`，Route 表留文字指针。
- 仅经链接可达的刚需 skill（源不在任何注入 root）→ 提升为顶层 `<root>/<name>` 符号链接。
- 空壳目录（建了没填内容）→ `mv → /tmp`。

---

## 四、同步引用：别留断链

折叠改了路径，所有**外部引用**必须同步，否则留下断链。用 grep 定位全部引用点：

```bash
grep -rn "<old-path-fragment>" <所有可能引用处：路由文档 / docs / 其他 skill / runtime 配置>
```

必改清单：
- 集合 `SKILL.md` 的 Route by task 表入口（→ `references/<tool>/GUIDE.md`）+ 示例表达。
- 路由文档里的示例命令路径。
- 文档（知识库/操作手册）里引用该脚本的绝对/相对路径。
- 定时任务/脚本配置里写死的路径。
- 工具文档正文内的「典型命令」示例路径。
- quickstart、USER 和 repo-knowledge 里把内部工具误写成独立 Skill 的措辞。

> **原生历史例外**：Git、任务系统和日志平台中的历史证据不因 workspace 路径变化而重写。

---

## 五、验收：跑命令，不看 diff

结构性改动必须实跑验证，不能只看 diff 判断成功。逐条核：

```bash
# 1. 每个顶层可见 Skill 有且只有一个根 SKILL.md
find skills -mindepth 2 -maxdepth 2 -name SKILL.md
# 2. 集合内部 GUIDE 不带 Skill frontmatter，且不存在工具级 SKILL.md
find skills/<collection>/references -name SKILL.md    # 应为空
# 3. 断链归零（排除托管外部包 + 冻结快照）
grep -rn "<old-path-fragment>" skills/ docs/    # 应为空
# 4. 注入数：物理 vs 含符号链接
find skills -name SKILL.md | wc -l                 # 物理
find -L skills -name SKILL.md 2>/dev/null | wc -l   # 含符号链接跟随（近似实际注入）
# 5. 脚本冒烟：每个搬过的脚本能 --help 或正常报参数错（证明依赖可加载）
<script> --help
# 6. 深度敏感脚本实测解析到正确根（见 3.1）
# 7. 文档引用检查通过
spec refs check
# 8. 源目录未误删
ls -d <各符号链接的源>
```

**最终确认项（工具代不了）**：在真实 CLI 新会话里用具体工具名和自然语言各触发一次，确认命中集合 Skill 并路由到正确 GUIDE，且无 description 截断告警。整理目标是同时提高正确召回并控制公开 metadata；SKILL.md 数量下降不是唯一终判据。

---

## 六、输出报告

```markdown
# Skill 整理报告 - YYYY-MM-DD
## 概览：聚合 X 个内部工具 / 保留 Y 个独立 Skill / 流程入口 Z / 清空壳 M
## 结构变更：[用户表达] → [集合 Skill] → [工具坐标]
## 入口数：物理 A→B，含符号链接 C→D
## 验收：find/grep/冒烟/深度脚本/spec refs 逐条结果
## 待人工确认：### 归属存疑项 / ### 托管源建议 / ### 真实 CLI 注入数复核
## 规范更新建议：无 / 建议改本 Runbook 第 X 节，原因...
```

---

## 七、避坑

- **盘点先行**：没分清 native / 符号链接 / 托管源就动手 = 埋冲突。§一 是硬前置。
- **深度敏感脚本**：`parent×N` 数根的脚本移动后必须实测校准，盲目 ±1 是高频 bug。
- **grep 排除项别过度**：收敛断链时只排除明确托管的外部包；不要排除 workspace 活文档，否则会掩盖真实断链。
- **托管源只引用不搬**：包管理器/CLI 维护的 Skill 会被下次同步还原，只写逻辑 handoff；仅当该源不被任何 root 注入时才加顶层 symlink。
- **不要在数量与召回间二选一**：用宽 description + 工具名 Route 同时控制 metadata 数量和召回；若真实触发测试失败，再把必要能力提升为独立入口。
- **不要复活用途套件**：聚合是减少暴露，不是重新建立 infra/testing/doc/long-tail 多套路由。
- **一次一类、分开提交**：搬脚本 / 转文档 / 改引用 / 改路由混在一个 commit 里，diff 不可读、回滚困难。
- **验收看命令不看 diff**：diff 只能证明"改了"，跑命令才能证明"能用"。
