# Requirement Source Contract

本目录保存需求源的只读导出或稳定链接，是正式知识的溯源入口。

## 规则

- 需求源正文只读，不在归档或整理流程中改写。
- 业务规则提炼到 `docs/biz-knowledge/`。
- 实现知识提炼到 `docs/repo-knowledge/`。
- 只读取当前任务需要的片段，不把完整需求全文注入执行上下文。
- 每份导出必须保留可重新获取原始需求的来源标识。

## 命名

建议使用：

```text
<NN>-<slug>-clean.md
<NN>-<slug>-assets/
```

具体来源平台、导出命令和凭证属于 adapter，不写入本契约。

## 索引

当前 workspace 的需求索引与来源信息位于 [INDEX.md](./INDEX.md)。

知识分类和召回顺序见 [`03-knowledge-model.md`](../architecture/03-knowledge-model.md)。
